"""Deterministic benchmark selection and aggregation tests."""
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services import benchmarks  # noqa: E402
from app.services.provenance import data_value, evidence_text  # noqa: E402


NOW = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)


def point(value, unit=None):
    return {
        "value": value,
        "unit": unit,
        "display_value": None,
        "provider": "Yahoo Finance",
        "source": "test fixture",
        "as_of_date": date(2026, 7, 19),
        "fetched_at": NOW,
        "freshness_status": "fresh",
        "confidence": 0.9,
        "source_url": "https://example.com",
    }


def company(
    ticker,
    market_cap,
    trailing_pe,
    revenue_growth,
    *,
    industry="Software - Infrastructure",
):
    return {
        "ticker": ticker,
        "name": f"{ticker} Corp",
        "sector": "Technology",
        "industry": industry,
        "exchange": "NMS",
        "market_cap": point(market_cap, "USD"),
        "trailing_pe": point(trailing_pe),
        "revenue_growth": point(revenue_growth, "ratio"),
    }


def quote(ticker, market_cap, exchange="NMS"):
    return {
        "symbol": ticker,
        "shortName": f"{ticker} Corp",
        "quoteType": "EQUITY",
        "exchange": exchange,
        "marketCap": market_cap,
    }


def test_screener_labels_and_exchange_region_match_yahoo_taxonomy():
    assert (
        benchmarks.normalize_screener_label("industry", "Software - Infrastructure")
        == "Software—Infrastructure"
    )
    assert benchmarks.normalize_screener_label("sector", "Technology") == "Technology"
    assert benchmarks.exchange_region("NMS") == "us"


def test_build_context_exposes_all_four_benchmarks_and_peer_reasons(monkeypatch):
    overview = company("TEST", 100e9, 42.0, 0.22)
    industry_quotes = [
        {**quote("AAD", 96e9), "shortName": "AAA Corp"},
        quote("AAA", 95e9),
        quote("BBB", 110e9),
        quote("CCC", 80e9),
        quote("DDD", 125e9),
        quote("TEST", 100e9),
    ]
    sector_quotes = [
        quote("EEE", 90e9),
        quote("FFF", 115e9),
        quote("GGG", 70e9),
        quote("HHH", 140e9),
        quote("III", 60e9),
    ]
    peer_overviews = {
        "AAD": {**company("AAD", 96e9, 15.0, 0.05), "name": "AAA Corp"},
        "AAA": company("AAA", 95e9, 15.0, 0.05),
        "BBB": company("BBB", 110e9, 20.0, 0.08),
        "CCC": company("CCC", 80e9, 25.0, 0.10),
        "DDD": company("DDD", 125e9, 30.0, 0.12),
        "EEE": company("EEE", 90e9, 18.0, 0.06, industry="Semiconductors"),
        "FFF": company("FFF", 115e9, 22.0, 0.07, industry="Computer Hardware"),
        "GGG": company("GGG", 70e9, 28.0, 0.09, industry="Semiconductors"),
        "HHH": company("HHH", 140e9, 32.0, 0.11, industry="Computer Hardware"),
        "III": company("III", 60e9, 35.0, 0.13, industry="Software - Application"),
    }

    def candidates(scope, name, **kwargs):
        return industry_quotes if scope == "industry" else sector_quotes

    history = [
        {
            "period_end": date(year, 12, 31),
            "metrics": {"revenue_growth": point(value, "ratio")},
        }
        for year, value in ((2022, 0.04), (2023, 0.09), (2024, 0.14))
    ]
    monkeypatch.setattr(
        "app.services.benchmarks.market_data.get_benchmark_candidates", candidates
    )
    monkeypatch.setattr(
        "app.services.benchmarks.market_data.get_overview",
        lambda ticker: peer_overviews[ticker],
    )
    monkeypatch.setattr(
        "app.services.benchmarks.market_data.get_historical_financial_metrics",
        lambda ticker: history,
    )

    context = benchmarks.build_benchmark_context("TEST", overview)
    assert [peer["ticker"] for peer in context["selected_peers"]] == [
        "AAD",
        "BBB",
        "CCC",
        "DDD",
    ]
    assert all(
        peer["selection_reason_key"] == "peerSameIndustryReason"
        for peer in context["selected_peers"]
    )

    revenue = next(
        metric for metric in context["metrics"] if metric["metric_key"] == "revenue_growth"
    )
    references = {reference["scope"]: reference for reference in revenue["references"]}
    assert set(references) == {"industry", "sector", "peers", "historical"}
    assert revenue["primary_scope"] == "industry"
    assert data_value(references["industry"]["median"]) == 0.09
    assert data_value(references["industry"]["lower_bound"]) == 0.0725
    assert data_value(references["industry"]["upper_bound"]) == pytest.approx(0.105)
    assert references["historical"]["period"] == "2022–2024"
    assert data_value(references["historical"]["lower_bound"]) == 0.04
    assert data_value(references["historical"]["upper_bound"]) == 0.14
    assert references["sector"]["sample_size"] == 9
    assert references["industry"]["median"]["provider"] == "FinSight"
    assert "transparent sample" in evidence_text(context["methodology"])
    assert context["limitations"]


def test_context_degrades_each_missing_scope_without_universal_fallback(monkeypatch):
    overview = company("TEST", 100e9, 42.0, 0.22)
    monkeypatch.setattr(
        "app.services.benchmarks.market_data.get_benchmark_candidates",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        "app.services.benchmarks.market_data.get_historical_financial_metrics",
        lambda ticker: [],
    )
    context = benchmarks.build_benchmark_context("TEST", overview)
    assert context["selected_peers"] == []
    assert all(metric["references"] == [] for metric in context["metrics"])
    assert all(metric["primary_scope"] is None for metric in context["metrics"])
    assert any(
        "No sufficiently comparable" in evidence_text(item)
        for item in context["limitations"]
    )
