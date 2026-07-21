"""Evidence-based risk/opportunity analysis.

Every insight cites the concrete numbers that triggered it, so users can see
*why* FinSight flags something — not just what to think. Deterministic and
fully unit-testable; the optional AI layer only narrates on top of this.
"""

from .provenance import data_point, data_value, evidence, inherited_provenance

DISCLAIMER = (
    "FinSight explains evidence; it does not give investment advice. "
    "Data may be delayed or incomplete. Always do your own research."
)


def _pct(v: float | None) -> str:
    return "n/a" if v is None else f"{v * 100:.1f}%"


def _fmt_metric(metric_key: str, value: float) -> str:
    if metric_key in {
        "revenue_growth",
        "profit_margin",
        "operating_margin",
        "free_cash_flow_margin",
        "dividend_yield",
    }:
        return _pct(value)
    if metric_key == "debt_to_equity":
        return f"{value:.0f}%"
    return f"{value:.2f}"


def _metric_context(benchmarks: dict, metric_key: str) -> dict | None:
    return next(
        (item for item in benchmarks.get("metrics", []) if item["metric_key"] == metric_key),
        None,
    )


def _primary_reference(metric: dict | None) -> dict | None:
    if not metric or not metric.get("primary_scope"):
        return None
    return next(
        (
            reference
            for reference in metric.get("references", [])
            if reference["scope"] == metric["primary_scope"]
        ),
        None,
    )


def _relative_position(value: float, reference: dict) -> tuple[str | None, str]:
    lower = float(data_value(reference["lower_bound"]))
    upper = float(data_value(reference["upper_bound"]))
    if value > upper:
        position = "above"
        distance = value - upper
    elif value < lower:
        position = "below"
        distance = lower - value
    else:
        return None, "low"
    width = max(abs(upper - lower), abs(float(data_value(reference["median"]))) * 0.1, 1e-9)
    return position, "high" if distance > width else "medium"


def _benchmark_item(metric: dict, reference: dict) -> dict:
    scope = reference["scope"]
    median_value = reference["median"].get("display_value") or str(
        data_value(reference["median"])
    )
    lower = reference["lower_bound"].get("display_value") or str(
        data_value(reference["lower_bound"])
    )
    upper = reference["upper_bound"].get("display_value") or str(
        data_value(reference["upper_bound"])
    )
    range_label = (
        "observed range"
        if reference["range_kind"] == "observed_range"
        else "middle 50%"
    )
    claim = (
        f"{reference['name']} {scope} median {median_value}; {range_label} "
        f"{lower}–{upper} ({reference['sample_size']} observations)."
    )
    source_point = metric["company_value"]
    value = float(data_value(source_point))
    return {
        "metric": metric["label"],
        "metric_key": metric["metric_key"],
        "value": {**source_point, "display_value": _fmt_metric(metric["metric_key"], value)},
        "benchmark": evidence(
            claim,
            **inherited_provenance(
                [
                    reference["median"],
                    reference["lower_bound"],
                    reference["upper_bound"],
                ],
                source=f"benchmark-aware analysis: {metric['metric_key']}",
                confidence=0.8,
            ),
        ),
        "benchmark_key": f"relative_{scope}_benchmark",
        "benchmark_params": {
            "name": reference["name"],
            "median": median_value,
            "lower": lower,
            "upper": upper,
            "sampleSize": str(reference["sample_size"]),
        },
    }


def build_insights(m: dict, benchmarks: dict | None = None) -> list[dict]:
    """Flag benchmark outliers without falling back to universal thresholds."""
    benchmarks = benchmarks or {"metrics": []}
    raw = {key: data_value(value) for key, value in m.items()}
    out: list[dict] = []

    def add(code, kind, title, severity, explanation, metric, reference):
        item = _benchmark_item(metric, reference)
        claim_meta = inherited_provenance(
            [item["value"], item["benchmark"]],
            source=f"deterministic benchmark insight: {code}",
            confidence=0.85,
        )
        out.append(
            {
                "code": code,
                "kind": kind,
                "title": evidence(title, **claim_meta),
                "severity": severity,
                "explanation": evidence(explanation, **claim_meta),
                "evidence": [item],
            }
        )

    def evaluate(metric_key, *, above=None, below=None):
        metric = _metric_context(benchmarks, metric_key)
        reference = _primary_reference(metric)
        value = raw.get(metric_key)
        if not metric or not reference or not isinstance(value, (int, float)):
            return
        position, severity = _relative_position(float(value), reference)
        signal = above if position == "above" else below if position == "below" else None
        if not signal:
            return
        code, kind, title, explanation = signal
        if kind == "opportunity" and metric_key in {
            "revenue_growth",
            "profit_margin",
            "free_cash_flow_margin",
        } and value <= 0:
            return
        add(code, kind, title, severity, explanation, metric, reference)

    for valuation_key in ("trailing_pe", "forward_pe", "price_to_sales"):
        before = len(out)
        evaluate(
            valuation_key,
            above=(
                "rich_valuation",
                "risk",
                "Valuation premium to benchmark",
                "The valuation multiple is above the most comparable benchmark range. "
                "The premium requires stronger or more durable results to be justified.",
            ),
            below=(
                "low_earnings_multiple",
                "opportunity",
                "Valuation discount to benchmark",
                "The valuation multiple is below the most comparable benchmark range. "
                "That may indicate value or reflect company-specific risks that peers do not share.",
            ),
        )
        if len(out) > before:
            break

    evaluate(
        "debt_to_equity",
        above=(
            "high_leverage",
            "risk",
            "Leverage above benchmark",
            "Debt is high relative to the comparison group or the company's own history, "
            "which can amplify downturns and refinancing risk.",
        ),
    )
    evaluate(
        "current_ratio",
        below=(
            "tight_liquidity",
            "risk",
            "Liquidity below benchmark",
            "Short-term liquidity sits below the selected comparison range. Review the "
            "company's working-capital model before treating the difference as distress.",
        ),
    )
    evaluate(
        "free_cash_flow_margin",
        above=(
            "strong_cash_generation",
            "opportunity",
            "Cash generation above benchmark",
            "The company converts more revenue into free cash flow than its most relevant "
            "benchmark, providing greater reinvestment or capital-return flexibility.",
        ),
        below=(
            "negative_free_cash_flow",
            "risk",
            "Cash generation below benchmark",
            "Free cash flow conversion trails the most relevant comparison range. Check "
            "whether investment needs are temporary or structurally higher.",
        ),
    )
    evaluate(
        "revenue_growth",
        above=(
            "fast_revenue_growth",
            "opportunity",
            "Revenue growth above benchmark",
            "Sales growth is above the selected industry, peer, sector, or historical range, "
            "which may indicate share gains or stronger end-market demand.",
        ),
        below=(
            "shrinking_revenue",
            "risk",
            "Revenue growth below benchmark",
            "Sales growth trails the most relevant comparison range. Determine whether the "
            "gap is cyclical, company-specific, or caused by a different business mix.",
        ),
    )
    evaluate(
        "profit_margin",
        above=(
            "high_profitability",
            "opportunity",
            "Profitability above benchmark",
            "Net margin is above the selected comparison range, which may reflect pricing "
            "power, scale, or a more profitable business mix.",
        ),
        below=(
            "unprofitable_operations",
            "risk",
            "Profitability below benchmark",
            "Net margin is below the most relevant comparison range. Review whether the gap "
            "comes from temporary investment, cyclicality, or weaker economics.",
        ),
    )
    evaluate(
        "beta",
        above=(
            "high_volatility",
            "risk",
            "Volatility above benchmark",
            "The stock has moved more than its comparison group. Beta is backward-looking "
            "and should be interpreted alongside business and balance-sheet risk.",
        ),
    )
    before_dividend = len(out)
    evaluate(
        "dividend_yield",
        above=(
            "dividend_income",
            "opportunity",
            "Dividend yield above benchmark",
            "The dividend yield is above the selected comparison range. Verify that earnings "
            "and cash flow support the payout before treating the yield as durable.",
        ),
    )
    if len(out) > before_dividend:
        out[-1]["severity"] = "low"

    price = raw.get("price")
    low = raw.get("fifty_two_week_low")
    high = raw.get("fifty_two_week_high")
    if all(isinstance(value, (int, float)) for value in (price, low, high)) and high > low:
        position = (price - low) / (high - low)
        if position >= 0.75 or position <= 0.25:
            kind = "risk" if position >= 0.75 else "opportunity"
            code = "near_52_week_high" if kind == "risk" else "near_52_week_low"
            title = "Upper quartile of 52-week range" if kind == "risk" else "Lower quartile of 52-week range"
            explanation = (
                "The price is in the upper quarter of its own one-year range. This is a "
                "historical price comparison, not evidence that the shares must reverse."
                if kind == "risk"
                else "The price is in the lower quarter of its own one-year range. This may "
                "reflect deteriorating evidence or a possible overreaction."
            )
            inputs = [
                m[key]
                for key in ("price", "fifty_two_week_low", "fifty_two_week_high")
                if isinstance(m.get(key), dict)
            ]
            item = {
                "metric": "Position in 52-week range",
                "metric_key": "range_position",
                "value": data_point(
                    position,
                    display_value=_pct(position),
                    **inherited_provenance(inputs, source="52-week range position", confidence=0.9),
                ),
                "benchmark": evidence(
                    f"Observed range {low:,.2f}–{high:,.2f}",
                    **inherited_provenance(inputs, source="company 52-week range", confidence=0.9),
                ),
                "benchmark_key": "range_values",
                "benchmark_params": {"low": f"{low:,.2f}", "high": f"{high:,.2f}"},
            }
            claim_meta = inherited_provenance(
                [item["value"], item["benchmark"]],
                source=f"deterministic benchmark insight: {code}",
                confidence=0.85,
            )
            out.append(
                {
                    "code": code,
                    "kind": kind,
                    "title": evidence(title, **claim_meta),
                    "severity": "low",
                    "explanation": evidence(explanation, **claim_meta),
                    "evidence": [item],
                }
            )

    severity_rank = {"high": 0, "medium": 1, "low": 2}
    out.sort(key=lambda insight: (severity_rank[insight["severity"]], insight["kind"]))
    return out


COMPARE_METRICS = [
    ("market_cap", "Market cap", True),
    ("trailing_pe", "Trailing P/E", False),
    ("forward_pe", "Forward P/E", False),
    ("price_to_sales", "Price / Sales", False),
    ("revenue_growth", "Revenue growth (YoY)", True),
    ("profit_margin", "Net margin", True),
    ("operating_margin", "Operating margin", True),
    ("debt_to_equity", "Debt / Equity", False),
    ("free_cash_flow", "Free cash flow", True),
    ("dividend_yield", "Dividend yield", True),
    ("beta", "Beta", None),
]


def build_comparison(overviews: list[dict]) -> list[dict]:
    """Side-by-side metric rows across companies, flagging the best per metric."""
    rows = []
    for key, label, higher_better in COMPARE_METRICS:
        values = {o["ticker"]: o.get(key) for o in overviews}
        best = None
        if higher_better is not None:
            numeric = {
                ticker: data_value(value)
                for ticker, value in values.items()
                if isinstance(data_value(value), (int, float))
            }
            if len(numeric) >= 2:
                best_ticker = (max if higher_better else min)(numeric, key=numeric.get)
                best = evidence(
                    best_ticker,
                    **inherited_provenance(
                        [value for value in values.values() if isinstance(value, dict)],
                        source=f"peer comparison: {key}",
                        confidence=0.9,
                    ),
                )
        rows.append(
            {
                "metric": key,
                "label": label,
                "values": values,
                "best": best,
                "higher_is_better": higher_better,
            }
        )
    return rows
