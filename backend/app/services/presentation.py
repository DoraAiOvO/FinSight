"""Deterministic interpretation derived from profiles and investment policies.

This module never changes, removes, or invents evidence. It only sorts existing
insights and describes how the frontend should organize and expand the report.
"""

from collections import defaultdict

from ..models.schemas import (
    ExplanationDepth,
    PersonalizedInterpretation,
    PolicyRuleResult,
    ReportDepth,
    ReportPresentation,
    ReportSection,
)
from .provenance import data_value


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


POLICY_METRIC_KEYS = {
    "minimum_revenue_growth": "revenue_growth",
    "maximum_revenue_growth": "revenue_growth",
    "minimum_profit_margin": "profit_margin",
    "maximum_profit_margin": "profit_margin",
    "minimum_free_cash_flow_margin": "free_cash_flow_margin",
    "maximum_debt_to_equity": "debt_to_equity",
    "minimum_current_ratio": "current_ratio",
    "maximum_forward_pe": "forward_pe",
    "maximum_trailing_pe": "trailing_pe",
    "maximum_price_to_sales": "price_to_sales",
    "valuation_threshold": "trailing_pe",
    "preferred_sector": "sector",
    "country": "country",
    "excluded_asset_type": "asset_type",
}


def _policy_version(policy):
    if policy is None:
        return None
    versions = [
        version
        for version in policy.versions
        if _value(version, "status") == "published"
    ]
    return max(versions, key=lambda version: version.version_number, default=None)


def _observed_policy_value(metrics: dict, rule) -> object:
    rule_type = _value(rule, "rule_type", "")
    metric_key = POLICY_METRIC_KEYS.get(rule_type, rule_type)
    return data_value(metrics.get(metric_key))


def _matches_policy_rule(observed, rule) -> bool | None:
    if observed is None:
        return None
    expected = _value(rule, "value")
    operator = str(_value(rule, "operator", "equals")).casefold()
    try:
        if operator in {"equals", "equal", "=="}:
            matched = (
                observed in expected
                if isinstance(expected, list)
                else observed == expected
            )
        elif operator in {"not_equals", "not_equal", "!="}:
            matched = (
                observed not in expected
                if isinstance(expected, list)
                else observed != expected
            )
        elif operator in {"greater_than", ">"}:
            matched = observed > expected
        elif operator in {"greater_than_or_equal", ">="}:
            matched = observed >= expected
        elif operator in {"less_than", "<"}:
            matched = observed < expected
        elif operator in {"less_than_or_equal", "<="}:
            matched = observed <= expected
        elif operator == "in":
            matched = observed in expected
        elif operator == "not_in":
            matched = observed not in expected
        elif operator == "contains":
            matched = expected in observed
        else:
            return None
    except (TypeError, ValueError):
        return None
    if str(_value(rule, "rule_type", "")).startswith("excluded_"):
        matched = not matched
    return matched


def _rule_result(rule, observed, matched) -> PolicyRuleResult:
    return PolicyRuleResult(
        rule_type=_value(rule, "rule_type"),
        observed=observed,
        preference=_value(rule, "value"),
        matched=matched,
        importance=int(_value(rule, "importance", 3)),
        rationale=_value(rule, "rationale", "Policy preference"),
    )


def build_personalized_interpretation(
    metrics: dict,
    neutral_insights: list[dict],
    organized_insights: list[dict],
    presentation: ReportPresentation,
    policy=None,
) -> PersonalizedInterpretation:
    """Interpret immutable evidence through profile and policy preferences."""
    version = _policy_version(policy)
    matched_preferences = []
    failed_preferences = []
    hard_constraint_results = []
    alert_relevance = []
    policy_emphasis = []
    weighted_matches = 0
    evaluated_weight = 0

    if version is not None:
        for collection in (
            "principles",
            "market_scopes",
            "sector_preferences",
            "theme_preferences",
            "metric_rules",
            "constraints",
            "valuation_rules",
            "portfolio_rules",
            "alert_rules",
        ):
            for rule in getattr(version, collection):
                if not _value(rule, "enabled", True):
                    continue
                observed = _observed_policy_value(metrics, rule)
                matched = _matches_policy_rule(observed, rule)
                result = _rule_result(rule, observed, matched)
                strength = _value(rule, "hard_or_soft", "soft")
                effect = _value(rule, "application_effect", "preference_fit_scoring")
                if strength == "hard":
                    hard_constraint_results.append(result)
                elif matched is True:
                    matched_preferences.append(result)
                elif matched is False:
                    failed_preferences.append(result)
                if matched is not None:
                    weight = int(_value(rule, "importance", 3))
                    evaluated_weight += weight
                    if matched:
                        weighted_matches += weight
                if effect == "report_emphasis" and matched is not False:
                    policy_emphasis.append(_value(rule, "rule_type"))
                if effect == "alerts" and matched is True:
                    alert_relevance.append(_value(rule, "rule_type"))

    if version is not None and not presentation.personalized:
        presentation = presentation.model_copy(update={"personalized": True})

    neutral_index = {item["code"]: index for index, item in enumerate(neutral_insights)}
    ranking = []
    for rank, insight in enumerate(organized_insights, start=1):
        reasons = []
        if insight.get("highlighted"):
            reasons.append("Matched research profile priorities or horizon.")
        if neutral_index.get(insight["code"]) != rank - 1:
            reasons.append("Moved forward by the personalized research lens.")
        if not reasons:
            reasons.append("Preserved the neutral evidence order.")
        ranking.append(
            {"insight_code": insight["code"], "rank": rank, "reasons": reasons}
        )

    report_emphasis = list(
        dict.fromkeys(
            [*presentation.highlighted_insight_codes, *policy_emphasis]
        )
    )
    return PersonalizedInterpretation(
        policy_fit=(
            round(weighted_matches / evaluated_weight, 4)
            if evaluated_weight
            else None
        ),
        matched_preferences=matched_preferences,
        failed_preferences=failed_preferences,
        hard_constraint_results=hard_constraint_results,
        ranking_explanation=ranking,
        report_emphasis=report_emphasis,
        alert_relevance=list(dict.fromkeys(alert_relevance)),
        presentation=presentation,
    )
