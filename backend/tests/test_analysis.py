"""Unit tests for the evidence-based analysis rules (no network required)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.analysis import build_comparison, build_insights  # noqa: E402


def base_metrics(**overrides):
    m = {
        "ticker": "TEST",
        "name": "Test Corp",
        "price": 100.0,
        "market_cap": 50e9,
        "trailing_pe": 20.0,
        "forward_pe": 18.0,
        "price_to_sales": 5.0,
        "profit_margin": 0.10,
        "operating_margin": 0.15,
        "revenue_growth": 0.08,
        "earnings_growth": 0.05,
        "debt_to_equity": 80.0,
        "current_ratio": 1.5,
        "free_cash_flow": 2e9,
        "beta": 1.0,
        "dividend_yield": 0.01,
        "fifty_two_week_low": 70.0,
        "fifty_two_week_high": 130.0,
        "analyst_target_mean": 105.0,
    }
    m.update(overrides)
    return m


def titles(insights, kind=None):
    return [i["title"] for i in insights if kind is None or i["kind"] == kind]


def test_healthy_company_has_no_high_severity_risks():
    insights = build_insights(base_metrics())
    assert not [i for i in insights if i["kind"] == "risk" and i["severity"] == "high"]


def test_high_pe_flags_valuation_risk_with_evidence():
    insights = build_insights(base_metrics(trailing_pe=75.0))
    risk = next(i for i in insights if i["title"] == "Rich valuation")
    assert risk["severity"] == "high"
    assert risk["evidence"][0]["metric"] == "Trailing P/E"
    assert "75.0" in risk["evidence"][0]["value"]


def test_low_pe_flags_opportunity():
    insights = build_insights(base_metrics(trailing_pe=8.0))
    assert "Low earnings multiple" in titles(insights, "opportunity")


def test_leverage_and_liquidity_risks():
    insights = build_insights(base_metrics(debt_to_equity=350.0, current_ratio=0.7))
    assert "High leverage" in titles(insights, "risk")
    assert "Tight short-term liquidity" in titles(insights, "risk")
    leverage = next(i for i in insights if i["title"] == "High leverage")
    assert leverage["severity"] == "high"


def test_negative_fcf_is_high_risk():
    insights = build_insights(base_metrics(free_cash_flow=-1e9))
    fcf = next(i for i in insights if i["title"] == "Negative free cash flow")
    assert fcf["severity"] == "high"


def test_strong_fcf_yield_is_opportunity():
    insights = build_insights(base_metrics(free_cash_flow=4e9, market_cap=50e9))
    assert "Strong cash generation" in titles(insights, "opportunity")


def test_growth_and_margin_opportunities():
    insights = build_insights(base_metrics(revenue_growth=0.35, profit_margin=0.25))
    assert "Fast revenue growth" in titles(insights, "opportunity")
    assert "High profitability" in titles(insights, "opportunity")
    growth = next(i for i in insights if i["title"] == "Fast revenue growth")
    assert growth["severity"] == "high"


def test_shrinking_revenue_and_losses_are_risks():
    insights = build_insights(base_metrics(revenue_growth=-0.15, profit_margin=-0.05))
    assert "Shrinking revenue" in titles(insights, "risk")
    assert "Unprofitable operations" in titles(insights, "risk")


def test_52_week_range_position():
    near_high = build_insights(base_metrics(price=129.5))
    assert "Trading at 52-week highs" in titles(near_high, "risk")
    near_low = build_insights(base_metrics(price=71.0))
    assert "Near 52-week lows" in titles(near_low, "opportunity")


def test_analyst_gap_flags_both_directions():
    upside = build_insights(base_metrics(analyst_target_mean=130.0))
    assert "Analyst targets diverge from price" in titles(upside, "opportunity")
    downside = build_insights(base_metrics(analyst_target_mean=80.0))
    assert "Analyst targets diverge from price" in titles(downside, "risk")


def test_insights_sorted_by_severity():
    insights = build_insights(
        base_metrics(free_cash_flow=-1e9, beta=1.8, trailing_pe=45.0)
    )
    ranks = {"high": 0, "medium": 1, "low": 2}
    sev = [ranks[i["severity"]] for i in insights]
    assert sev == sorted(sev)


def test_missing_metrics_do_not_crash():
    insights = build_insights({"ticker": "X"})
    assert insights == []


def test_comparison_picks_best_per_metric():
    a = base_metrics()
    a.update({"ticker": "AAA", "revenue_growth": 0.30, "trailing_pe": 35.0})
    b = base_metrics()
    b.update({"ticker": "BBB", "revenue_growth": 0.05, "trailing_pe": 12.0})
    rows = build_comparison([a, b])
    by_metric = {r["metric"]: r for r in rows}
    assert by_metric["revenue_growth"]["best"] == "AAA"  # higher is better
    assert by_metric["trailing_pe"]["best"] == "BBB"  # lower is better
    assert by_metric["beta"]["best"] is None  # neutral metric


def test_comparison_handles_missing_values():
    a = base_metrics()
    a.update({"ticker": "AAA", "dividend_yield": None})
    b = base_metrics()
    b.update({"ticker": "BBB"})
    rows = build_comparison([a, b])
    div = next(r for r in rows if r["metric"] == "dividend_yield")
    assert div["values"]["AAA"] is None
    # With only one company reporting, no "best" is declared — a win against
    # missing data would be misleading evidence.
    assert div["best"] is None
