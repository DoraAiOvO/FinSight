"""Command-line entry point for the deterministic product evaluation suite."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .models import EvaluationReport
from .runner import load_dataset, run_evaluation


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate FinSight stock research reports against a fixed dataset."
    )
    parser.add_argument("dataset", help="Path to the versioned evaluation dataset JSON")
    parser.add_argument(
        "--baseline",
        help="Optional prior evaluation JSON; regressions beyond the dataset limit fail",
    )
    parser.add_argument("--output", help="Optional path for the full JSON result")
    parser.add_argument(
        "--allow-failures",
        action="store_true",
        help="Always exit zero while preserving pass/fail in the JSON result",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    dataset = load_dataset(args.dataset)
    baseline = None
    if args.baseline:
        baseline = EvaluationReport.model_validate_json(
            Path(args.baseline).read_text(encoding="utf-8")
        )
    result = run_evaluation(dataset, baseline=baseline)
    rendered = json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered + "\n", encoding="utf-8")
        print(
            f"{result.dataset_name}: {'PASS' if result.passed else 'FAIL'} "
            f"({result.overall_score:.3f}) -> {output}"
        )
    else:
        print(rendered)
    return 0 if result.passed or args.allow_failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
