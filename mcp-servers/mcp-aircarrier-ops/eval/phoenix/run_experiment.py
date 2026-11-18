"""Run an experiment: the agent plus the judges, against a dataset.

    uv run run_experiment.py --dataset-name mcp-eval-0
    uv run run_experiment.py --dataset-name mcp-eval-0 --no-tools
    uv run run_experiment.py --dataset-name mcp-eval-0 \
        --system-prompt-version v2 --repeats 3

`--no-tools` is the baseline. The gap between it and the tooled run is the
server's contribution, and it is the number worth reporting.
"""

from __future__ import annotations

import argparse

from agent import AircarrierOpsAgent
from dotenv import load_dotenv
from judges import check_answer_scope, match_expected_response

load_dotenv()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-name", default="mcp-eval-0")
    parser.add_argument("--system-prompt-version", default="v1", choices=["v1", "v2"])
    parser.add_argument("--project-name", default="mcp-eval-0")
    parser.add_argument("--phoenix-endpoint", default="http://localhost:6006/v1/traces")
    parser.add_argument("--experiment-description", default="")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument(
        "--no-tools",
        action="store_true",
        help="Run the baseline: same questions, no MCP server attached.",
    )
    args = parser.parse_args()

    from phoenix.client import Client

    client = Client()
    dataset = client.datasets.get_dataset(dataset=args.dataset_name)

    agent = AircarrierOpsAgent(
        system_prompt_version=args.system_prompt_version,
        project_name=args.project_name,
        phoenix_endpoint=args.phoenix_endpoint,
        with_tools=not args.no_tools,
    )

    label = "baseline-no-tools" if args.no_tools else "with-server"
    description = (
        args.experiment_description or f"{label}, prompt {args.system_prompt_version}"
    )

    results = client.experiments.run_experiment(
        dataset=dataset,
        task=agent.create_experiment_task(),
        evaluators=[check_answer_scope, match_expected_response],
        experiment_description=description,
        repetitions=args.repeats,
    )
    print(results)
    print(
        "\nReview per-question traces at http://localhost:6006 and decide "
        "whether each failure belongs to the tool schema, the docstring, the "
        "return shape, or the question."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
