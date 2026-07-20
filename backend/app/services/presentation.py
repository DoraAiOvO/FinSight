"""Deterministic report presentation derived from customer preferences.

This module never changes, removes, or invents evidence. It only sorts existing
insights and describes how the frontend should organize and expand the report.
"""

from collections import defaultdict

from ..models.schemas import (
    ExplanationDepth,
    ReportDepth,
    ReportPresentation,
    ReportSection,
)


PRIORITY_CODES = {
    "growth": {"fast_revenue_growth", "shrinking_revenue", "high_profitability"},
    "stability": {
        "high_leverage",
        "tight_liquidity",
        "negative_free_cash_flow",
        "high_volatility",
        "unprofitable_operations",
    },
    "income": {"dividend_income", "strong_cash_generation", "negative_free_cash_flow"},
    "value": {
        "rich_valuation",
        "low_earnings_multiple",
        "strong_cash_generation",
        "near_52_week_low",
        "analyst_target_gap",
    },
    "innovation": {"fast_revenue_growth", "high_profitability", "rich_valuation"},
}

PRIORITY_METRICS = {
    "growth": {"revenue_growth", "profit_margin", "forward_pe"},
    "stability": {"debt_to_equity", "free_cash_flow", "beta"},
    "income": {"dividend_yield", "free_cash_flow", "profit_margin"},
    "value": {"trailing_pe", "price_to_sales", "free_cash_flow"},
    "innovation": {"revenue_growth", "profit_margin", "price_to_sales"},
}

HORIZON_CODES = {
    "short_term": {
        "near_52_week_high",
        "near_52_week_low",
        "high_volatility",
        "analyst_target_gap",
    },
    "one_to_three_years": {"fast_revenue_growth", "rich_valuation", "high_profitability"},
    "five_plus_years": {
        "strong_cash_generation",
        "negative_free_cash_flow",
        "high_profitability",
        "high_leverage",
        "dividend_income",
    },
}


def _value(profile, key: str, default=None):
    if profile is None:
        return default
    value = getattr(profile, key, default)
    return value.value if hasattr(value, "value") else value


def _explanation_depth(profile) -> ExplanationDepth:
    experience = _value(profile, "experience_level")
    report_depth = _value(profile, "preferred_report_depth", ReportDepth.STANDARD.value)
    if experience == "beginner" or report_depth == ReportDepth.QUICK.value:
        return ExplanationDepth.SIMPLE
    if experience == "advanced" and report_depth == ReportDepth.DEEP.value:
        return ExplanationDepth.PROFESSIONAL
    return ExplanationDepth.STANDARD


def _section_order(profile) -> list[ReportSection]:
    horizon = _value(profile, "research_horizon")
    priorities = set(_value(profile, "priorities", []))
    risk = _value(profile, "risk_comfort")

    if horizon == "short_term":
        return [
            ReportSection.OVERVIEW,
            ReportSection.PRICE_HISTORY,
            ReportSection.NEWS,
            ReportSection.ANALYSIS,
        ]
    if risk == "low" or "stability" in priorities:
        return [
            ReportSection.OVERVIEW,
            ReportSection.ANALYSIS,
            ReportSection.PRICE_HISTORY,
            ReportSection.NEWS,
        ]
    if priorities & {"growth", "innovation"}:
        return [
            ReportSection.OVERVIEW,
            ReportSection.ANALYSIS,
            ReportSection.NEWS,
            ReportSection.PRICE_HISTORY,
        ]
    return [
        ReportSection.OVERVIEW,
        ReportSection.PRICE_HISTORY,
        ReportSection.ANALYSIS,
        ReportSection.NEWS,
    ]


def _industry_match(metrics: dict, profile) -> bool:
    interests = {
        value.casefold() for value in _value(profile, "industries_of_interest", [])
    }
    company_values = {
        str(metrics.get("sector") or "").casefold(),
        str(metrics.get("industry") or "").casefold(),
    }
    return any(
        interest in company or company in interest
        for interest in interests
        for company in company_values
        if interest and company
    )


def organize_report(metrics: dict, insights: list[dict], profile=None):
    """Return every insight plus a presentation-only personalization plan."""
    if profile is None:
        untouched = [{**insight, "highlighted": False} for insight in insights]
        return untouched, ReportPresentation()

    scores: dict[str, int] = defaultdict(int)
    priorities = _value(profile, "priorities", [])
    for priority in priorities:
        for code in PRIORITY_CODES.get(priority, set()):
            scores[code] += 3

    for code in HORIZON_CODES.get(_value(profile, "research_horizon"), set()):
        scores[code] += 2

    risk = _value(profile, "risk_comfort")
    for insight in insights:
        if insight["severity"] == "high":
            scores[insight["code"]] += 1
        if risk == "low" and insight["kind"] == "risk":
            scores[insight["code"]] += 2
        if risk == "high" and insight["code"] in {"high_volatility", "rich_valuation"}:
            # High risk comfort does not suppress risk; it makes the relevant
            # volatility and valuation evidence easier to find.
            scores[insight["code"]] += 2

    indexed = list(enumerate(insights))
    indexed.sort(key=lambda item: (-scores[item[1]["code"]], item[0]))
    highlighted_codes = [
        insight["code"]
        for _, insight in indexed
        if scores[insight["code"]] > 0
    ][:3]
    highlighted = set(highlighted_codes)
    organized = [
        {**insight, "highlighted": insight["code"] in highlighted}
        for _, insight in indexed
    ]

    metric_scores: dict[str, int] = defaultdict(int)
    for priority in priorities:
        for metric in PRIORITY_METRICS.get(priority, set()):
            metric_scores[metric] += 1
    highlighted_metrics = [
        metric for metric, _ in sorted(metric_scores.items(), key=lambda item: (-item[1], item[0]))
    ][:4]

    report_depth = ReportDepth(
        _value(profile, "preferred_report_depth", ReportDepth.STANDARD.value)
    )
    presentation = ReportPresentation(
        personalized=True,
        section_order=_section_order(profile),
        explanation_depth=_explanation_depth(profile),
        report_depth=report_depth,
        highlighted_insight_codes=highlighted_codes,
        highlighted_metric_keys=highlighted_metrics,
        industry_match=_industry_match(metrics, profile),
    )
    return organized, presentation
