"""Deterministic valuation engine and API tests."""

import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402
from app.models.schemas import ValuationAssumptions, ValuationResponse  # noqa: E402
from app.services import valuations  # noqa: E402


NOW = datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc)


def point(value, unit=None, provider="Yahoo Finance"):
    return {
        "value": value,
        "unit": unit,
        "display_value": None,
        "provider": provider,
        "source": "test fixture",
        "as_of_date": date(2026, 7, 20),
        "fetched_at": NOW,
        "freshness_status": "fresh",
        "confidence": 0.9,
        "source_url": "https://example.com/source",
    }


def intrinsic_value(growth=0.05, margin=0.10, discount=0.10, terminal=0.02):
    revenue = 1_000.0
    present_values = []
    final_fcf = None
    for year in range(1, 6):
        revenue *= 1 + growth
        final_fcf = revenue * margin
        present_values.append(final_fcf / ((1 + discount) ** year))
    terminal_value = final_fcf * (1 + terminal) / (discount - terminal)
    enterprise_value = sum(present_values) + terminal_value / ((1 + discount) ** 5)
    return (enterprise_value + 100 - 50) / 100


def valuation_inputs(current_price=None):
    current_price = current_price if current_price is not None else intrinsic_value()
    return {
        "ticker": "TEST",
        "currency": "USD",
        "total_revenue": point(1_000.0, "USD"),
        "free_cash_flow": point(100.0, "USD"),
        "total_cash": point(100.0, "USD"),
        "total_debt": point(50.0, "USD"),
        "shares_outstanding": point(100.0, "shares"),
        "current_price": point(current_price, "USD"),
        "trailing_eps": point(2.0, "USD"),
        "revenue_growth": point(0.05, "ratio"),
        "free_cash_flow_margin": point(0.10, "ratio", provider="FinSight"),
    }


def peer_reference(metric_key, multiple):
    return {
        "metric_key": metric_key,
        "references": [
            {
                "scope": "peers",
                "median": point(multiple),
                "sample_size": 3,
                "sample_tickers": ["AAA", "BBB", "CCC"],
            }
        ],
    }


def benchmark_context():
    return {
        "metrics": [
            peer_reference("trailing_pe", 20.0),
            peer_reference("price_to_sales", 4.0),
        ]
    }


def assumptions():
    return ValuationAssumptions(
        projection_years=5,
        revenue_growth=0.05,
        free_cash_flow_margin=0.10,
        discount_rate=0.10,
        terminal_growth=0.02,
        annual_share_dilution=0,
    )


def assert_provenance(item):
    assert item["provider"]
    assert item["source"]
    assert item["as_of_date"]
    assert item["fetched_at"]
    assert item["freshness_status"]
    assert 0 <= item["confidence"] <= 1


def test_dcf_reverse_dcf_peer_multiples_and_sensitivity_are_calculated_in_code():
    result = valuations.build_valuation(
        "TEST",
        valuation_inputs(),
        benchmark_context(),
        assumptions(),
    )
    validated = ValuationResponse.model_validate(result)

    assert validated.base_case.intrinsic_value_per_share.value == pytest.approx(
        intrinsic_value()
    )
    assert validated.base_case.upside_downside.value == pytest.approx(0, abs=1e-7)
    assert validated.reverse_dcf.converged is True
    assert validated.reverse_dcf.implied_revenue_growth.value == pytest.approx(
        0.05, abs=1e-7
    )
    peer_values = {
        estimate.method.value: estimate.implied_value_per_share.value
        for estimate in validated.peer_multiples
    }
    assert peer_values == pytest.approx(
        {"trailing_pe": 40.0, "price_to_sales": 40.0}
    )
    assert [item.scenario.value for item in validated.scenarios] == [
        "conservative",
        "base",
        "optimistic",
    ]
    assert len(validated.sensitivity.terminal_growth_rates) == 5
    assert len(validated.sensitivity.rows) == 5
    assert all(len(row.cells) == 5 for row in validated.sensitivity.rows)
    assert validated.margin_of_safety_range.low.value <= validated.margin_of_safety_range.base.value
    assert validated.margin_of_safety_range.high.value >= validated.margin_of_safety_range.base.value

    payload = validated.model_dump(mode="json")
    assert_provenance(payload["base_case"]["intrinsic_value_per_share"])
    assert_provenance(payload["reverse_dcf"]["implied_revenue_growth"])
    assert_provenance(payload["peer_multiples"][0]["implied_value_per_share"])
    assert "No LLM" in payload["methodology"]["claim"]


def test_default_assumptions_are_transparent_and_code_defined():
    result = valuations.build_valuation(
        "TEST",
        valuation_inputs(current_price=10),
        benchmark_context(),
    )

    assumptions_payload = result["base_case"]["assumptions"]
    assert assumptions_payload["revenue_growth"]["value"] == 0.05
    assert "latest revenue growth" in assumptions_payload["revenue_growth"]["source"]
    assert assumptions_payload["free_cash_flow_margin"]["value"] == 0.10
    assert assumptions_payload["discount_rate"]["value"] == 0.10
    assert "assumption policy" in assumptions_payload["discount_rate"]["source"]


def test_reverse_dcf_returns_a_disclosed_limitation_for_non_positive_margin():
    negative = ValuationAssumptions(
        projection_years=5,
        revenue_growth=0.05,
        free_cash_flow_margin=-0.05,
        discount_rate=0.10,
        terminal_growth=0.02,
        annual_share_dilution=0,
    )
    result = valuations.build_valuation(
        "TEST",
        valuation_inputs(current_price=10),
        benchmark_context(),
        negative,
    )

    assert result["reverse_dcf"]["converged"] is False
    assert result["reverse_dcf"]["implied_revenue_growth"] is None
    assert any("did not converge" in item["claim"] for item in result["limitations"])


def test_valuation_api_uses_code_only_and_validates_assumptions(monkeypatch):
    monkeypatch.setattr(
        "app.main.market_data.get_valuation_inputs",
        lambda ticker: valuation_inputs(),
    )
    monkeypatch.setattr(
        "app.main.market_data.get_overview",
        lambda ticker: {"ticker": ticker, "exchange": "NMS"},
    )
    monkeypatch.setattr(
        "app.main.benchmarks.build_benchmark_context",
        lambda ticker, overview: benchmark_context(),
    )
    monkeypatch.setattr(
        "app.main.ai.narrate_analysis",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("valuation must not call the LLM")
        ),
    )
    client = TestClient(app)

    response = client.get("/api/valuation/TEST")
    assert response.status_code == 200
    assert response.json()["ticker"] == "TEST"
    custom = client.post(
        "/api/valuation/TEST",
        json={
            "projection_years": 5,
            "revenue_growth": 0.08,
            "free_cash_flow_margin": 0.12,
            "discount_rate": 0.11,
            "terminal_growth": 0.025,
            "annual_share_dilution": 0.01,
        },
    )
    assert custom.status_code == 200
    assert custom.json()["base_case"]["assumptions"]["revenue_growth"][
        "provider"
    ] == "User"

    invalid = client.post(
        "/api/valuation/TEST",
        json={
            "projection_years": 5,
            "revenue_growth": 0.08,
            "free_cash_flow_margin": 0.12,
            "discount_rate": 0.02,
            "terminal_growth": 0.03,
            "annual_share_dilution": 0,
        },
    )
    assert invalid.status_code == 422


def test_openapi_exposes_valuation_contracts():
    schema = app.openapi()
    models = schema["components"]["schemas"]

    assert "/api/valuation/{ticker}" in schema["paths"]
    assert {"get", "post"} <= schema["paths"]["/api/valuation/{ticker}"].keys()
    assert models["ValuationResponse"]["properties"]["base_case"]["$ref"].endswith(
        "/DcfResult"
    )
    assert models["ValuationResponse"]["properties"]["reverse_dcf"][
        "$ref"
    ].endswith("/ReverseDcfResult")
    assert models["ResearchSnapshot"]["properties"]["valuation"]["anyOf"][0][
        "$ref"
    ].endswith("/ValuationResponse")
