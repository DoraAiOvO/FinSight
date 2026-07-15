"""Evidence-based risk/opportunity analysis.

Every insight cites the concrete numbers that triggered it, so users can see
*why* FinSight flags something — not just what to think. Deterministic and
fully unit-testable; the optional AI layer only narrates on top of this.
"""

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


def build_insights(m: dict) -> list[dict]:
    """Apply transparent rules to normalized metrics. Returns list of insights."""
    out: list[dict] = []

    def add(kind, title, severity, explanation, evidence):
        out.append(
            {
                "kind": kind,
                "title": title,
                "severity": severity,
                "explanation": explanation,
                "evidence": evidence,
            }
        )

    pe = m.get("trailing_pe")
    if pe is not None:
        if pe > 40:
            add(
                "risk",
                "Rich valuation",
                "high" if pe > 60 else "medium",
                "The market is paying a high multiple of current earnings. If growth "
                "slows, high-multiple stocks tend to fall harder.",
                [
                    {
                        "metric": "Trailing P/E",
                        "value": f"{pe:.1f}",
                        "benchmark": "Broad-market long-run average is roughly 15–20",
                    }
                ],
            )
        elif pe < 12:
            add(
                "opportunity",
                "Low earnings multiple",
                "medium",
                "Shares trade cheaply relative to current earnings. That can signal "
                "value — or that the market expects earnings to decline; check why.",
                [
                    {
                        "metric": "Trailing P/E",
                        "value": f"{pe:.1f}",
                        "benchmark": "Broad-market long-run average is roughly 15–20",
                    }
                ],
            )

    dte = m.get("debt_to_equity")
    if dte is not None and dte > 150:
        add(
            "risk",
            "High leverage",
            "high" if dte > 300 else "medium",
            "Debt is large relative to shareholder equity, which magnifies losses in "
            "downturns and raises refinancing risk when rates rise.",
            [
                {
                    "metric": "Debt / Equity",
                    "value": f"{dte:.0f}%",
                    "benchmark": "Above ~150% is generally considered elevated",
                }
            ],
        )

    cr = m.get("current_ratio")
    if cr is not None and cr < 1:
        add(
            "risk",
            "Tight short-term liquidity",
            "medium",
            "Current liabilities exceed current assets; the company may depend on new "
            "financing or fast inventory turnover to pay near-term bills.",
            [
                {
                    "metric": "Current ratio",
                    "value": f"{cr:.2f}",
                    "benchmark": "Below 1.0 means liabilities due soon exceed liquid assets",
                }
            ],
        )

    fcf = m.get("free_cash_flow")
    if fcf is not None and fcf < 0:
        add(
            "risk",
            "Negative free cash flow",
            "high",
            "The business consumes more cash than it generates, so it must fund "
            "itself from reserves, debt, or dilution.",
            [
                {
                    "metric": "Free cash flow (TTM)",
                    "value": _fmt_num(fcf),
                    "benchmark": "Sustainable businesses generate positive free cash flow",
                }
            ],
        )
    elif fcf is not None and fcf > 0 and m.get("market_cap"):
        yield_ = fcf / m["market_cap"]
        if yield_ > 0.05:
            add(
                "opportunity",
                "Strong cash generation",
                "medium",
                "Free cash flow is high relative to the company's price, giving "
                "flexibility for buybacks, dividends, or reinvestment.",
                [
                    {
                        "metric": "FCF yield",
                        "value": _pct(yield_),
                        "benchmark": "Above ~5% is considered strong",
                    },
                    {
                        "metric": "Free cash flow (TTM)",
                        "value": _fmt_num(fcf),
                        "benchmark": f"vs market cap {_fmt_num(m['market_cap'])}",
                    },
                ],
            )

    rg = m.get("revenue_growth")
    if rg is not None:
        if rg > 0.15:
            add(
                "opportunity",
                "Fast revenue growth",
                "high" if rg > 0.30 else "medium",
                "Sales are expanding well above typical GDP-level growth, suggesting "
                "market share gains or a growing market.",
                [
                    {
                        "metric": "Revenue growth (YoY)",
                        "value": _pct(rg),
                        "benchmark": "Above ~15% is fast for an established company",
                    }
                ],
            )
        elif rg < 0:
            add(
                "risk",
                "Shrinking revenue",
                "high" if rg < -0.10 else "medium",
                "Sales are declining year over year. Check whether this is cyclical, "
                "one-off, or structural.",
                [
                    {
                        "metric": "Revenue growth (YoY)",
                        "value": _pct(rg),
                        "benchmark": "Negative growth means the top line is contracting",
                    }
                ],
            )

    pm = m.get("profit_margin")
    if pm is not None:
        if pm > 0.20:
            add(
                "opportunity",
                "High profitability",
                "medium",
                "The company keeps a large share of every dollar of revenue as profit, "
                "often a sign of pricing power or scale advantages.",
                [
                    {
                        "metric": "Net profit margin",
                        "value": _pct(pm),
                        "benchmark": "Above ~20% is high across most industries",
                    }
                ],
            )
        elif pm < 0:
            add(
                "risk",
                "Unprofitable operations",
                "medium",
                "The company currently loses money on a net basis; the investment case "
                "depends on a credible path to profitability.",
                [
                    {
                        "metric": "Net profit margin",
                        "value": _pct(pm),
                        "benchmark": "Negative margin means net losses",
                    }
                ],
            )

    beta = m.get("beta")
    if beta is not None and beta > 1.5:
        add(
            "risk",
            "High volatility",
            "low",
            "The stock historically moves much more than the overall market, in both "
            "directions. Expect larger swings.",
            [
                {
                    "metric": "Beta (5y)",
                    "value": f"{beta:.2f}",
                    "benchmark": "1.0 = moves with the market; above 1.5 is volatile",
                }
            ],
        )

    dy = m.get("dividend_yield")
    if dy is not None and dy > 0.03:
        add(
            "opportunity",
            "Meaningful dividend income",
            "low",
            "The stock pays a substantial dividend relative to its price. Verify the "
            "payout is covered by earnings and cash flow.",
            [
                {
                    "metric": "Dividend yield",
                    "value": _pct(dy),
                    "benchmark": "Above ~3% is a meaningful income component",
                }
            ],
        )

    price, low, high = m.get("price"), m.get("fifty_two_week_low"), m.get("fifty_two_week_high")
    if price and low and high and high > low:
        pos = (price - low) / (high - low)
        if pos > 0.95:
            add(
                "risk",
                "Trading at 52-week highs",
                "low",
                "The price sits at the top of its one-year range. Momentum can "
                "continue, but there is little recent price support below.",
                [
                    {
                        "metric": "Position in 52-week range",
                        "value": _pct(pos),
                        "benchmark": f"Range {low:,.2f} – {high:,.2f}",
                    }
                ],
            )
        elif pos < 0.10:
            add(
                "opportunity",
                "Near 52-week lows",
                "low",
                "The price is at the bottom of its one-year range. This may reflect "
                "real problems or an overreaction — check the news and fundamentals.",
                [
                    {
                        "metric": "Position in 52-week range",
                        "value": _pct(pos),
                        "benchmark": f"Range {low:,.2f} – {high:,.2f}",
                    }
                ],
            )

    target = m.get("analyst_target_mean")
    if price and target:
        upside = (target - price) / price
        if abs(upside) > 0.15:
            kind = "opportunity" if upside > 0 else "risk"
            add(
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
                        "value": f"{target:,.2f}",
                        "benchmark": f"vs current price {price:,.2f} ({_pct(upside)} gap)",
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
            numeric = {t: v for t, v in values.items() if isinstance(v, (int, float))}
            if len(numeric) >= 2:
                best = (max if higher_better else min)(numeric, key=numeric.get)
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
