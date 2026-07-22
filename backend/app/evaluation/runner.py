"""Deterministic scoring engine for stock research report evaluation."""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import date, datetime
import json
import math
from pathlib import Path
import re
from typing import Any, Iterable

from pydantic import BaseModel

from ..models.schemas import ResearchReportDraft
from ..services import evidence_auditor
from .models import (
    DimensionResult,
    EvaluationCase,
    EvaluationDataset,
    EvaluationDetail,
    EvaluationDimension,
    EvaluationReport,
)


SENTENCE_SPLIT_RE = re.compile(r"[.!?。！？]+")
LATIN_WORD_RE = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*", re.UNICODE)
CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")


def load_dataset(path: str | Path) -> EvaluationDataset:
    """Load and validate a versioned evaluation dataset."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return EvaluationDataset.model_validate(payload)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _materialize_report(dataset: EvaluationDataset, case: EvaluationCase):
    payload = _deep_merge(dataset.base_report, case.report_overrides)
    for path, value in case.report_path_overrides.items():
        if not _set_existing_path(payload, path, deepcopy(value)):
            raise ValueError(
                f"case {case.id!r} has an invalid report_path_overrides path: {path}"
            )
    return ResearchReportDraft.model_validate(payload)


def _payload(report: BaseModel) -> dict[str, Any]:
    return report.model_dump(mode="python")


def _resolve(root: Any, path: str) -> Any:
    if not path or path.startswith(".") or "__" in path:
        return None
    current = root
    for token in path.split("."):
        if isinstance(current, dict):
            if token not in current:
                return None
            current = current[token]
        elif isinstance(current, list) and token.isdigit():
            index = int(token)
            if index >= len(current):
                return None
            current = current[index]
        else:
            return None
    return current


def _set_existing_path(root: Any, path: str, value: Any) -> bool:
    tokens = path.split(".")
    if not path or path.startswith(".") or "__" in path:
        return False
    current = root
    for token in tokens[:-1]:
        if isinstance(current, dict) and token in current:
            current = current[token]
        elif isinstance(current, list) and token.isdigit() and int(token) < len(current):
            current = current[int(token)]
        else:
            return False
    final = tokens[-1]
    if isinstance(current, dict) and final in current:
        current[final] = value
        return True
    if isinstance(current, list) and final.isdigit() and int(final) < len(current):
        current[int(final)] = value
        return True
    return False


def _nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (str, list, dict, tuple, set)):
        return bool(value)
    return True


def _walk_provenance(
    node: Any, path: str = ""
) -> Iterable[tuple[str, dict[str, Any]]]:
    if isinstance(node, dict):
        if evidence_auditor._is_provenance(node):
            yield path, node
        for key, value in node.items():
            child_path = f"{path}.{key}" if path else str(key)
            yield from _walk_provenance(value, child_path)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            child_path = f"{path}.{index}" if path else str(index)
            yield from _walk_provenance(value, child_path)


def _generated_nodes(root: dict[str, Any]):
    return [
        (path, node)
        for path, node in _walk_provenance(root)
        if "claim" in node and evidence_auditor._is_generated(node)
    ]


def _statement_records(root: dict[str, Any]):
    for path, node in _generated_nodes(root):
        statements = node.get("statements") or [
            {"text": str(node.get("claim") or ""), "citations": node.get("citations") or []}
        ]
        for index, statement in enumerate(statements):
            yield path, index, statement


def _detail(
    id_: str,
    passed: bool,
    message: str,
    *,
    score: float | None = None,
    observed: Any = None,
    expected: Any = None,
) -> EvaluationDetail:
    return EvaluationDetail(
        id=id_,
        passed=passed,
        score=float(passed) if score is None else max(0.0, min(1.0, score)),
        message=message,
        observed=observed,
        expected=expected,
    )


def _citation_details(case_id: str, root: dict[str, Any]):
    details = []
    for evidence_path, index, statement in _statement_records(root):
        citations = statement.get("citations") or []
        resolved = [_resolve(root, path) for path in citations]
        valid = bool(citations) and all(
            evidence_auditor._is_supporting_node(node)
            and evidence_auditor._citation_allowed(evidence_path, citation)
            for citation, node in zip(citations, resolved)
        )
        details.append(
            _detail(
                f"{case_id}:{evidence_path}.statements.{index}",
                valid,
                "Generated statement has valid report-local support."
                if valid
                else "Generated statement is missing valid report-local support.",
                observed=citations,
                expected="one or more valid citations",
            )
        )
    if not details:
        details.append(
            _detail(
                f"{case_id}:generated-statements",
                False,
                "No generated statements were available to measure citation coverage.",
            )
        )
    return details


def _numeric_value(value: Any) -> float | None:
    if isinstance(value, dict) and "value" in value:
        value = value["value"]
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _numeric_details(case_id: str, root: dict[str, Any], dataset: EvaluationDataset):
    details = []
    for expectation in dataset.numeric_expectations:
        observed = _numeric_value(_resolve(root, expectation.path))
        passed = observed is not None and math.isclose(
            observed,
            expectation.expected,
            rel_tol=expectation.relative_tolerance,
            abs_tol=expectation.absolute_tolerance,
        )
        details.append(
            _detail(
                f"{case_id}:{expectation.id}",
                passed,
                "Structured value matches the reference value."
                if passed
                else "Structured value differs from the reference value.",
                observed=observed,
                expected=expectation.expected,
            )
        )

    for evidence_path, index, statement in _statement_records(root):
        text = str(statement.get("text") or "")
        if not evidence_auditor._number_values(text):
            continue
        citations = statement.get("citations") or []
        cited_nodes = [
            node
            for citation in citations
            if evidence_auditor._is_supporting_node(node := _resolve(root, citation))
        ]
        unsupported = evidence_auditor._unsupported_numbers(text, cited_nodes)
        passed = bool(cited_nodes) and not unsupported
        details.append(
            _detail(
                f"{case_id}:{evidence_path}.statements.{index}:numbers",
                passed,
                "Narrative numbers match cited evidence."
                if passed
                else "Narrative contains a number not supported by its citations.",
                observed=unsupported,
                expected=[],
            )
        )
    return details


def _as_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _freshness_details(
    case_id: str,
    report: ResearchReportDraft,
    root: dict[str, Any],
    maximum_age_days: int,
):
    captured = report.captured_at.date()
    details = []
    for path, node in _walk_provenance(root):
        status = getattr(node.get("freshness_status"), "value", node.get("freshness_status"))
        as_of = _as_date(node.get("as_of_date"))
        age = (captured - as_of).days if as_of else None
        if status == "historical":
            passed = True
        else:
            passed = status == "fresh" and age is not None and 0 <= age <= maximum_age_days
        details.append(
            _detail(
                f"{case_id}:{path}",
                passed,
                "Source freshness label and age are acceptable."
                if passed
                else "Source is stale, unknown, future-dated, or older than the allowed window.",
                observed={"status": status, "age_days": age},
                expected={"status": "fresh or historical", "maximum_age_days": maximum_age_days},
            )
        )
    return details


def _claim_text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("claim") or value.get("text") or "")
    return str(value or "")


def _contradiction_details(
    case_id: str,
    report: ResearchReportDraft,
    root: dict[str, Any],
    dataset: EvaluationDataset,
):
    audit = evidence_auditor.audit_research_report(report).audit
    details = []
    for expectation in dataset.contradictions:
        facts_present = all(_nonempty(_resolve(root, path)) for path in expectation.fact_paths)
        issue_detected = any(
            issue.code == expectation.required_issue_code
            and set(expectation.fact_paths)
            <= {issue.path, *issue.related_paths}
            for issue in audit.issues
        )
        acknowledgement = " ".join(
            _claim_text(_resolve(root, path))
            for path in expectation.acknowledgement_paths
        ).casefold()
        terms_present = all(
            term.casefold() in acknowledgement
            for term in expectation.acknowledgement_terms
        )
        passed = facts_present and issue_detected and terms_present
        details.append(
            _detail(
                f"{case_id}:{expectation.id}",
                passed,
                "Conflicting facts are preserved, detected, and explicitly acknowledged."
                if passed
                else "The contradiction is missing, undetected, or not acknowledged in the report.",
                observed={
                    "facts_present": facts_present,
                    "issue_detected": issue_detected,
                    "acknowledgement_terms_present": terms_present,
                },
                expected=True,
            )
        )
    return details


def _important_information_details(
    case_id: str, root: dict[str, Any], dataset: EvaluationDataset
):
    details = []
    for expectation in dataset.important_information:
        present = [_nonempty(_resolve(root, path)) for path in expectation.paths]
        passed = all(present) if expectation.mode == "all" else any(present)
        details.append(
            _detail(
                f"{case_id}:{expectation.id}",
                passed,
                "Important report information is present."
                if passed
                else "Important report information is missing.",
                observed=dict(zip(expectation.paths, present)),
                expected=expectation.mode,
            )
        )
    return details


def _readability_score(text: str) -> tuple[float, dict[str, Any]]:
    sentences = [part.strip() for part in SENTENCE_SPLIT_RE.split(text) if part.strip()]
    if not sentences:
        return 0.0, {"reason": "no sentences"}

    cjk_count = len(CJK_RE.findall(text))
    latin_words = LATIN_WORD_RE.findall(text)
    if cjk_count >= max(4, len(latin_words)):
        average_units = cjk_count / len(sentences)
        sentence_score = max(0.0, min(1.0, (55 - average_units) / 27))
        score = sentence_score
        detail = {
            "script": "cjk",
            "sentences": len(sentences),
            "characters": cjk_count,
            "average_characters_per_sentence": round(average_units, 2),
        }
    else:
        if not latin_words:
            return 0.0, {"reason": "no readable words"}
        average_units = len(latin_words) / len(sentences)
        long_ratio = sum(len(word) > 10 for word in latin_words) / len(latin_words)
        sentence_score = max(0.0, min(1.0, (32 - average_units) / 16))
        vocabulary_score = max(0.0, min(1.0, (0.4 - long_ratio) / 0.25))
        score = 0.75 * sentence_score + 0.25 * vocabulary_score
        detail = {
            "script": "latin",
            "sentences": len(sentences),
            "words": len(latin_words),
            "average_words_per_sentence": round(average_units, 2),
            "long_word_ratio": round(long_ratio, 3),
        }
    return round(score, 6), detail


def _readability_details(
    case_id: str, root: dict[str, Any], dataset: EvaluationDataset
):
    details = []
    for path in dataset.readability_paths:
        text = _claim_text(_resolve(root, path))
        score, diagnostics = _readability_score(text)
        passed = score >= dataset.thresholds[EvaluationDimension.READABILITY]
        details.append(
            _detail(
                f"{case_id}:{path}",
                passed,
                "Text meets the deterministic plain-language heuristic."
                if passed
                else "Text is too dense for the configured readability threshold.",
                score=score,
                observed=diagnostics,
                expected={
                    "minimum_score": dataset.thresholds[EvaluationDimension.READABILITY]
                },
            )
        )
    return details


def _normalized(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return getattr(value, "value", value)


def _fact_fingerprint(root: dict[str, Any]) -> list[str]:
    facts = []
    for _, node in _walk_provenance(root):
        if "claim" not in node and "value" not in node:
            continue
        if "claim" in node and evidence_auditor._is_generated(node):
            continue
        fact = {
            "provider": _normalized(node.get("provider")),
            "source": _normalized(node.get("source")),
            "as_of_date": _normalized(node.get("as_of_date")),
            "freshness_status": _normalized(node.get("freshness_status")),
            "claim": _normalized(node.get("claim")),
            "value": _normalized(node.get("value")),
            "unit": _normalized(node.get("unit")),
        }
        facts.append(json.dumps(fact, ensure_ascii=False, sort_keys=True))
    return sorted(facts)


def _presentation_details(
    dataset: EvaluationDataset,
    cases: list[tuple[EvaluationCase, ResearchReportDraft, dict[str, Any]]],
):
    details = []
    groups: dict[str, list[tuple[EvaluationCase, dict[str, Any]]]] = defaultdict(list)
    for case, _, root in cases:
        if case.personalization_group:
            groups[case.personalization_group].append((case, root))

    for group, members in groups.items():
        fingerprints = [_fact_fingerprint(root) for _, root in members]
        same_facts = all(value == fingerprints[0] for value in fingerprints[1:])
        details.append(
            _detail(
                f"{group}:fact-invariance",
                same_facts,
                "Personalization variants preserve the same sourced facts."
                if same_facts
                else "Personalization changed, removed, or invented sourced facts.",
                observed=[len(value) for value in fingerprints],
                expected="identical fact fingerprints",
            )
        )
        for case, root in members:
            passed, observed, expected_payload = _presentation_contract(case, root)
            details.append(
                _detail(
                    f"{case.id}:presentation-contract",
                    passed,
                    "Presentation matches the profile-specific contract."
                    if passed
                    else "Presentation does not match the profile-specific contract.",
                    observed=observed,
                    expected=expected_payload,
                )
            )
    if not details:
        details.append(
            _detail(
                "personalization-groups",
                False,
                "No personalization comparison group was provided.",
            )
        )
    return details


def _presentation_contract(
    case: EvaluationCase, root: dict[str, Any]
) -> tuple[bool, dict[str, Any], Any]:
    expected = case.expected_presentation
    observed_plan = _resolve(
        root, "analysis.personalized_interpretation.presentation"
    )
    highlighted_codes = _resolve(
        root, "analysis.personalized_interpretation.report_emphasis"
    ) or []
    observed = {
        "presentation": observed_plan,
        "highlighted_insight_flags": highlighted_codes,
    }
    if expected is None:
        return False, observed, None
    expected_payload = expected.model_dump(mode="python")
    plan_matches = isinstance(observed_plan, dict) and all(
        observed_plan.get(key) == value for key, value in expected_payload.items()
    )
    flags_match = highlighted_codes == expected_payload["highlighted_insight_codes"]
    return plan_matches and flags_match, observed, {
        "presentation": expected_payload,
        "highlighted_insight_flags": expected_payload["highlighted_insight_codes"],
    }


def _generated_signature(root: dict[str, Any]) -> list[str]:
    signatures = []
    for _, _, statement in _statement_records(root):
        signature = {
            "citations": sorted(statement.get("citations") or []),
            "numbers": sorted(evidence_auditor._number_values(statement.get("text"))),
        }
        signatures.append(json.dumps(signature, sort_keys=True))
    return sorted(signatures)


def _multilingual_details(
    dataset: EvaluationDataset,
    cases: list[tuple[EvaluationCase, ResearchReportDraft, dict[str, Any]]],
):
    details = []
    groups: dict[str, list[tuple[EvaluationCase, dict[str, Any]]]] = defaultdict(list)
    for case, _, root in cases:
        if case.multilingual_group:
            groups[case.multilingual_group].append((case, root))

    for group, members in groups.items():
        locales = {case.locale.value for case, _ in members}
        fingerprints = [_fact_fingerprint(root) for _, root in members]
        signatures = [_generated_signature(root) for _, root in members]
        consistent = (
            len(locales) >= 2
            and all(value == fingerprints[0] for value in fingerprints[1:])
            and all(value == signatures[0] for value in signatures[1:])
        )
        details.append(
            _detail(
                f"{group}:cross-language-invariance",
                consistent,
                "Languages preserve sourced facts, narrative numbers, and citation targets."
                if consistent
                else "A language variant changed facts, narrative numbers, or citation targets.",
                observed={"locales": sorted(locales)},
                expected="at least two locales with identical invariants",
            )
        )
        for case, root in members:
            text = " ".join(
                _claim_text(_resolve(root, path))
                for path in dataset.readability_paths
            ).casefold()
            markers_present = bool(case.language_markers) and all(
                marker.casefold() in text for marker in case.language_markers
            )
            details.append(
                _detail(
                    f"{case.id}:language-markers",
                    markers_present,
                    "Expected locale markers appear in generated narrative."
                    if markers_present
                    else "Generated narrative is missing expected locale markers.",
                    observed=case.language_markers if markers_present else text,
                    expected=case.language_markers,
                )
            )
            presentation_passed, observed, expected = _presentation_contract(case, root)
            details.append(
                _detail(
                    f"{case.id}:localized-presentation-contract",
                    presentation_passed,
                    "Localized report preserves its presentation contract."
                    if presentation_passed
                    else "Localized report changed its presentation contract or highlight flags.",
                    observed=observed,
                    expected=expected,
                )
            )
    if not details:
        details.append(
            _detail(
                "multilingual-groups",
                False,
                "No multilingual comparison group was provided.",
            )
        )
    return details


def _aggregate(
    dimension: EvaluationDimension,
    details: list[EvaluationDetail],
    dataset: EvaluationDataset,
) -> DimensionResult:
    score = sum(detail.score for detail in details) / len(details) if details else 0.0
    score = round(score, 6)
    threshold = dataset.thresholds[dimension]
    return DimensionResult(
        score=score,
        threshold=threshold,
        passed=score >= threshold,
        evaluated_items=len(details),
        passed_items=sum(detail.passed for detail in details),
        details=details,
    )


def run_evaluation(
    dataset: EvaluationDataset,
    *,
    baseline: EvaluationReport | None = None,
) -> EvaluationReport:
    """Run all eight dimensions against every materialized report variant."""
    if baseline and baseline.dataset_name != dataset.name:
        raise ValueError("baseline dataset_name does not match the evaluation dataset")
    materialized = [
        (case, report, _payload(report))
        for case in dataset.cases
        for report in [_materialize_report(dataset, case)]
    ]

    per_dimension: dict[EvaluationDimension, list[EvaluationDetail]] = {
        dimension: [] for dimension in EvaluationDimension
    }
    for case, report, root in materialized:
        per_dimension[EvaluationDimension.CITATION_COVERAGE].extend(
            _citation_details(case.id, root)
        )
        per_dimension[EvaluationDimension.NUMERIC_ACCURACY].extend(
            _numeric_details(case.id, root, dataset)
        )
        per_dimension[EvaluationDimension.SOURCE_FRESHNESS].extend(
            _freshness_details(
                case.id, report, root, dataset.maximum_source_age_days
            )
        )
        per_dimension[EvaluationDimension.CONTRADICTION_HANDLING].extend(
            _contradiction_details(case.id, report, root, dataset)
        )
        per_dimension[EvaluationDimension.IMPORTANT_INFORMATION_COVERAGE].extend(
            _important_information_details(case.id, root, dataset)
        )
        per_dimension[EvaluationDimension.READABILITY].extend(
            _readability_details(case.id, root, dataset)
        )

    per_dimension[EvaluationDimension.PERSONALIZATION_CONSISTENCY].extend(
        _presentation_details(dataset, materialized)
    )
    per_dimension[EvaluationDimension.MULTILINGUAL_CONSISTENCY].extend(
        _multilingual_details(dataset, materialized)
    )

    dimensions = {
        dimension: _aggregate(dimension, details, dataset)
        for dimension, details in per_dimension.items()
    }
    overall_score = round(
        sum(result.score for result in dimensions.values()) / len(dimensions), 6
    )
    regressions = {}
    if baseline:
        for dimension, result in dimensions.items():
            previous = baseline.dimensions.get(dimension)
            if previous and previous.score > result.score:
                regressions[dimension] = round(previous.score - result.score, 6)

    passed = (
        all(result.passed for result in dimensions.values())
        and overall_score >= dataset.overall_threshold
        and all(drop <= dataset.maximum_regression for drop in regressions.values())
    )
    return EvaluationReport(
        dataset_name=dataset.name,
        case_ids=[case.id for case in dataset.cases],
        dimensions=dimensions,
        overall_score=overall_score,
        overall_threshold=dataset.overall_threshold,
        regressions=regressions,
        maximum_regression=dataset.maximum_regression,
        passed=passed,
    )
