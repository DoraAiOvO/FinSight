"""Unit tests for provider-data normalization (no network required)."""
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.market_data import (  # noqa: E402
    extract_metrics,
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
