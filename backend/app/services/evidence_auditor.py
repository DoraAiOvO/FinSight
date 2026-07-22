"""Deterministic evidence auditing and factual-conclusion blocking.

The auditor never asks an LLM whether another LLM is correct. It validates the
report's structured provenance, citations, units, and numeric consistency, then
removes generated statements that do not pass those checks.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import math
import re
from typing import Any, Iterable

from pydantic import BaseModel

from ..models.schemas import (
    AuditIssueCode,
    AuditSeverity,
    AuditStatus,
    EvidenceAudit,
    ResearchReportAuditResponse,
    ResearchReportDraft,
    ResearchSnapshot,
)


CHECKS = list(AuditIssueCode)
AI_PROVIDERS = {"anthropic", "openai", "google", "mistral", "cohere"}
PROVENANCE_KEYS = {
    "provider",
    "source",
    "as_of_date",
    "fetched_at",
    "freshness_status",
    "confidence",
}

RATIO_KEYS = {
    "profit_margin",
    "operating_margin",
    "revenue_growth",
    "earnings_growth",
    "free_cash_flow_margin",
    "dividend_yield",
    "discount_rate",
    "terminal_growth",
    "annual_share_dilution",
    "upside_downside",
    "implied_revenue_growth",
    "search_lower_bound",
    "search_upper_bound",
    "terminal_growth_rates",
}
PERCENT_KEYS = {"change_percent", "debt_to_equity"}
CURRENCY_KEYS = {
    "price",
    "market_cap",
    "free_cash_flow",
    "total_revenue",
    "total_cash",
    "total_debt",
    "current_price",
    "trailing_eps",
    "fifty_two_week_low",
    "fifty_two_week_high",
    "analyst_target_mean",
    "projected_revenue",
    "projected_free_cash_flow",
    "present_value",
    "present_value_explicit_cash_flows",
    "terminal_value",
    "present_value_terminal_value",
    "enterprise_value",
    "equity_value",
}
PER_SHARE_KEYS = {
    "intrinsic_value_per_share",
    "implied_value_per_share",
    "target_price",
    "low",
    "base",
    "high",
}
MULTIPLE_KEYS = {
    "trailing_pe",
    "forward_pe",
    "price_to_sales",
    "current_ratio",
    "beta",
    "peer_median_multiple",
}

NUMBER_RE = re.compile(
    # ASCII boundaries keep identifiers such as Q2 out while still allowing
    # numbers next to CJK text (for example, "收入增长24%").
    r"(?<![A-Za-z0-9_.])(?P<currency>[$€£])?"
    r"(?P<number>[-+]?\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<suffix>%|[KMBT]|thousand|million|billion|trillion)?",
    re.IGNORECASE,
)
SUFFIX_SCALE = {
    "k": 1_000,
    "thousand": 1_000,
    "m": 1_000_000,
    "million": 1_000_000,
    "b": 1_000_000_000,
    "billion": 1_000_000_000,
    "t": 1_000_000_000_000,
    "trillion": 1_000_000_000_000,
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def _section(path: str) -> str:
    return path.split(".", 1)[0] if path else "report"


def _is_provenance(node: Any) -> bool:
    return isinstance(node, dict) and PROVENANCE_KEYS <= node.keys()


def _walk(node: Any, path: str = "") -> Iterable[tuple[str, str, dict]]:
    if isinstance(node, dict):
        if _is_provenance(node):
            if "claim" in node:
                yield "evidence", path, node
            elif "value" in node:
                yield "data_point", path, node
            else:
                yield "provenance", path, node
        for key, value in node.items():
            child_path = f"{path}.{key}" if path else str(key)
            yield from _walk(value, child_path)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            child_path = f"{path}.{index}" if path else str(index)
            yield from _walk(value, child_path)


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


def _set_path(root: Any, path: str, value: Any) -> bool:
    tokens = path.split(".")
    current = root
    for token in tokens[:-1]:
        if isinstance(current, dict) and token in current:
            current = current[token]
        elif (
            isinstance(current, list)
            and token.isdigit()
            and int(token) < len(current)
        ):
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


def _metric_key(root: dict, path: str) -> str:
    tokens = path.split(".")
    if len(tokens) >= 2 and tokens[0] == "overview":
        return tokens[1]
    if len(tokens) >= 3 and tokens[:2] == ["valuation", "inputs"]:
        return tokens[2]
    if len(tokens) >= 6 and tokens[:2] == ["analysis", "insights"]:
        item_path = ".".join(tokens[:5])
        item = _resolve(root, item_path)
        if isinstance(item, dict) and item.get("metric_key"):
            return str(item["metric_key"])
    if len(tokens) >= 5 and tokens[:3] == ["analysis", "benchmarks", "metrics"]:
        metric = _resolve(root, ".".join(tokens[:4]))
        if isinstance(metric, dict) and metric.get("metric_key"):
            return str(metric["metric_key"])
    if len(tokens) >= 5 and tokens[:2] == ["comparison", "rows"]:
        row = _resolve(root, ".".join(tokens[:3]))
        if isinstance(row, dict) and row.get("metric"):
            return str(row["metric"])
    return tokens[-2] if tokens[-1].isdigit() and len(tokens) > 1 else tokens[-1]


def _accepted_units(root: dict, path: str) -> set[str | None] | None:
    key = _metric_key(root, path)
    overview = root.get("overview") or {}
    valuation = root.get("valuation") or {}
    currency = (
        str(overview.get("currency") or valuation.get("currency") or "").upper()
        or None
    )
    if key in RATIO_KEYS:
        return {"ratio"}
    if key in PERCENT_KEYS:
        return {"percent"}
    if key in CURRENCY_KEYS:
        if currency is None:
            return None
        if key == "price" and path.startswith("history."):
            return {"price", currency}
        return {currency, f"{currency}/share" if key == "trailing_eps" else currency}
    if key == "close":
        return {"price", currency}
    if key == "company_basis":
        return {currency, f"{currency}/share"}
    if key in PER_SHARE_KEYS and path.startswith("valuation."):
        return {currency, f"{currency}/share"}
    if key in {"shares_outstanding", "diluted_shares"}:
        return {"shares"}
    if key == "discount_factor":
        return {"factor"}
    if key in MULTIPLE_KEYS:
        return {None, "multiple"}
    return None


def _unit_is_valid(root: dict, path: str, point: dict) -> bool:
    accepted = _accepted_units(root, path)
    return accepted is None or point.get("unit") in accepted


def _number_values(text: Any) -> list[float]:
    if not isinstance(text, str):
        return []
    values = []
    for match in NUMBER_RE.finditer(text):
        try:
            value = float(match.group("number").replace(",", ""))
        except ValueError:
            continue
        suffix = (match.group("suffix") or "").lower()
        if suffix in SUFFIX_SCALE:
            value *= SUFFIX_SCALE[suffix]
        values.append(value)
    return values


def _supported_number_values(nodes: list[dict]) -> list[float]:
    values: list[float] = []
    for node in nodes:
        if "value" in node and isinstance(node.get("value"), (int, float)):
            raw = float(node["value"])
            values.append(raw)
            if node.get("unit") == "ratio":
                values.append(raw * 100)
        values.extend(_number_values(node.get("display_value")))
        values.extend(_number_values(node.get("claim")))
        as_of = str(node.get("as_of_date") or "")
        if len(as_of) >= 4 and as_of[:4].isdigit():
            values.append(float(as_of[:4]))
    return values


def _number_matches(value: float, allowed: list[float]) -> bool:
    return any(
        math.isclose(
            value,
            candidate,
            rel_tol=1e-4,
            abs_tol=max(1e-7, abs(candidate) * 1e-6),
        )
        for candidate in allowed
    )


def _unsupported_numbers(text: str, cited_nodes: list[dict]) -> list[float]:
    observed = _number_values(text)
    allowed = _supported_number_values(cited_nodes)
    return [value for value in observed if not _number_matches(value, allowed)]


def _is_generated(node: dict) -> bool:
    return bool(node.get("generated")) or str(node.get("provider", "")).casefold() in AI_PROVIDERS


def _is_supporting_node(node: Any) -> bool:
    return (
        _is_provenance(node)
        and ("claim" in node or "value" in node)
        and not ("claim" in node and _is_generated(node))
    )


def _citation_allowed(conclusion_path: str, citation_path: str) -> bool:
    if conclusion_path == "analysis.neutral_evidence.narrative":
        return citation_path.startswith(
            (
                "analysis.neutral_evidence.risks.",
                "analysis.neutral_evidence.opportunities.",
                "analysis.neutral_evidence.facts.",
            )
        )
    if conclusion_path == "news.ai_summary":
        return citation_path.startswith("news.items.")
    section = _section(conclusion_path)
    return citation_path.startswith(f"{section}.") and citation_path != conclusion_path


def _materially_different(values: list[float]) -> bool:
    low, high = min(values), max(values)
    return not math.isclose(low, high, rel_tol=0.005, abs_tol=1e-9)


def _canonical_facts(root: dict) -> dict[str, list[tuple[str, dict]]]:
    facts: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    overview = root.get("overview") or {}
    for key, value in overview.items():
        if _is_provenance(value) and "value" in value:
            facts[key].append((f"overview.{key}", value))

    inputs = ((root.get("valuation") or {}).get("inputs") or {})
    for key, value in inputs.items():
        if _is_provenance(value) and "value" in value:
            facts[key].append((f"valuation.inputs.{key}", value))

    neutral = ((root.get("analysis") or {}).get("neutral_evidence") or {})
    for collection in ("risks", "opportunities"):
        for insight_index, insight in enumerate(neutral.get(collection) or []):
            for evidence_index, item in enumerate(insight.get("evidence") or []):
                key = item.get("metric_key")
                value = item.get("value")
                if key and _is_provenance(value) and "value" in value:
                    facts[str(key)].append(
                        (
                            f"analysis.neutral_evidence.{collection}.{insight_index}."
                            f"evidence.{evidence_index}.value",
                            value,
                        )
                    )
    benchmark_metrics = (neutral.get("benchmarks") or {}).get("metrics") or []
    for metric_index, metric in enumerate(benchmark_metrics):
        key = metric.get("metric_key")
        value = metric.get("company_value")
        if key and _is_provenance(value) and "value" in value:
            facts[str(key)].append(
                (
                    f"analysis.neutral_evidence.benchmarks.metrics.{metric_index}.company_value",
                    value,
                )
            )
    return facts


def _issue(
    code: AuditIssueCode,
    severity: AuditSeverity,
    path: str,
    message: str,
    *,
    claim: str | None = None,
    related_paths: list[str] | None = None,
) -> dict:
    return {
        "code": code,
        "severity": severity,
        "section": _section(path),
        "path": path,
        "message": message,
        "claim": claim,
        "related_paths": related_paths or [],
    }


def _audit_document(document: BaseModel) -> tuple[BaseModel, EvidenceAudit]:
    payload = document.model_dump(mode="python")
    payload.pop("audit", None)
    sanitized = deepcopy(payload)
    issues: list[dict] = []
    invalid_unit_paths: set[str] = set()
    inconsistent_paths: set[str] = set()
    evidence_count = 0
    point_count = 0

    nodes = list(_walk(payload))
    for kind, path, node in nodes:
        if kind == "evidence":
            evidence_count += 1
        elif kind == "data_point":
            point_count += 1
        if _enum_value(node.get("freshness_status")) == "stale":
            issues.append(
                _issue(
                    AuditIssueCode.STALE_EVIDENCE,
                    AuditSeverity.WARNING,
                    path,
                    "Evidence is explicitly marked stale and should not be presented as current.",
                    claim=node.get("claim"),
                )
            )
        if kind == "data_point" and not _unit_is_valid(payload, path, node):
            invalid_unit_paths.add(path)
            issues.append(
                _issue(
                    AuditIssueCode.INCORRECT_UNIT,
                    AuditSeverity.WARNING,
                    path,
                    f"Unit {node.get('unit')!r} is incompatible with this metric.",
                )
            )

    for metric_key, records in _canonical_facts(payload).items():
        numeric = [
            (path, node)
            for path, node in records
            if isinstance(node.get("value"), (int, float))
        ]
        same_date_groups: dict[str, list[tuple[str, dict]]] = defaultdict(list)
        for path, node in numeric:
            same_date_groups[str(node.get("as_of_date"))].append((path, node))
        for dated_records in same_date_groups.values():
            values = [float(node["value"]) for _, node in dated_records]
            if len(values) < 2 or not _materially_different(values):
                continue
            paths = [path for path, _ in dated_records]
            inconsistent_paths.update(paths)
            issues.append(
                _issue(
                    AuditIssueCode.INCONSISTENT_NUMBER,
                    AuditSeverity.WARNING,
                    paths[0],
                    f"The report contains materially different values for {metric_key} on the same date.",
                    related_paths=paths[1:],
                )
            )
            sources = {
                (str(node.get("provider")), str(node.get("source")))
                for _, node in dated_records
            }
            if len(sources) > 1:
                issues.append(
                    _issue(
                        AuditIssueCode.CONFLICTING_SOURCES,
                        AuditSeverity.WARNING,
                        paths[0],
                        f"Different sources disagree on {metric_key}.",
                        related_paths=paths[1:],
                    )
                )

    blocked_paths: list[str] = []
    blocked_statements = 0
    generated_nodes = [
        (path, node)
        for kind, path, node in nodes
        if kind == "evidence" and _is_generated(node)
    ]
    for path, node in generated_nodes:
        statements = node.get("statements") or []
        if not statements:
            statements = [{"text": str(node.get("claim") or ""), "citations": []}]
        supported_statements = []
        for index, statement in enumerate(statements):
            statement_path = f"{path}.statements.{index}"
            text = " ".join(str(statement.get("text") or "").split())
            citations = statement.get("citations") or []
            cited_nodes = [_resolve(payload, citation) for citation in citations]
            valid_nodes = [
                item
                for citation, item in zip(citations, cited_nodes)
                if _is_supporting_node(item) and _citation_allowed(path, citation)
            ]
            should_block = False
            if not citations:
                should_block = True
                issues.append(
                    _issue(
                        AuditIssueCode.MISSING_CITATION,
                        AuditSeverity.BLOCKING,
                        statement_path,
                        "Generated factual statement has no citation.",
                        claim=text,
                    )
                )
            invalid_citations = [
                citation
                for citation, resolved in zip(citations, cited_nodes)
                if not _is_supporting_node(resolved)
                or not _citation_allowed(path, citation)
            ]
            if invalid_citations:
                should_block = True
                issues.append(
                    _issue(
                        AuditIssueCode.UNSUPPORTED_CLAIM,
                        AuditSeverity.BLOCKING,
                        statement_path,
                        "Generated statement cites evidence that is absent from the report.",
                        claim=text,
                        related_paths=invalid_citations,
                    )
                )
            bad_support = [
                citation
                for citation in citations
                if citation in invalid_unit_paths or citation in inconsistent_paths
            ]
            if bad_support:
                should_block = True
                issues.append(
                    _issue(
                        AuditIssueCode.UNSUPPORTED_CLAIM,
                        AuditSeverity.BLOCKING,
                        statement_path,
                        "Generated statement relies on invalid or internally inconsistent evidence.",
                        claim=text,
                        related_paths=bad_support,
                    )
                )
            mismatched = _unsupported_numbers(text, valid_nodes) if valid_nodes else []
            if mismatched:
                should_block = True
                issues.append(
                    _issue(
                        AuditIssueCode.INCONSISTENT_NUMBER,
                        AuditSeverity.BLOCKING,
                        statement_path,
                        "Generated statement contains numbers not found in its cited evidence.",
                        claim=text,
                        related_paths=citations,
                    )
                )
            if citations and not invalid_citations and not bad_support and not valid_nodes:
                should_block = True
            if should_block:
                blocked_paths.append(statement_path)
                blocked_statements += 1
                if not any(
                    issue["code"] == AuditIssueCode.UNSUPPORTED_CLAIM
                    and issue["path"] == statement_path
                    for issue in issues
                ):
                    issues.append(
                        _issue(
                            AuditIssueCode.UNSUPPORTED_CLAIM,
                            AuditSeverity.BLOCKING,
                            statement_path,
                            "Generated statement could not be supported by the cited report evidence.",
                            claim=text,
                            related_paths=citations,
                        )
                    )
                continue
            supported_statements.append({"text": text, "citations": citations})

        if supported_statements:
            replacement = deepcopy(node)
            replacement["statements"] = supported_statements
            replacement["claim"] = " ".join(item["text"] for item in supported_statements)
            replacement["citations"] = list(
                dict.fromkeys(
                    citation
                    for statement in supported_statements
                    for citation in statement["citations"]
                )
            )
            _set_path(sanitized, path, replacement)
        else:
            _set_path(sanitized, path, None)

    counts = Counter(issue["code"] for issue in issues)
    status = (
        AuditStatus.BLOCKED
        if blocked_statements
        else AuditStatus.WARNING
        if issues
        else AuditStatus.PASSED
    )
    audit = EvidenceAudit.model_validate(
        {
            "status": status,
            "audited_at": _utc_now(),
            "checks_performed": CHECKS,
            "issues": issues,
            "issue_counts": dict(counts),
            "blocked_paths": blocked_paths,
            "blocked_statements": blocked_statements,
            "evidence_checked": evidence_count,
            "data_points_checked": point_count,
            "factual_conclusions_allowed": blocked_statements == 0,
        }
    )
    return document.__class__.model_validate(sanitized), audit


def audit_research_report(report: ResearchReportDraft) -> ResearchReportAuditResponse:
    sanitized, audit = _audit_document(report)
    return ResearchReportAuditResponse(report=sanitized, audit=audit)


def audit_snapshot(snapshot: ResearchSnapshot) -> ResearchSnapshot:
    sanitized, audit = _audit_document(snapshot)
    return sanitized.model_copy(update={"audit": audit})
