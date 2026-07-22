"""Customer onboarding persistence and presentation-boundary tests."""

import sys
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.base import Base  # noqa: E402
from app.db.models import User  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services.analysis import build_insights  # noqa: E402


PROFILE = {
    "experience_level": "beginner",
    "research_horizon": "five_plus_years",
    "priorities": ["stability", "growth"],
    "risk_comfort": "low",
    "preferred_report_depth": "quick",
    "preferred_language": "zh",
    "industries_of_interest": ["Technology", "Semiconductors"],
}


def _point(value):
    return {
        "value": value,
        "unit": None,
        "display_value": None,
        "provider": "Yahoo Finance",
        "source": "test fixture",
        "as_of_date": date(2026, 7, 19),
        "fetched_at": datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc),
        "freshness_status": "fresh",
        "confidence": 0.9,
        "source_url": "https://example.com",
    }


def _claim(text):
    return {
        "claim": text,
        **{
            key: value
            for key, value in _point(None).items()
            if key not in {"value", "unit", "display_value"}
        },
    }


def _benchmark_context(metrics):
    definitions = {
        "trailing_pe": ("Trailing P/E", 15.0, 20.0, 25.0),
        "debt_to_equity": ("Debt / Equity", 50.0, 80.0, 120.0),
    }
    benchmark_metrics = []
    for metric_key, (label, lower, middle, upper) in definitions.items():
        reference = {
            "scope": "industry",
            "name": "Semiconductors",
            "median": _point(middle),
            "lower_bound": _point(lower),
            "upper_bound": _point(upper),
            "range_kind": "middle_50_percent",
            "sample_size": 4,
            "sample_tickers": ["AAA", "BBB", "CCC", "DDD"],
            "period": None,
            "rationale": _claim("Industry comparison."),
            "rationale_key": "benchmarkIndustryReason",
            "rationale_params": {"name": "Semiconductors", "sampleSize": "4"},
        }
        benchmark_metrics.append(
            {
                "metric_key": metric_key,
                "label": label,
                "company_value": _point(metrics[metric_key]),
                "references": [reference],
                "primary_scope": "industry",
                "primary_rationale": reference["rationale"],
            }
        )
    return {
        "industry": "Semiconductors",
        "sector": "Technology",
        "selected_peers": [],
        "metrics": benchmark_metrics,
        "methodology": _claim("Benchmark methodology."),
        "limitations": [],
    }


def test_customer_profile_create_read_and_update(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db():
        with testing_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    try:
        created = client.post("/api/customer-profiles", json=PROFILE)
        assert created.status_code == 201
        payload = created.json()
        customer_id = payload["customer_id"]
        assert payload["priorities"] == ["stability", "growth"]
        assert payload["preferred_language"] == "zh"

        fetched = client.get(f"/api/customer-profiles/{customer_id}")
        assert fetched.status_code == 200
        assert fetched.json() == payload

        replacement = {
            **PROFILE,
            "experience_level": "advanced",
            "priorities": ["value", "income"],
            "preferred_report_depth": "deep",
            "preferred_language": "en",
        }
        updated = client.put(
            f"/api/customer-profiles/{customer_id}", json=replacement
        )
        assert updated.status_code == 200
        assert updated.json()["experience_level"] == "advanced"
        assert updated.json()["priorities"] == ["value", "income"]

        with Session(engine) as session:
            user = session.scalar(select(User))
            assert user is not None
            assert user.email is None
            assert user.customer_profile.preferred_report_depth == "deep"
    finally:
        app.dependency_overrides.clear()


def test_customer_profile_validation_rejects_duplicates_and_unknown_values():
    client = TestClient(app)
    duplicate_priorities = {
        **PROFILE,
        "priorities": ["growth", "growth"],
    }
    invalid_risk = {**PROFILE, "risk_comfort": "very_high"}

    assert client.post("/api/customer-profiles", json=duplicate_priorities).status_code == 422
    assert client.post("/api/customer-profiles", json=invalid_risk).status_code == 422


def test_profile_only_changes_presentation_not_report_evidence(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db():
        with testing_session() as session:
            yield session

    metrics = {
        "ticker": "TEST",
        "name": "Test Corp",
        "sector": "Technology",
        "industry": "Semiconductors",
        "price": 100.0,
        "market_cap": 50e9,
        "trailing_pe": 65.0,
        "profit_margin": 0.25,
        "revenue_growth": 0.35,
        "debt_to_equity": 350.0,
        "current_ratio": 1.5,
        "free_cash_flow": 4e9,
        "beta": 1.8,
        "dividend_yield": 0.01,
        "fifty_two_week_low": 70.0,
        "fifty_two_week_high": 130.0,
        "analyst_target_mean": 105.0,
    }
    narrative_calls = []

    def record_narrative(
        ticker, metrics, insights, lang="en", explanation_depth="standard"
    ):
        narrative_calls.append(
            {
                "lang": lang,
                "explanation_depth": explanation_depth,
                "codes": [insight["code"] for insight in insights],
            }
        )
        return None

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr("app.main.market_data.get_overview", lambda ticker: metrics)
    monkeypatch.setattr(
        "app.main.benchmarks.build_benchmark_context",
        lambda ticker, company_metrics: _benchmark_context(company_metrics),
    )
    monkeypatch.setattr("app.main.ai.narrate_analysis", record_narrative)
    client = TestClient(app)
    try:
        anonymous = client.get("/api/analysis/TEST").json()
        created = client.post("/api/customer-profiles", json=PROFILE).json()
        personalized = client.get(
            f"/api/analysis/TEST?customer_id={created['customer_id']}&lang=zh"
        ).json()

        anonymous_evidence = anonymous["neutral_evidence"]
        personalized_evidence = personalized["neutral_evidence"]
        anonymous_insights = [
            *anonymous_evidence["risks"],
            *anonymous_evidence["opportunities"],
        ]
        personalized_insights = [
            *personalized_evidence["risks"],
            *personalized_evidence["opportunities"],
        ]
        anonymous_codes = {item["code"] for item in anonymous_insights}
        personalized_codes = {item["code"] for item in personalized_insights}
        assert personalized_codes == anonymous_codes
        interpretation = personalized["personalized_interpretation"]
        presentation = interpretation["presentation"]
        assert presentation["personalized"] is True
        assert presentation["explanation_depth"] == "simple"
        assert presentation["section_order"] == [
            "overview",
            "analysis",
            "price_history",
            "news",
        ]
        assert presentation["industry_match"] is True
        assert "high_leverage" in interpretation["report_emphasis"]
        assert any(
            item["code"] == "rich_valuation" and item["kind"] == "risk"
            for item in personalized_insights
        )

        # The model-facing call receives only language, explanation depth, and
        # the unchanged evidence set—not risk comfort or suitability data.
        assert narrative_calls[-1] == {
            "lang": "zh",
            "explanation_depth": "standard",
            "codes": [
                item["code"]
                for item in build_insights(metrics, _benchmark_context(metrics))
            ],
        }

        professional_profile = {
            **PROFILE,
            "experience_level": "advanced",
            "preferred_report_depth": "deep",
        }
        update = client.put(
            f"/api/customer-profiles/{created['customer_id']}",
            json=professional_profile,
        )
        assert update.status_code == 200
        professional = client.get(
            f"/api/analysis/TEST?customer_id={created['customer_id']}"
        ).json()
        assert professional["personalized_interpretation"]["presentation"][
            "explanation_depth"
        ] == "professional"
        professional_neutral = professional["neutral_evidence"]
        assert {
            item["code"]
            for item in [
                *professional_neutral["risks"],
                *professional_neutral["opportunities"],
            ]
        } == anonymous_codes
    finally:
        app.dependency_overrides.clear()
