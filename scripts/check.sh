#!/usr/bin/env bash
# One command that runs every test suite in this repository from a clean clone.
#
#   scripts/check.sh            # every project
#   scripts/check.sh creator    # one project (see PROJECTS below)
#   JUNIT_DIR=out scripts/check.sh   # also write one JUnit XML file per pytest run
#
# CI runs exactly this script, one project per job, so a green badge and a
# green local run mean the same thing. Needs uv (https://docs.astral.sh/uv/).
# Works inside a Databricks Git folder: no bytecode or pytest cache is written.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONDONTWRITEBYTECODE=1
PYTEST_FLAGS=(-q -p no:cacheprovider)
RUFF_PIN=0.17.5
PROJECTS=(creator ops bakehouse docs analyst probe mcp-local one-hub evidence)
FAILED=()

say() { printf '\n== %s\n' "$*"; }

# FLAGS: the pytest flags for the next run, plus a JUnit XML path when JUNIT_DIR is set.
JN=0
next_flags() {
  JN=$((JN + 1))
  FLAGS=("${PYTEST_FLAGS[@]}")
  if [ -n "${JUNIT_DIR:-}" ]; then
    mkdir -p "$JUNIT_DIR"
    FLAGS+=("--junitxml=$JUNIT_DIR/${CUR:-run}-$JN.xml")
  fi
  return 0
}

# uv projects: their pyproject.toml declares the dev group.
uv_project() {
  local dir="$1"
  (
    cd "$ROOT/$dir" || exit 1
    uv sync --group dev --quiet || exit 1
    next_flags
    uv run --no-sync pytest tests "${FLAGS[@]}" || exit 1
    uv run --no-sync ruff check . || exit 1
    uv run --no-sync ruff format --check . || exit 1
  )
}

# requirements.txt projects: an isolated venv, never the system Python.
req_project() {
  local dir="$1" target="$2"
  (
    cd "$ROOT/$dir" || exit 1
    uv venv --quiet --allow-existing .venv || exit 1
    uv pip install --quiet --python .venv -r requirements.txt pytest pytest-asyncio || exit 1
    next_flags
    PYTHONPATH=src .venv/bin/python -m pytest "$target" "${FLAGS[@]}" || exit 1
    # Hand-written projects carry no ruff config, so pin the version (finding F12).
    uvx --quiet "ruff@$RUFF_PIN" check . || exit 1
  )
}

one_hub() {
  (
    cd "$ROOT/the-one-hub/ops-center" || exit 1
    uv sync --group dev --quiet || exit 1
    # Lint is enforced here too (finding F12), pinned like the other projects.
    uvx --quiet "ruff@$RUFF_PIN" check . || exit 1
    next_flags
    PYTHONPATH=. uv run --no-sync pytest "${FLAGS[@]}" --assert=plain \
      checks/test_analyst.py checks/test_si.py checks/test_work.py \
      checks/test_harness.py checks/test_mcp_server.py checks/test_impact.py checks/test_deploy_config.py checks/test_capture_ask.py || exit 1
    # Script suites print their own summary and exit non-zero on failure.
    for suite in test_agents test_gate test_llm_tracing test_app test_serverless_entrypoints verify; do
      echo "-- checks/$suite.py"
      PYTHONPATH=. uv run --no-sync python "checks/$suite.py" > "/tmp/onehub_$suite.log" 2>&1 \
        || { tail -20 "/tmp/onehub_$suite.log"; exit 1; }
      tail -1 "/tmp/onehub_$suite.log"
    done
  )
}

run() {
  case "$1" in
    creator)   uv_project mcp-server-creator ;;
    ops)       uv_project mcp-servers/mcp-aircarrier-ops ;;
    bakehouse) uv_project mcp-servers/mcp-bakehouse-sales ;;
    docs)      req_project mcp-servers/mcp-aircarrier-docs tests ;;
    analyst)   req_project mcp-servers/mcp-aircarrier-analyst tests ;;
    probe)     req_project mcp-servers/aircarrier-mcp-probe test_probe.py ;;
    mcp-local) (cd "$ROOT/mcp-servers" && next_flags && uv run --quiet --no-project --with pytest \
                 --with "fastmcp>=3.4,<4" python -m pytest test_mcp_local.py "${FLAGS[@]}" \
               && echo "-- instruction text in results is reported (source_notice)" \
               && next_flags && uv run --quiet --no-project --with pytest --with "fastmcp>=3.4,<4" \
                 --with-requirements mcp-aircarrier-ops/requirements.txt \
                 python -m pytest test_source_notice.py "${FLAGS[@]}" \
               && echo "-- a failure reaches the client as an error (error_contract)" \
               && next_flags && uv run --quiet --no-project --with pytest \
                 --with-requirements ../mcp-server-creator/requirements.txt \
                 python -m pytest test_error_contract.py "${FLAGS[@]}" \
               && echo "-- adversarial arguments against all 30 Air Carrier tools" \
               && next_flags && uv run --quiet --no-project --with pytest --with "fastmcp>=3.4,<4" \
                 --with "mcp>=1.24,<2" \
                 --with-requirements mcp-aircarrier-docs/requirements.txt \
                 --with-requirements mcp-aircarrier-analyst/requirements.txt \
                 --with-requirements mcp-aircarrier-ops/requirements.txt \
                 python -m pytest test_adversarial_arguments.py "${FLAGS[@]}") ;;
    one-hub)   one_hub ;;
    evidence)  (cd "$ROOT" && python3 scripts/check_links.py \
                 && python3 scripts/check_portability.py \
                 && python3 eval/delegation/analyze.py > /tmp/delegation_results.md \
                 && diff -u eval/delegation/RESULTS.md /tmp/delegation_results.md \
                 && echo "eval/delegation/RESULTS.md matches runs.csv" \
                 && next_flags && uvx --quiet pytest "${FLAGS[@]}" eval/delegation/round4/test_grade.py \
                      eval/delegation/round4/test_runner.py \
                 && python3 -B eval/delegation/round4/analyze_round4.py > /tmp/delegation_results_r4.md \
                 && diff -u eval/delegation/round4/RESULTS.md /tmp/delegation_results_r4.md \
                 && echo "eval/delegation/round4/RESULTS.md matches runs_r4.csv") ;;
    *) echo "unknown project: $1 (choose from: ${PROJECTS[*]})"; return 2 ;;
  esac
}

targets=("$@")
[ ${#targets[@]} -eq 0 ] && targets=("${PROJECTS[@]}")
for p in "${targets[@]}"; do
  CUR="$p"
  say "$p"
  if run "$p"; then echo "PASS $p"; else echo "FAIL $p"; FAILED+=("$p"); fi
done

echo
if [ ${#FAILED[@]} -eq 0 ]; then
  echo "All ${#targets[@]} project(s) passed."
else
  echo "Failed: ${FAILED[*]}"
  exit 1
fi
