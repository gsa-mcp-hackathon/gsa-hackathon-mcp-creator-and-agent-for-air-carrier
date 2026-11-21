#!/usr/bin/env bash
# One command that runs every test suite in this repository from a clean clone.
#
#   scripts/check.sh            # every project
#   scripts/check.sh creator    # one project (see PROJECTS below)
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

# uv projects: their pyproject.toml declares the dev group.
uv_project() {
  local dir="$1"
  (
    cd "$ROOT/$dir" || exit 1
    uv sync --group dev --quiet || exit 1
    uv run --no-sync pytest tests "${PYTEST_FLAGS[@]}" || exit 1
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
    PYTHONPATH=src .venv/bin/python -m pytest "$target" "${PYTEST_FLAGS[@]}" || exit 1
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
    PYTHONPATH=. uv run --no-sync pytest "${PYTEST_FLAGS[@]}" --assert=plain \
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
    mcp-local) (cd "$ROOT/mcp-servers" && uv run --quiet --no-project --with pytest \
                 --with "fastmcp>=2.14,<3" python -m pytest test_mcp_local.py "${PYTEST_FLAGS[@]}" \
               && echo "-- adversarial arguments against all 30 Air Carrier tools" \
               && uv run --quiet --no-project --with pytest --with "fastmcp>=2.14,<3" \
                 --with "mcp>=1.24,<2" \
                 --with-requirements mcp-aircarrier-docs/requirements.txt \
                 --with-requirements mcp-aircarrier-analyst/requirements.txt \
                 --with-requirements mcp-aircarrier-ops/requirements.txt \
                 python -m pytest test_adversarial_arguments.py "${PYTEST_FLAGS[@]}") ;;
    one-hub)   one_hub ;;
    evidence)  (cd "$ROOT" && python3 scripts/check_links.py \
                 && python3 eval/delegation/analyze.py > /tmp/delegation_results.md \
                 && diff -u eval/delegation/RESULTS.md /tmp/delegation_results.md \
                 && echo "eval/delegation/RESULTS.md matches runs.csv") ;;
    *) echo "unknown project: $1 (choose from: ${PROJECTS[*]})"; return 2 ;;
  esac
}

targets=("$@")
[ ${#targets[@]} -eq 0 ] && targets=("${PROJECTS[@]}")
for p in "${targets[@]}"; do
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
