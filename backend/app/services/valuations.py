"""Deterministic valuation models; no financial arithmetic is delegated to an LLM."""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..models.schemas import ValuationAssumptions
from .provenance import (
    data_point,
    data_value,
    evidence,
    inherited_provenance,
    provenance,
    utc_now,
)


DISCLAIMER = (
    "Valuation outputs are educational scenario estimates, not price targets or "
    "investment advice. Small assumption changes can materially change the result."
)
DEFAULT_DISCOUNT_RATE = 0.10
DEFAULT_TERMINAL_GROWTH = 0.025
DEFAULT_SHARE_DILUTION = 0.0
DEFAULT_REVENUE_GROWTH = 0.05
REVERSE_GROWTH_BOUNDS = (-0.50, 1.00)


class ValuationError(ValueError):
    """Base exception for deterministic valuation failures."""


class ValuationDataUnavailableError(ValuationError):
    """Raised when a sourced input required by the model is unavailable."""


@dataclass(frozen=True)
class NumericInputs:
    total_revenue: float
    free_cash_flow: float
    total_cash: float
    total_debt: float
    shares_outstanding: float
    current_price: float


def _finite(point, field: str) -> float:
    value = data_value(point)
    if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValuationDataUnavailableError(f"{field} is unavailable")
    return float(value)


def _numeric_inputs(inputs: dict) -> NumericInputs:
    values = NumericInputs(
        total_revenue=_finite(inputs.get("total_revenue"), "Total revenue"),
        free_cash_flow=_finite(inputs.get("free_cash_flow"), "Free cash flow"),
        total_cash=_finite(inputs.get("total_cash"), "Total cash"),
        total_debt=_finite(inputs.get("total_debt"), "Total debt"),
        shares_outstanding=_finite(
            inputs.get("shares_outstanding"), "Shares outstanding"
        ),
        current_price=_finite(inputs.get("current_price"), "Current price"),
    )
    if values.total_revenue <= 0:
        raise ValuationDataUnavailableError("Total revenue must be positive")
    if values.shares_outstanding <= 0:
        raise ValuationDataUnavailableError("Shares outstanding must be positive")
    if values.current_price <= 0:
        raise ValuationDataUnavailableError("Current price must be positive")
    if values.total_cash < 0 or values.total_debt < 0:
        raise ValuationDataUnavailableError("Cash and debt cannot be negative")
    return values


def _clamp(value: float, lower: float, upper: float) -> float:
    return min(upper, max(lower, value))


def _format_number(value: float, unit: str | None) -> str:
    if unit == "ratio":
        return f"{value * 100:.1f}%"
    if unit == "multiple":
        return f"{value:.2f}x"
    if unit == "shares":
        if abs(value) >= 1_000_000_000:
            return f"{value / 1_000_000_000:.2f}B"
        if abs(value) >= 1_000_000:
            return f"{value / 1_000_000:.2f}M"
        return f"{value:,.0f}"
    if unit and unit not in {"factor"}:
        absolute = abs(value)
        if absolute >= 1_000_000_000:
            return f"{unit} {value / 1_000_000_000:.2f}B"
        if absolute >= 1_000_000:
            return f"{unit} {value / 1_000_000:.2f}M"
        return f"{unit} {value:,.2f}"
    return f"{value:.4f}" if unit == "factor" else f"{value:,.2f}"


def _derived_point(
    value: float,
    inputs: list[dict],
    *,
    source: str,
    unit: str | None = None,
    confidence: float = 0.8,
) -> dict:
    return data_point(
        value,
        unit=unit,
        display_value=_format_number(value, unit),
        **inherited_provenance(
            inputs,
            source=source,
            confidence=confidence,
        ),
    )


def _policy_point(value: float, *, source: str, unit: str = "ratio") -> dict:
    now = utc_now()
    return data_point(
        value,
        unit=unit,
        display_value=_format_number(value, unit),
        **provenance(
            provider="FinSight",
            source=source,
            as_of_date=now.date(),
            fetched_at=now,
            freshness_status="unknown",
            confidence=1.0,
        ),
    )


def _user_point(value: float, field: str) -> dict:
    now = utc_now()
    return data_point(
        value,
        unit="ratio",
        display_value=_format_number(value, "ratio"),
        **provenance(
            provider="User",
            source=f"user-provided valuation assumption: {field}",
            as_of_date=now.date(),
            fetched_at=now,
            freshness_status="fresh",
            confidence=1.0,
        ),
    )


def _default_assumptions(inputs: dict) -> ValuationAssumptions:
    growth_point = inputs.get("revenue_growth")
    growth = data_value(growth_point)
    if not isinstance(growth, (int, float)) or not math.isfinite(float(growth)):
        growth = DEFAULT_REVENUE_GROWTH
    margin = _finite(inputs.get("free_cash_flow_margin"), "Free cash flow margin")
    return ValuationAssumptions(
        projection_years=5,
        revenue_growth=_clamp(float(growth), -0.20, 0.30),
        free_cash_flow_margin=_clamp(margin, -0.30, 0.50),
        discount_rate=DEFAULT_DISCOUNT_RATE,
        terminal_growth=DEFAULT_TERMINAL_GROWTH,
        annual_share_dilution=DEFAULT_SHARE_DILUTION,
    )


def _assumption_points(
    assumptions: ValuationAssumptions,
    inputs: dict,
    *,
    user_provided: bool,
) -> dict:
    if user_provided:
        points = {
            field: _user_point(getattr(assumptions, field), field)
            for field in (
                "revenue_growth",
                "free_cash_flow_margin",
                "discount_rate",
                "terminal_growth",
                "annual_share_dilution",
            )
        }
    else:
        growth_source = inputs.get("revenue_growth")
        margin_source = inputs.get("free_cash_flow_margin")
        points = {
            "revenue_growth": (
                _derived_point(
                    assumptions.revenue_growth,
                    [growth_source] if isinstance(growth_source, dict) else [],
                    source=(
                        "default assumption: latest revenue growth constrained to "
                        "the -20% to 30% model range"
                    ),
                    unit="ratio",
                )
                if isinstance(growth_source, dict)
                else _policy_point(
                    assumptions.revenue_growth,
                    source="default assumption policy v1: 5% revenue growth when unavailable",
                )
            ),
            "free_cash_flow_margin": _derived_point(
                assumptions.free_cash_flow_margin,
                [margin_source],
                source=(
                    "default assumption: latest free-cash-flow margin constrained "
                    "to the -30% to 50% model range"
                ),
                unit="ratio",
            ),
            "discount_rate": _policy_point(
                assumptions.discount_rate,
                source="default assumption policy v1: 10% discount rate",
            ),
            "terminal_growth": _policy_point(
                assumptions.terminal_growth,
                source="default assumption policy v1: 2.5% terminal growth",
            ),
            "annual_share_dilution": _policy_point(
                assumptions.annual_share_dilution,
                source="default assumption policy v1: 0% annual share dilution",
            ),
        }
    return {"projection_years": assumptions.projection_years, **points}


def _raw_dcf(facts: NumericInputs, assumptions: ValuationAssumptions) -> dict:
    if assumptions.discount_rate <= assumptions.terminal_growth:
        raise ValuationError("Discount rate must exceed terminal growth")
    revenue = facts.total_revenue
    shares = facts.shares_outstanding
    projections = []
    for year in range(1, assumptions.projection_years + 1):
        revenue *= 1 + assumptions.revenue_growth
        free_cash_flow = revenue * assumptions.free_cash_flow_margin
        shares *= 1 + assumptions.annual_share_dilution
        discount_factor = 1 / ((1 + assumptions.discount_rate) ** year)
        projections.append(
            {
                "year": year,
                "revenue": revenue,
                "free_cash_flow": free_cash_flow,
                "shares": shares,
                "discount_factor": discount_factor,
                "present_value": free_cash_flow * discount_factor,
            }
        )
    final_free_cash_flow = projections[-1]["free_cash_flow"]
    terminal_value = (
        final_free_cash_flow
        * (1 + assumptions.terminal_growth)
        / (assumptions.discount_rate - assumptions.terminal_growth)
    )
    present_value_explicit = sum(item["present_value"] for item in projections)
    present_value_terminal = terminal_value * projections[-1]["discount_factor"]
    enterprise_value = present_value_explicit + present_value_terminal
    equity_value = enterprise_value + facts.total_cash - facts.total_debt
    intrinsic_value = equity_value / projections[-1]["shares"]
    return {
        "projections": projections,
        "present_value_explicit": present_value_explicit,
        "terminal_value": terminal_value,
        "present_value_terminal": present_value_terminal,
        "enterprise_value": enterprise_value,
        "equity_value": equity_value,
        "intrinsic_value": intrinsic_value,
        "upside_downside": intrinsic_value / facts.current_price - 1,
    }


def _present_dcf(
    raw: dict,
    facts: NumericInputs,
    inputs: dict,
    assumptions: ValuationAssumptions,
    assumption_points: dict,
    currency: str,
    *,
    source_prefix: str = "deterministic DCF v1",
) -> dict:
    base_points = [
        inputs[field]
        for field in (
            "total_revenue",
            "free_cash_flow",
            "total_cash",
            "total_debt",
            "shares_outstanding",
            "current_price",
        )
    ]
    assumption_inputs = [
        assumption_points[field]
        for field in (
            "revenue_growth",
            "free_cash_flow_margin",
            "discount_rate",
            "terminal_growth",
            "annual_share_dilution",
        )
    ]
    all_inputs = [*base_points, *assumption_inputs]
    projections = []
    for item in raw["projections"]:
        year = item["year"]
        projections.append(
            {
                "year": year,
                "projected_revenue": _derived_point(
                    item["revenue"],
                    all_inputs,
                    source=f"{source_prefix}: projected revenue year {year}",
                    unit=currency,
                ),
                "projected_free_cash_flow": _derived_point(
                    item["free_cash_flow"],
                    all_inputs,
                    source=f"{source_prefix}: projected free cash flow year {year}",
                    unit=currency,
                ),
                "diluted_shares": _derived_point(
                    item["shares"],
                    all_inputs,
                    source=f"{source_prefix}: diluted shares year {year}",
                    unit="shares",
                ),
                "discount_factor": _derived_point(
                    item["discount_factor"],
                    all_inputs,
                    source=f"{source_prefix}: discount factor year {year}",
                    unit="factor",
                ),
                "present_value": _derived_point(
                    item["present_value"],
                    all_inputs,
                    source=f"{source_prefix}: present value year {year}",
                    unit=currency,
                ),
            }
        )
    per_share_unit = f"{currency}/share"
    return {
        "assumptions": assumption_points,
        "projections": projections,
        "present_value_explicit_cash_flows": _derived_point(
            raw["present_value_explicit"],
            all_inputs,
            source=f"{source_prefix}: sum of discounted explicit cash flows",
            unit=currency,
        ),
        "terminal_value": _derived_point(
            raw["terminal_value"],
            all_inputs,
            source=f"{source_prefix}: Gordon growth terminal value",
            unit=currency,
        ),
        "present_value_terminal_value": _derived_point(
            raw["present_value_terminal"],
            all_inputs,
            source=f"{source_prefix}: discounted terminal value",
            unit=currency,
        ),
        "enterprise_value": _derived_point(
            raw["enterprise_value"],
            all_inputs,
            source=f"{source_prefix}: enterprise value",
            unit=currency,
        ),
        "equity_value": _derived_point(
            raw["equity_value"],
            all_inputs,
            source=f"{source_prefix}: enterprise value plus cash minus debt",
            unit=currency,
        ),
        "intrinsic_value_per_share": _derived_point(
            raw["intrinsic_value"],
            all_inputs,
            source=f"{source_prefix}: equity value divided by diluted shares",
            unit=per_share_unit,
        ),
        "current_price": inputs["current_price"],
        "upside_downside": _derived_point(
            raw["upside_downside"],
            all_inputs,
            source=f"{source_prefix}: intrinsic value divided by current price minus one",
            unit="ratio",
        ),
    }


def _scenario_assumptions(base: ValuationAssumptions, scenario: str) -> ValuationAssumptions:
    if scenario == "base":
        return base
    direction = -1 if scenario == "conservative" else 1
    discount = base.discount_rate - direction * 0.015
    terminal = base.terminal_growth + direction * 0.005
    discount = _clamp(discount, 0.02, 0.50)
    terminal = _clamp(terminal, -0.05, 0.10)
    if discount <= terminal:
        discount = min(0.50, terminal + 0.005)
    return ValuationAssumptions(
        projection_years=base.projection_years,
        revenue_growth=_clamp(base.revenue_growth + direction * 0.03, -0.50, 1.00),
        free_cash_flow_margin=_clamp(
            base.free_cash_flow_margin + direction * 0.02, -0.50, 0.80
        ),
        discount_rate=discount,
        terminal_growth=terminal,
        annual_share_dilution=_clamp(
            base.annual_share_dilution - direction * 0.005, -0.10, 0.25
        ),
    )


def _scenario_points(
    scenario: str,
    assumptions: ValuationAssumptions,
    base_points: dict,
) -> dict:
    points = {"projection_years": assumptions.projection_years}
    for field in (
        "revenue_growth",
        "free_cash_flow_margin",
        "discount_rate",
        "terminal_growth",
        "annual_share_dilution",
    ):
        value = getattr(assumptions, field)
        if scenario == "base":
            points[field] = base_points[field]
        else:
            points[field] = _derived_point(
                value,
                [base_points[field]],
                source=f"deterministic {scenario} scenario offset policy v1: {field}",
                unit="ratio",
                confidence=0.75,
            )
    return points


def _reverse_dcf(
    facts: NumericInputs,
    inputs: dict,
    assumptions: ValuationAssumptions,
    assumption_points: dict,
) -> dict:
    lower, upper = REVERSE_GROWTH_BOUNDS
    shared_inputs = [
        inputs[field]
        for field in (
            "total_revenue",
            "total_cash",
            "total_debt",
            "shares_outstanding",
            "current_price",
        )
    ] + [
        assumption_points[field]
        for field in (
            "free_cash_flow_margin",
            "discount_rate",
            "terminal_growth",
            "annual_share_dilution",
        )
    ]
    lower_point = _derived_point(
        lower,
        shared_inputs,
        source="reverse DCF v1: lower revenue-growth search bound",
        unit="ratio",
    )
    upper_point = _derived_point(
        upper,
        shared_inputs,
        source="reverse DCF v1: upper revenue-growth search bound",
        unit="ratio",
    )
    implied = None
    converged = False
    explanation_text = (
        "Reverse DCF could not solve an implied growth rate because the base free-cash-flow "
        "margin is not positive."
    )
    if assumptions.free_cash_flow_margin > 0:
        def price_for(growth: float) -> float:
            candidate = assumptions.model_copy(update={"revenue_growth": growth})
            return _raw_dcf(facts, candidate)["intrinsic_value"]

        low_price = price_for(lower)
        high_price = price_for(upper)
        target = facts.current_price
        if low_price <= target <= high_price:
            low, high = lower, upper
            for _ in range(120):
                midpoint = (low + high) / 2
                midpoint_price = price_for(midpoint)
                if abs(midpoint_price - target) <= max(1e-8, target * 1e-9):
                    low = high = midpoint
                    converged = True
                    break
                if midpoint_price < target:
                    low = midpoint
                else:
                    high = midpoint
            implied_value = (low + high) / 2
            converged = converged or abs(price_for(implied_value) - target) <= max(
                1e-7, target * 1e-8
            )
            if converged:
                implied = _derived_point(
                    implied_value,
                    shared_inputs,
                    source=(
                        "reverse DCF v1: bisection solution matching deterministic DCF "
                        "value to current price"
                    ),
                    unit="ratio",
                    confidence=0.75,
                )
                explanation_text = (
                    "The implied annual revenue growth is the bisection solution that makes "
                    "the deterministic DCF equal the sourced current share price while all "
                    "other base assumptions remain fixed."
                )
        else:
            explanation_text = (
                "The current price falls outside the DCF values produced by the transparent "
                "-50% to 100% annual revenue-growth search range."
            )
    return {
        "target_price": inputs["current_price"],
        "implied_revenue_growth": implied,
        "search_lower_bound": lower_point,
        "search_upper_bound": upper_point,
        "converged": converged,
        "explanation": evidence(
            explanation_text,
            **inherited_provenance(
                shared_inputs,
                source="reverse DCF v1 methodology explanation",
                confidence=0.75,
            ),
        ),
    }


def _peer_reference(benchmark_context: dict, metric_key: str) -> dict | None:
    metric = next(
        (
            item
            for item in benchmark_context.get("metrics", [])
            if item.get("metric_key") == metric_key
        ),
        None,
    )
    if not metric:
        return None
    return next(
        (
            reference
            for reference in metric.get("references", [])
            if reference.get("scope") == "peers"
        ),
        None,
    )


def _peer_multiples(
    facts: NumericInputs,
    inputs: dict,
    benchmark_context: dict,
    currency: str,
) -> list[dict]:
    estimates = []
    per_share_unit = f"{currency}/share"
    specifications = (
        ("trailing_pe", "trailing_eps", "trailing earnings per share"),
        ("price_to_sales", "revenue_per_share", "revenue per share"),
    )
    for metric_key, basis_key, basis_label in specifications:
        reference = _peer_reference(benchmark_context, metric_key)
        multiple = data_value(reference.get("median")) if reference else None
        if not isinstance(multiple, (int, float)) or not math.isfinite(float(multiple)):
            continue
        if basis_key == "trailing_eps":
            basis = inputs.get("trailing_eps")
            basis_value = data_value(basis)
            if not isinstance(basis_value, (int, float)) or basis_value <= 0:
                continue
        else:
            basis_value = facts.total_revenue / facts.shares_outstanding
            basis = _derived_point(
                basis_value,
                [inputs["total_revenue"], inputs["shares_outstanding"]],
                source="peer multiple v1: total revenue divided by shares outstanding",
                unit=per_share_unit,
            )
        implied_value = float(multiple) * float(basis_value)
        calculation_inputs = [reference["median"], basis]
        estimates.append(
            {
                "method": metric_key,
                "peer_median_multiple": reference["median"],
                "company_basis": basis,
                "implied_value_per_share": _derived_point(
                    implied_value,
                    calculation_inputs,
                    source=(
                        f"peer multiple v1: selected-peer median {metric_key} "
                        f"multiplied by company {basis_label}"
                    ),
                    unit=per_share_unit,
                    confidence=0.7,
                ),
                "sample_size": reference["sample_size"],
                "peer_tickers": reference.get("sample_tickers", []),
                "explanation": evidence(
                    f"Applies the median {metric_key} from {reference['sample_size']} "
                    f"automatically selected peers to the company's sourced {basis_label}.",
                    **inherited_provenance(
                        calculation_inputs,
                        source=f"peer multiple v1 methodology: {metric_key}",
                        confidence=0.7,
                    ),
                ),
            }
        )
    return estimates


def _sensitivity(
    facts: NumericInputs,
    inputs: dict,
    assumptions: ValuationAssumptions,
    assumption_points: dict,
    currency: str,
) -> dict:
    discount_rates = [
        round(_clamp(assumptions.discount_rate + offset, 0.02, 0.50), 6)
        for offset in (-0.02, -0.01, 0, 0.01, 0.02)
    ]
    terminal_rates = [
        round(_clamp(assumptions.terminal_growth + offset, -0.05, 0.10), 6)
        for offset in (-0.01, -0.005, 0, 0.005, 0.01)
    ]
    discount_rates = list(dict.fromkeys(discount_rates))
    terminal_rates = list(dict.fromkeys(terminal_rates))
    base_inputs = [
        inputs[field]
        for field in (
            "total_revenue",
            "total_cash",
            "total_debt",
            "shares_outstanding",
        )
    ]
    terminal_points = [
        _derived_point(
            rate,
            [assumption_points["terminal_growth"]],
            source="DCF sensitivity v1: terminal-growth grid value",
            unit="ratio",
        )
        for rate in terminal_rates
    ]
    rows = []
    for discount_rate in discount_rates:
        discount_point = _derived_point(
            discount_rate,
            [assumption_points["discount_rate"]],
            source="DCF sensitivity v1: discount-rate grid value",
            unit="ratio",
        )
        cells = []
        for terminal_rate, terminal_point in zip(terminal_rates, terminal_points):
            intrinsic = None
            if discount_rate > terminal_rate:
                candidate = assumptions.model_copy(
                    update={
                        "discount_rate": discount_rate,
                        "terminal_growth": terminal_rate,
                    }
                )
                value = _raw_dcf(facts, candidate)["intrinsic_value"]
                intrinsic = _derived_point(
                    value,
                    [*base_inputs, discount_point, terminal_point],
                    source=(
                        "DCF sensitivity v1: intrinsic value using grid discount "
                        "and terminal-growth rates"
                    ),
                    unit=f"{currency}/share",
                    confidence=0.7,
                )
            cells.append(
                {
                    "terminal_growth": terminal_point,
                    "intrinsic_value_per_share": intrinsic,
                }
            )
        rows.append({"discount_rate": discount_point, "cells": cells})
    return {"terminal_growth_rates": terminal_points, "rows": rows}


def _limitation(claim: str, inputs: list[dict]) -> dict:
    return evidence(
        claim,
        **inherited_provenance(
            inputs,
            source="deterministic valuation limitation",
            confidence=0.9,
        ),
    )


def build_valuation(
    ticker: str,
    inputs: dict,
    benchmark_context: dict,
    assumptions: ValuationAssumptions | None = None,
) -> dict:
    """Build DCF, reverse DCF, peer, scenario, and sensitivity outputs in code."""
    facts = _numeric_inputs(inputs)
    currency = str(inputs.get("currency") or "").strip().upper()
    if not currency:
        raise ValuationDataUnavailableError("Currency is unavailable")
    user_provided = assumptions is not None
    selected = assumptions or _default_assumptions(inputs)
    base_points = _assumption_points(
        selected,
        inputs,
        user_provided=user_provided,
    )
    base_raw = _raw_dcf(facts, selected)
    base_dcf = _present_dcf(
        base_raw,
        facts,
        inputs,
        selected,
        base_points,
        currency,
    )

    scenarios = []
    scenario_values = {}
    for scenario in ("conservative", "base", "optimistic"):
        scenario_assumptions = _scenario_assumptions(selected, scenario)
        scenario_points = _scenario_points(
            scenario,
            scenario_assumptions,
            base_points,
        )
        scenario_raw = base_raw if scenario == "base" else _raw_dcf(
            facts, scenario_assumptions
        )
        scenario_dcf = base_dcf if scenario == "base" else _present_dcf(
            scenario_raw,
            facts,
            inputs,
            scenario_assumptions,
            scenario_points,
            currency,
            source_prefix=f"deterministic {scenario} scenario DCF v1",
        )
        scenarios.append({"scenario": scenario, "dcf": scenario_dcf})
        scenario_values[scenario] = scenario_raw["intrinsic_value"]

    range_inputs = [
        scenario["dcf"]["intrinsic_value_per_share"] for scenario in scenarios
    ]
    low_value = min(scenario_values.values())
    high_value = max(scenario_values.values())
    margin_range = {
        "low": _derived_point(
            low_value,
            range_inputs,
            source="scenario range v1: minimum scenario value",
            unit=f"{currency}/share",
        ),
        "base": base_dcf["intrinsic_value_per_share"],
        "high": _derived_point(
            high_value,
            range_inputs,
            source="scenario range v1: maximum scenario value",
            unit=f"{currency}/share",
        ),
        "current_price": inputs["current_price"],
    }
    peer_estimates = _peer_multiples(
        facts,
        inputs,
        benchmark_context,
        currency,
    )
    reverse = _reverse_dcf(facts, inputs, selected, base_points)
    limitations = [
        _limitation(
            "DCF values are scenarios driven by explicit assumptions, not forecasts or recommendations.",
            [base_dcf["intrinsic_value_per_share"]],
        ),
        _limitation(
            "The model holds the selected annual revenue growth and free-cash-flow margin constant through the explicit projection period.",
            [
                base_points["revenue_growth"],
                base_points["free_cash_flow_margin"],
            ],
        ),
    ]
    if not peer_estimates:
        limitations.append(
            _limitation(
                "Selected peers did not provide enough positive comparable multiples for a peer-value estimate.",
                [inputs["current_price"]],
            )
        )
    if not reverse["converged"]:
        limitations.append(
            _limitation(
                "Reverse DCF did not converge within the disclosed revenue-growth search range.",
                [inputs["current_price"]],
            )
        )
    methodology_inputs = [
        inputs[field]
        for field in (
            "total_revenue",
            "free_cash_flow",
            "total_cash",
            "total_debt",
            "shares_outstanding",
            "current_price",
        )
    ] + [
        base_points[field]
        for field in (
            "revenue_growth",
            "free_cash_flow_margin",
            "discount_rate",
            "terminal_growth",
            "annual_share_dilution",
        )
    ]
    methodology = evidence(
        "FinSight projects revenue and free cash flow, discounts each explicit cash flow, "
        "uses a Gordon-growth terminal value, bridges enterprise value to equity value "
        "with sourced cash and debt, and divides by code-projected diluted shares. Reverse "
        "DCF uses bisection; peer estimates use selected-peer medians. No LLM performs or "
        "supplies financial arithmetic.",
        **inherited_provenance(
            methodology_inputs,
            source="FinSight deterministic valuation methodology v1",
            confidence=0.8,
        ),
    )
    return {
        "ticker": ticker.upper(),
        "currency": currency,
        "inputs": {
            field: inputs.get(field)
            for field in (
                "total_revenue",
                "free_cash_flow",
                "total_cash",
                "total_debt",
                "shares_outstanding",
                "current_price",
                "trailing_eps",
            )
            if inputs.get(field) is not None
        },
        "base_case": base_dcf,
        "reverse_dcf": reverse,
        "peer_multiples": peer_estimates,
        "scenarios": scenarios,
        "margin_of_safety_range": margin_range,
        "sensitivity": _sensitivity(
            facts,
            inputs,
            selected,
            base_points,
            currency,
        ),
        "methodology": methodology,
        "limitations": limitations,
        "disclaimer": DISCLAIMER,
    }
