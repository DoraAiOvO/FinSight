"""Unit tests for benchmark-aware analysis rules (no network required)."""
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.analysis import build_comparison, build_insights  # noqa: E402
from app.services.provenance import evidence_text  # noqa: E402
from app.services.tickers import normalize_comparison, normalize_ticker  # noqa: E402


NOW = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)


def point(value, display_value=None):
    return {
        "value": value,
        "unit": None,
        "display_value": display_value,
        "provider": "Yahoo Finance",
        "source": "test fixture",
        "as_of_date": date(2026, 7, 19),
        "fetched_at": NOW,
        "freshness_status": "fresh",
        "confidence": 0.9,
        "source_url": "https://example.com",
    }


def claim(text):
    return {
        "claim": text,
        **{
            key: value
            for key, value in point(None).items()
            if key not in {"value", "unit", "display_value"}
        },
    }


def base_metrics(**overrides):
    metrics = {
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
        "total_revenue": 40e9,
        "free_cash_flow_margin": 0.05,
        "beta": 1.0,
        "dividend_yield": 0.01,
        "fifty_two_week_low": 70.0,
        "fifty_two_week_high": 130.0,
        "analyst_target_mean": 105.0,
    }
    metrics.update(overrides)
    return metrics


def benchmark_context(metrics, **ranges):
    benchmark_metrics = []
    labels = {
        "trailing_pe": "Trailing P/E",
        "debt_to_equity": "Debt / Equity",
        "current_ratio": "Current ratio",
        "free_cash_flow_margin": "Free cash flow margin",
        "revenue_growth": "Revenue growth (YoY)",
        "profit_margin": "Net profit margin",
        "beta": "Beta (5y)",
    }
    for metric_key, (lower, median_value, upper) in ranges.items():
        reference = {
            "scope": "industry",
            "name": "Test industry",
            "median": point(median_value),
            "lower_bound": point(lower),
            "upper_bound": point(upper),
            "range_kind": "middle_50_percent",
            "sample_size": 4,
            "sample_tickers": ["A", "B", "C", "D"],
            "period": None,
            "rationale": claim("Same-industry companies are the closest comparison."),
            "rationale_key": "benchmarkIndustryReason",
            "rationale_params": {
                "name": "Test industry",
                "sampleSize": "4",
                "period": "",
            },
        }
        benchmark_metrics.append(
            {
                "metric_key": metric_key,
                "label": labels.get(metric_key, metric_key),
                "company_value": point(metrics[metric_key]),
                "references": [reference],
                "primary_scope": "industry",
                "primary_rationale": reference["rationale"],
            }
        )
    return {"metrics": benchmark_metrics}


def titles(insights, kind=None):
    return [
        evidence_text(insight["title"])
        for insight in insights
        if kind is None or insight["kind"] == kind
    ]


def test_healthy_company_has_no_high_severity_risks():
    metrics = base_metrics()
    context = benchmark_context(metrics, trailing_pe=(15, 20, 25))
    insights = build_insights(metrics, context)
    assert not [item for item in insights if item["kind"] == "risk" and item["severity"] == "high"]


def test_high_pe_flags_relative_valuation_risk_with_evidence():
    metrics = base_metrics(trailing_pe=75.0)
    context = benchmark_context(metrics, trailing_pe=(15, 20, 25))
    insights = build_insights(metrics, context)
    risk = next(
        item
        for item in insights
        if evidence_text(item["title"]) == "Valuation premium to benchmark"
    )
    assert risk["code"] == "rich_valuation"
    assert risk["severity"] == "high"
    assert risk["evidence"][0]["metric"] == "Trailing P/E"
    assert risk["evidence"][0]["metric_key"] == "trailing_pe"
    assert risk["evidence"][0]["benchmark_key"] == "relative_industry_benchmark"
    assert risk["evidence"][0]["value"]["display_value"] == "75.00"
    assert risk["title"]["provider"] == "FinSight"
    assert risk["explanation"]["confidence"] == 0.8
    assert "industry median 20" in risk["evidence"][0]["benchmark"]["claim"]


def test_low_pe_flags_relative_opportunity():
    metrics = base_metrics(trailing_pe=8.0)
    context = benchmark_context(metrics, trailing_pe=(15, 20, 25))
    assert "Valuation discount to benchmark" in titles(
        build_insights(metrics, context), "opportunity"
    )


def test_universal_pe_cutoff_is_not_used_when_industry_is_more_expensive():
    metrics = base_metrics(trailing_pe=75.0)
    context = benchmark_context(metrics, trailing_pe=(80, 90, 100))
    insights = build_insights(metrics, context)
    assert "Valuation premium to benchmark" not in titles(insights, "risk")


def test_leverage_and_liquidity_use_relative_ranges():
    metrics = base_metrics(debt_to_equity=350.0, current_ratio=0.7)
    context = benchmark_context(
        metrics,
        debt_to_equity=(50, 80, 120),
        current_ratio=(1.1, 1.5, 2.0),
    )
    insights = build_insights(metrics, context)
    assert "Leverage above benchmark" in titles(insights, "risk")
    assert "Liquidity below benchmark" in titles(insights, "risk")
    leverage = next(
        item
        for item in insights
        if evidence_text(item["title"]) == "Leverage above benchmark"
    )
    assert leverage["severity"] == "high"


def test_cash_generation_compares_free_cash_flow_margin():
    weak = base_metrics(free_cash_flow=-1e9, free_cash_flow_margin=-0.10)
    weak_context = benchmark_context(
        weak, free_cash_flow_margin=(0.04, 0.08, 0.12)
    )
    weak_insights = build_insights(weak, weak_context)
    risk = next(
        item
        for item in weak_insights
        if evidence_text(item["title"]) == "Cash generation below benchmark"
    )
    assert risk["severity"] == "high"

    strong = base_metrics(free_cash_flow=8e9, free_cash_flow_margin=0.20)
    strong_context = benchmark_context(
        strong, free_cash_flow_margin=(0.03, 0.06, 0.10)
    )
    strong_insights = build_insights(strong, strong_context)
    assert "Cash generation above benchmark" in titles(strong_insights, "opportunity")
    cash = next(item for item in strong_insights if item["code"] == "strong_cash_generation")
    assert cash["evidence"][0]["benchmark_params"]["sampleSize"] == "4"


def test_growth_and_margin_use_benchmark_distributions():
    metrics = base_metrics(revenue_growth=0.35, profit_margin=0.25)
    context = benchmark_context(
        metrics,
        revenue_growth=(0.03, 0.08, 0.15),
        profit_margin=(0.05, 0.10, 0.18),
    )
    insights = build_insights(metrics, context)
    assert "Revenue growth above benchmark" in titles(insights, "opportunity")
    assert "Profitability above benchmark" in titles(insights, "opportunity")
    growth = next(
        item
        for item in insights
        if evidence_text(item["title"]) == "Revenue growth above benchmark"
    )
    assert growth["severity"] == "high"


def test_growth_and_margin_below_benchmark_are_risks():
    metrics = base_metrics(revenue_growth=-0.15, profit_margin=-0.05)
    context = benchmark_context(
        metrics,
        revenue_growth=(0.02, 0.08, 0.12),
        profit_margin=(0.04, 0.10, 0.16),
    )
    insights = build_insights(metrics, context)
    assert "Revenue growth below benchmark" in titles(insights, "risk")
    assert "Profitability below benchmark" in titles(insights, "risk")


def test_52_week_range_uses_company_quartiles():
    near_high = build_insights(base_metrics(price=129.5))
    assert "Upper quartile of 52-week range" in titles(near_high, "risk")
    near_low = build_insights(base_metrics(price=71.0))
    assert "Lower quartile of 52-week range" in titles(near_low, "opportunity")


def test_analyst_target_does_not_create_a_universal_threshold_signal():
    insights = build_insights(base_metrics(analyst_target_mean=130.0))
    assert "Analyst targets diverge from price" not in titles(insights)


def test_insights_sorted_by_severity():
    metrics = base_metrics(
        free_cash_flow=-1e9,
        free_cash_flow_margin=-0.05,
        beta=1.8,
        trailing_pe=45.0,
    )
    context = benchmark_context(
        metrics,
        free_cash_flow_margin=(0.02, 0.06, 0.10),
        beta=(0.7, 1.0, 1.2),
        trailing_pe=(12, 18, 25),
    )
    insights = build_insights(metrics, context)
    ranks = {"high": 0, "medium": 1, "low": 2}
    severities = [ranks[item["severity"]] for item in insights]
    assert severities == sorted(severities)


def test_missing_metrics_do_not_crash():
    assert build_insights({"ticker": "X"}) == []


def test_comparison_picks_best_per_metric():
    first = base_metrics(ticker="AAA", revenue_growth=0.30, trailing_pe=35.0)
    second = base_metrics(ticker="BBB", revenue_growth=0.05, trailing_pe=12.0)
    rows = build_comparison([first, second])
    by_metric = {row["metric"]: row for row in rows}
    assert evidence_text(by_metric["revenue_growth"]["best"]) == "AAA"
    assert evidence_text(by_metric["trailing_pe"]["best"]) == "BBB"
    assert by_metric["beta"]["best"] is None


def test_comparison_handles_missing_values():
    first = base_metrics(ticker="AAA", dividend_yield=None)
    second = base_metrics(ticker="BBB")
    rows = build_comparison([first, second])
    dividend = next(row for row in rows if row["metric"] == "dividend_yield")
    assert dividend["values"]["AAA"] is None
    assert dividend["best"] is None


def test_tickers_are_normalized_and_validated():
    assert normalize_ticker(" brk-b ") == "BRK-B"
    assert normalize_ticker("rds.a") == "RDS.A"


def test_invalid_ticker_is_rejected():
    import pytest

    with pytest.raises(ValueError, match="valid ticker"):
        normalize_ticker("AAPL/MSFT")


def test_comparison_rejects_duplicates_and_more_than_five():
    import pytest

    with pytest.raises(ValueError, match="unique"):
        normalize_comparison("AAPL, aapl")
    with pytest.raises(ValueError, match="up to 5"):
        normalize_comparison("A,B,C,D,E,F")
