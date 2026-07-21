"""Unit tests for provider-data normalization (no network required)."""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.market_data import (  # noqa: E402
    extract_metrics,
    get_historical_financial_metrics,
    get_overview,
    normalize_dividend_yield,
    normalize_history_points,
)


def test_history_normalization_skips_missing_and_non_finite_closes():
    rows = [
        (datetime(2026, 7, 10), {"Close": 210.125}),
        (datetime(2026, 7, 11), {"Close": None}),
        (datetime(2026, 7, 12), {"Close": float("nan")}),
        (datetime(2026, 7, 13), {}),
        (datetime(2026, 7, 14), {"Close": 214.876}),
    ]

    assert normalize_history_points(rows) == [
        {"date": "2026-07-10", "close": 210.12},
        {"date": "2026-07-14", "close": 214.88},
    ]


def test_dividend_yield_prefers_annual_dividend_over_provider_units():
    info = {
        "symbol": "TEST",
        "currentPrice": 200.0,
        "dividendRate": 2.0,
        "dividendYield": 1.0,
    }

    assert extract_metrics(info, "TEST")["dividend_yield"] == 0.01


def test_dividend_yield_normalizes_percentage_points_fallback():
    assert normalize_dividend_yield({"dividendYield": 0.34}, None) == pytest.approx(0.0034)
    assert normalize_dividend_yield({"dividendYield": 0.015}, None) == 0.015


def test_free_cash_flow_margin_is_derived_from_revenue():
    metrics = extract_metrics(
        {"symbol": "TEST", "freeCashflow": 20.0, "totalRevenue": 100.0},
        "TEST",
    )
    assert metrics["free_cash_flow_margin"] == pytest.approx(0.20)


def test_annual_statements_create_company_historical_ranges(monkeypatch):
    columns = [pd.Timestamp("2024-12-31"), pd.Timestamp("2023-12-31")]
    income = pd.DataFrame(
        {
            columns[0]: {
                "TotalRevenue": 120.0,
                "NetIncome": 30.0,
                "OperatingIncome": 40.0,
            },
            columns[1]: {
                "TotalRevenue": 100.0,
                "NetIncome": 20.0,
                "OperatingIncome": 25.0,
            },
        }
    )
    balance = pd.DataFrame(
        {
            columns[0]: {
                "TotalDebt": 50.0,
                "StockholdersEquity": 50.0,
                "CurrentAssets": 80.0,
                "CurrentLiabilities": 40.0,
            },
            columns[1]: {
                "TotalDebt": 45.0,
                "StockholdersEquity": 50.0,
                "CurrentAssets": 70.0,
                "CurrentLiabilities": 40.0,
            },
        }
    )
    cash_flow = pd.DataFrame(
        {
            columns[0]: {"FreeCashFlow": 20.0},
            columns[1]: {"FreeCashFlow": 15.0},
        }
    )

    class FakeTicker:
        def get_income_stmt(self, freq="yearly"):
            return income

        def get_balance_sheet(self, freq="yearly"):
            return balance

        def get_cash_flow(self, freq="yearly"):
            return cash_flow

    monkeypatch.setattr("app.services.market_data.yf.Ticker", lambda ticker: FakeTicker())
    observations = get_historical_financial_metrics("HISTTEST")
    latest = observations[0]

    assert latest["period_end"].isoformat() == "2024-12-31"
    assert latest["metrics"]["revenue_growth"]["value"] == pytest.approx(0.20)
    assert latest["metrics"]["profit_margin"]["value"] == pytest.approx(0.25)
    assert latest["metrics"]["debt_to_equity"]["value"] == pytest.approx(100.0)
    assert latest["metrics"]["current_ratio"]["value"] == pytest.approx(2.0)
    assert latest["metrics"]["free_cash_flow_margin"]["value"] == pytest.approx(1 / 6)
    assert latest["metrics"]["profit_margin"]["freshness_status"] == "historical"


def test_overview_wraps_financial_values_and_summary_with_provenance(monkeypatch):
    fetched_at = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
    info = {
        "symbol": "TEST",
        "shortName": "Test Corp",
        "currency": "USD",
        "currentPrice": 200.0,
        "previousClose": 190.0,
        "marketCap": 1_000_000,
        "longBusinessSummary": "A test company.",
        "regularMarketTime": int(datetime(2026, 7, 19, tzinfo=timezone.utc).timestamp()),
    }
    monkeypatch.setattr(
        "app.services.market_data._info_with_fetch_time",
        lambda ticker: (info, fetched_at),
    )

    overview = get_overview("TEST")

    assert overview["price"]["value"] == 200.0
    assert overview["price"]["provider"] == "Yahoo Finance"
    assert overview["price"]["as_of_date"].isoformat() == "2026-07-19"
    assert overview["price"]["freshness_status"] == "fresh"
    assert overview["price"]["source_url"].endswith("/quote/TEST")
    assert overview["change_percent"]["provider"] == "FinSight"
    assert overview["summary"]["claim"] == "A test company."
