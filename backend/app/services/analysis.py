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


def _fmt_num(v: float | None) -> str:
    if v is None:
        return "n/a"
    if abs(v) >= 1e12:
        return f"{v / 1e12:.2f}T"
    if abs(v) >= 1e9:
        return f"{v / 1e9:.2f}B"
    if abs(v) >= 1e6:
        return f"{v / 1e6:.2f}M"
    return f"{v:,.2f}"


def _pct(v: float | None) -> str:
    return "n/a" if v is None else f"{v * 100:.1f}%"


EVIDENCE_INPUTS = {
    "free_cash_flow_ttm": ("free_cash_flow",),
    "fcf_yield": ("free_cash_flow", "market_cap"),
    "revenue_growth_yoy": ("revenue_growth",),
    "net_profit_margin": ("profit_margin",),
    "beta_5y": ("beta",),
    "range_position": ("price", "fifty_two_week_low", "fifty_two_week_high"),
    "analyst_target_mean": ("analyst_target_mean", "price"),
}

BENCHMARK_INPUTS = {
    "vs_market_cap": ("market_cap",),
}


def _source_points(metrics: dict, metric_key: str | None) -> list[dict]:
    keys = EVIDENCE_INPUTS.get(metric_key, (metric_key,) if metric_key else ())
    return [metrics[key] for key in keys if isinstance(metrics.get(key), dict)]


def _benchmark_points(metrics: dict, item: dict, inputs: list[dict]) -> list[dict]:
    keys = BENCHMARK_INPUTS.get(item.get("benchmark_key"), ())
    extra = [metrics[key] for key in keys if isinstance(metrics.get(key), dict)]
    return [*inputs, *extra]


def build_insights(m: dict) -> list[dict]:
    """Apply transparent rules to normalized metrics. Returns list of insights."""
    sourced_metrics = m
    m = {key: data_value(value) for key, value in m.items()}
    out: list[dict] = []

    def add(code, kind, title, severity, explanation, evidence_items):
        wrapped_items = []
        claim_inputs = []
        for item in evidence_items:
            inputs = _source_points(sourced_metrics, item.get("metric_key"))
            benchmark_inputs = _benchmark_points(sourced_metrics, item, inputs)
            value_meta = inherited_provenance(
                inputs,
                source=f"deterministic analysis: {item.get('metric_key') or item['metric']}",
                confidence=0.9,
            )
            wrapped = {
                **item,
                "value": data_point(
                    item["value"],
                    display_value=str(item["value"]),
                    **value_meta,
                ),
                "benchmark": evidence(
                    item["benchmark"],
                    **inherited_provenance(
                        benchmark_inputs,
                        source=(
                            "analysis benchmark: "
                            f"{item.get('benchmark_key') or item['metric']}"
                        ),
                        confidence=0.75,
                    ),
                ),
            }
            wrapped_items.append(wrapped)
            claim_inputs.append(wrapped["value"])

        claim_meta = inherited_provenance(
            claim_inputs,
            source=f"deterministic insight: {code}",
            confidence=0.85,
        )
        out.append(
            {
                "code": code,
                "kind": kind,
                "title": evidence(title, **claim_meta),
                "severity": severity,
                "explanation": evidence(explanation, **claim_meta),
                "evidence": wrapped_items,
            }
        )

    pe = m.get("trailing_pe")
    if pe is not None:
        if pe > 40:
            add(
                "rich_valuation",
                "risk",
                "Rich valuation",
                "high" if pe > 60 else "medium",
                "The market is paying a high multiple of current earnings. If growth "
                "slows, high-multiple stocks tend to fall harder.",
                [
                    {
                        "metric": "Trailing P/E",
                        "metric_key": "trailing_pe",
                        "value": f"{pe:.1f}",
                        "benchmark": "Broad-market long-run average is roughly 15–20",
                        "benchmark_key": "market_pe_average",
                    }
                ],
            )
        elif pe < 12:
            add(
                "low_earnings_multiple",
                "opportunity",
                "Low earnings multiple",
                "medium",
                "Shares trade cheaply relative to current earnings. That can signal "
                "value — or that the market expects earnings to decline; check why.",
                [
                    {
                        "metric": "Trailing P/E",
                        "metric_key": "trailing_pe",
                        "value": f"{pe:.1f}",
                        "benchmark": "Broad-market long-run average is roughly 15–20",
                        "benchmark_key": "market_pe_average",
                    }
                ],
            )

    dte = m.get("debt_to_equity")
    if dte is not None and dte > 150:
        add(
            "high_leverage",
            "risk",
            "High leverage",
            "high" if dte > 300 else "medium",
            "Debt is large relative to shareholder equity, which magnifies losses in "
            "downturns and raises refinancing risk when rates rise.",
            [
                {
                    "metric": "Debt / Equity",
                    "metric_key": "debt_to_equity",
                    "value": f"{dte:.0f}%",
                    "benchmark": "Above ~150% is generally considered elevated",
                    "benchmark_key": "debt_elevated",
                }
            ],
        )

    cr = m.get("current_ratio")
    if cr is not None and cr < 1:
        add(
            "tight_liquidity",
            "risk",
            "Tight short-term liquidity",
            "medium",
            "Current liabilities exceed current assets; the company may depend on new "
            "financing or fast inventory turnover to pay near-term bills.",
            [
                {
                    "metric": "Current ratio",
                    "metric_key": "current_ratio",
                    "value": f"{cr:.2f}",
                    "benchmark": "Below 1.0 means liabilities due soon exceed liquid assets",
                    "benchmark_key": "current_ratio_low",
                }
            ],
        )

    fcf = m.get("free_cash_flow")
    if fcf is not None and fcf < 0:
        add(
            "negative_free_cash_flow",
            "risk",
            "Negative free cash flow",
            "high",
            "The business consumes more cash than it generates, so it must fund "
            "itself from reserves, debt, or dilution.",
            [
                {
                    "metric": "Free cash flow (TTM)",
                    "metric_key": "free_cash_flow_ttm",
                    "value": _fmt_num(fcf),
                    "benchmark": "Sustainable businesses generate positive free cash flow",
                    "benchmark_key": "positive_fcf",
                }
            ],
        )
    elif fcf is not None and fcf > 0 and m.get("market_cap"):
        yield_ = fcf / m["market_cap"]
        if yield_ > 0.05:
            add(
                "strong_cash_generation",
                "opportunity",
                "Strong cash generation",
                "medium",
                "Free cash flow is high relative to the company's price, giving "
                "flexibility for buybacks, dividends, or reinvestment.",
                [
                    {
                        "metric": "FCF yield",
                        "metric_key": "fcf_yield",
                        "value": _pct(yield_),
                        "benchmark": "Above ~5% is considered strong",
                        "benchmark_key": "fcf_yield_strong",
                    },
                    {
                        "metric": "Free cash flow (TTM)",
                        "metric_key": "free_cash_flow_ttm",
                        "value": _fmt_num(fcf),
                        "benchmark": f"vs market cap {_fmt_num(m['market_cap'])}",
                        "benchmark_key": "vs_market_cap",
                        "benchmark_params": {"marketCap": _fmt_num(m["market_cap"])},
                    },
                ],
            )

    rg = m.get("revenue_growth")
    if rg is not None:
        if rg > 0.15:
            add(
                "fast_revenue_growth",
                "opportunity",
                "Fast revenue growth",
                "high" if rg > 0.30 else "medium",
                "Sales are expanding well above typical GDP-level growth, suggesting "
                "market share gains or a growing market.",
                [
                    {
                        "metric": "Revenue growth (YoY)",
                        "metric_key": "revenue_growth_yoy",
                        "value": _pct(rg),
                        "benchmark": "Above ~15% is fast for an established company",
                        "benchmark_key": "revenue_growth_fast",
                    }
                ],
            )
        elif rg < 0:
            add(
                "shrinking_revenue",
                "risk",
                "Shrinking revenue",
                "high" if rg < -0.10 else "medium",
                "Sales are declining year over year. Check whether this is cyclical, "
                "one-off, or structural.",
                [
                    {
                        "metric": "Revenue growth (YoY)",
                        "metric_key": "revenue_growth_yoy",
                        "value": _pct(rg),
                        "benchmark": "Negative growth means the top line is contracting",
                        "benchmark_key": "revenue_growth_negative",
                    }
                ],
            )

    pm = m.get("profit_margin")
    if pm is not None:
        if pm > 0.20:
            add(
                "high_profitability",
                "opportunity",
                "High profitability",
                "medium",
                "The company keeps a large share of every dollar of revenue as profit, "
                "often a sign of pricing power or scale advantages.",
                [
                    {
                        "metric": "Net profit margin",
                        "metric_key": "net_profit_margin",
                        "value": _pct(pm),
                        "benchmark": "Above ~20% is high across most industries",
                        "benchmark_key": "net_margin_high",
                    }
                ],
            )
        elif pm < 0:
            add(
                "unprofitable_operations",
                "risk",
                "Unprofitable operations",
                "medium",
                "The company currently loses money on a net basis; the investment case "
                "depends on a credible path to profitability.",
                [
                    {
                        "metric": "Net profit margin",
                        "metric_key": "net_profit_margin",
                        "value": _pct(pm),
                        "benchmark": "Negative margin means net losses",
                        "benchmark_key": "net_margin_negative",
                    }
                ],
            )

    beta = m.get("beta")
    if beta is not None and beta > 1.5:
        add(
            "high_volatility",
            "risk",
            "High volatility",
            "low",
            "The stock historically moves much more than the overall market, in both "
            "directions. Expect larger swings.",
            [
                {
                    "metric": "Beta (5y)",
                    "metric_key": "beta_5y",
                    "value": f"{beta:.2f}",
                    "benchmark": "1.0 = moves with the market; above 1.5 is volatile",
                    "benchmark_key": "beta_volatile",
                }
            ],
        )

    dy = m.get("dividend_yield")
    if dy is not None and dy > 0.03:
        add(
            "dividend_income",
            "opportunity",
            "Meaningful dividend income",
            "low",
            "The stock pays a substantial dividend relative to its price. Verify the "
            "payout is covered by earnings and cash flow.",
            [
                {
                    "metric": "Dividend yield",
                    "metric_key": "dividend_yield",
                    "value": _pct(dy),
                    "benchmark": "Above ~3% is a meaningful income component",
                    "benchmark_key": "dividend_meaningful",
                }
            ],
        )

    price, low, high = m.get("price"), m.get("fifty_two_week_low"), m.get("fifty_two_week_high")
    if price and low and high and high > low:
        pos = (price - low) / (high - low)
        if pos > 0.95:
            add(
                "near_52_week_high",
                "risk",
                "Trading at 52-week highs",
                "low",
                "The price sits at the top of its one-year range. Momentum can "
                "continue, but there is little recent price support below.",
                [
                    {
                        "metric": "Position in 52-week range",
                        "metric_key": "range_position",
                        "value": _pct(pos),
                        "benchmark": f"Range {low:,.2f} – {high:,.2f}",
                        "benchmark_key": "range_values",
                        "benchmark_params": {"low": f"{low:,.2f}", "high": f"{high:,.2f}"},
                    }
                ],
            )
        elif pos < 0.10:
            add(
                "near_52_week_low",
                "opportunity",
                "Near 52-week lows",
                "low",
                "The price is at the bottom of its one-year range. This may reflect "
                "real problems or an overreaction — check the news and fundamentals.",
                [
                    {
                        "metric": "Position in 52-week range",
                        "metric_key": "range_position",
                        "value": _pct(pos),
                        "benchmark": f"Range {low:,.2f} – {high:,.2f}",
                        "benchmark_key": "range_values",
                        "benchmark_params": {"low": f"{low:,.2f}", "high": f"{high:,.2f}"},
                    }
                ],
            )

    target = m.get("analyst_target_mean")
    if price and target:
        upside = (target - price) / price
        if abs(upside) > 0.15:
            kind = "opportunity" if upside > 0 else "risk"
            add(
                "analyst_target_gap",
                kind,
                "Analyst targets diverge from price",
                "low",
                "Consensus analyst targets sit well "
                + ("above" if upside > 0 else "below")
                + " the current price. Analyst targets are frequently wrong — treat "
                "as one input, not a verdict.",
                [
                    {
                        "metric": "Mean analyst target",
                        "metric_key": "analyst_target_mean",
                        "value": f"{target:,.2f}",
                        "benchmark": f"vs current price {price:,.2f} ({_pct(upside)} gap)",
                        "benchmark_key": "vs_current_price",
                        "benchmark_params": {
                            "price": f"{price:,.2f}",
                            "gap": _pct(upside),
                        },
                    }
                ],
            )

    severity_rank = {"high": 0, "medium": 1, "low": 2}
    out.sort(key=lambda i: (severity_rank[i["severity"]], i["kind"]))
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
