"""Repeatable product-evaluation metrics, gates, and CLI output."""

import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.evaluation.__main__ import main as evaluation_main  # noqa: E402
from app.evaluation.models import EvaluationDimension, EvaluationReport  # noqa: E402
from app.evaluation.runner import load_dataset, run_evaluation  # noqa: E402


DATASET_PATH = (
    Path(__file__).resolve().parents[1]
    / "evals"
    / "stock_research_reports.v1.json"
)


def dataset_copy():
    return load_dataset(DATASET_PATH).model_copy(deep=True)


def dimension(result, name: EvaluationDimension):
    return result.dimensions[name]


def test_reference_suite_meets_every_quality_gate():
    dataset = dataset_copy()

    result = run_evaluation(dataset)

    assert result.passed is True
    assert result.overall_score == 1.0
    assert set(result.dimensions) == set(EvaluationDimension)
    assert all(metric.passed for metric in result.dimensions.values())
    assert all(metric.evaluated_items > 0 for metric in result.dimensions.values())


def test_citation_numeric_and_freshness_regressions_are_detected():
    citation_dataset = dataset_copy()
    citation_dataset.base_report["news"]["ai_summary"]["statements"][0][
        "citations"
    ] = []
    citation_result = run_evaluation(citation_dataset)
    assert dimension(
        citation_result, EvaluationDimension.CITATION_COVERAGE
    ).score < 1

    numeric_dataset = dataset_copy()
    numeric_dataset.base_report["overview"]["price"]["value"] = 999.0
    numeric_result = run_evaluation(numeric_dataset)
    assert dimension(numeric_result, EvaluationDimension.NUMERIC_ACCURACY).score < 1

    freshness_dataset = dataset_copy()
    freshness_dataset.base_report["overview"]["price"][
        "freshness_status"
    ] = "stale"
    freshness_result = run_evaluation(freshness_dataset)
    assert dimension(
        freshness_result, EvaluationDimension.SOURCE_FRESHNESS
    ).score < 1


def test_contradiction_coverage_and_readability_regressions_are_detected():
    contradiction_dataset = dataset_copy()
    contradiction_dataset.base_report["analysis"]["insights"][0]["explanation"][
        "claim"
    ] = "The leverage values are shown below."
    contradiction_result = run_evaluation(contradiction_dataset)
    assert dimension(
        contradiction_result, EvaluationDimension.CONTRADICTION_HANDLING
    ).score < 1

    coverage_dataset = dataset_copy()
    coverage_dataset.base_report["overview"]["price"] = None
    coverage_result = run_evaluation(coverage_dataset)
    assert dimension(
        coverage_result, EvaluationDimension.IMPORTANT_INFORMATION_COVERAGE
    ).score < 1

    readability_dataset = dataset_copy()
    dense_text = " ".join(["extraordinarycomplexity"] * 100) + "."
    readability_dataset.base_report["analysis"]["ai_narrative"]["statements"][
        0
    ]["text"] = dense_text
    readability_dataset.base_report["analysis"]["ai_narrative"]["statements"][
        1
    ]["text"] = dense_text
    readability_dataset.base_report["news"]["ai_summary"]["statements"][0][
        "text"
    ] = dense_text
    readability_result = run_evaluation(readability_dataset)
    assert dimension(readability_result, EvaluationDimension.READABILITY).score < 0.8


def test_cross_variant_fact_and_language_drift_are_detected():
    personalization_dataset = dataset_copy()
    advanced_case = next(
        case
        for case in personalization_dataset.cases
        if case.id == "en-advanced-growth"
    )
    advanced_case.report_overrides.setdefault("overview", {})["price"] = {
        "value": 130.0
    }
    personalization_result = run_evaluation(personalization_dataset)
    assert dimension(
        personalization_result,
        EvaluationDimension.PERSONALIZATION_CONSISTENCY,
    ).score < 1

    multilingual_dataset = dataset_copy()
    chinese_case = next(
        case
        for case in multilingual_dataset.cases
        if case.id == "zh-beginner-stability"
    )
    chinese_case.report_overrides["analysis"]["ai_narrative"]["statements"][0][
        "text"
    ] = "收入同比增长99%。"
    multilingual_result = run_evaluation(multilingual_dataset)
    assert dimension(
        multilingual_result,
        EvaluationDimension.MULTILINGUAL_CONSISTENCY,
    ).score < 1


def test_baseline_regression_limit_and_machine_readable_cli_output(tmp_path):
    dataset = dataset_copy()
    baseline = run_evaluation(dataset)
    dataset.base_report["overview"]["price"]["value"] = 999.0

    regressed = run_evaluation(dataset, baseline=baseline)

    assert regressed.passed is False
    assert (
        regressed.regressions[EvaluationDimension.NUMERIC_ACCURACY]
        > dataset.maximum_regression
    )

    mismatched_baseline = baseline.model_copy(
        update={"dataset_name": "another evaluation dataset"}
    )
    with pytest.raises(ValueError, match="baseline dataset_name"):
        run_evaluation(dataset, baseline=mismatched_baseline)

    failed_dataset_path = tmp_path / "failed-dataset.json"
    failed_dataset_path.write_text(
        json.dumps(dataset.model_dump(mode="json")), encoding="utf-8"
    )
    failed_output_path = tmp_path / "failed-evaluation.json"
    assert evaluation_main(
        [str(failed_dataset_path), "--output", str(failed_output_path)]
    ) == 1
    assert EvaluationReport.model_validate_json(
        failed_output_path.read_text()
    ).passed is False

    output_path = tmp_path / "evaluation.json"
    exit_code = evaluation_main([str(DATASET_PATH), "--output", str(output_path)])
    written = EvaluationReport.model_validate_json(output_path.read_text())

    assert exit_code == 0
    assert written.passed is True
    assert written.dataset_name == baseline.dataset_name
