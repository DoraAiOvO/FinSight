"""Opt-in Long-Term Tech Value preset contract tests."""

import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402


PROFILE = {
    "experience_level": "advanced",
    "research_horizon": "five_plus_years",
    "priorities": ["growth", "value"],
    "risk_comfort": "medium",
    "preferred_report_depth": "deep",
    "preferred_language": "en",
    "industries_of_interest": ["Technology"],
}


def _client():
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
    return TestClient(app)


def _create_customer(client):
    response = client.post("/api/customer-profiles", json=PROFILE)
    assert response.status_code == 201
    return response.json()["customer_id"]


def test_long_term_tech_value_is_listed_as_optional_and_never_global_default():
    client = _client()
    try:
        response = client.get("/api/investment-policy-presets")
        assert response.status_code == 200
        presets = response.json()
        assert [preset["name"] for preset in presets] == [
            "Long-Term Tech Value"
        ]
        preset = presets[0]
        assert preset["preset_id"] == "long-term-tech-value"
        assert preset["is_opt_in"] is True
        assert preset["is_global_default"] is False
        assert preset["all_rules_editable"] is True
        assert preset["default_themes"] == [
            "software",
            "semiconductors",
            "internet",
            "AI",
            "cloud computing",
            "new energy",
            "smart vehicles",
        ]
        assert preset["default_markets"] == [
            "United States",
            "Japan",
            "Hong Kong",
        ]
        assert "does not reproduce" in preset["disclaimer"].lower()
        assert "real investor" in preset["disclaimer"].lower()
    finally:
        app.dependency_overrides.clear()


def test_selecting_preset_creates_only_an_editable_inactive_proposal():
    client = _client()
    try:
        customer_id = _create_customer(client)
        response = client.post(
            (
                f"/api/customers/{customer_id}/investment-policy-presets/"
                "long-term-tech-value/proposals"
            )
        )
        assert response.status_code == 201, response.text
        proposal = response.json()
        assert proposal["requires_confirmation"] is True
        assert proposal["ai_provider"] == "Deterministic FinSight preset"
        draft = proposal["proposed_policy"]
        version = draft["initial_version"]
        assert draft["name"] == "Long-Term Tech Value"
        assert version["status"] == "draft"

        principles = {rule["rule_type"] for rule in version["principles"]}
        assert principles == {
            "business_quality",
            "economic_moat",
            "management_and_capital_allocation",
            "long_term_free_cash_flow",
            "structural_growth",
            "margin_of_safety",
            "inversion_and_permanent_loss_risks",
            "concentrated_quality_research",
        }
        assert version["market_scopes"][0]["value"] == [
            "United States",
            "Japan",
            "Hong Kong",
        ]
        assert version["theme_preferences"][0]["value"] == [
            "software",
            "semiconductors",
            "internet",
            "AI",
            "cloud computing",
            "new energy",
            "smart vehicles",
        ]
        assert all(
            isinstance(rule["value"], (int, float))
            for family in ("metric_rules", "valuation_rules", "portfolio_rules")
            for rule in version[family]
        )

        # Selection is review-only and cannot silently create a policy.
        policies = client.get(
            f"/api/customers/{customer_id}/investment-policies"
        )
        assert policies.status_code == 200
        assert policies.json() == []
    finally:
        app.dependency_overrides.clear()


def test_edited_preset_can_be_confirmed_without_becoming_an_implicit_default():
    client = _client()
    try:
        customer_id = _create_customer(client)
        proposal = client.post(
            (
                f"/api/customers/{customer_id}/investment-policy-presets/"
                "long-term-tech-value/proposals"
            )
        ).json()
        edited_policy = proposal["proposed_policy"]
        position_limit = next(
            rule
            for rule in edited_policy["initial_version"]["portfolio_rules"]
            if rule["rule_type"] == "maximum_position_weight"
        )
        position_limit["value"] = 0.12

        confirmed = client.post(
            (
                f"/api/customers/{customer_id}/investment-policy-proposals/"
                f"{proposal['proposal_id']}/confirm"
            ),
            json={
                "confirmed": True,
                "policy": edited_policy,
                "make_default": False,
                "acknowledged_issue_ids": [],
            },
        )
        assert confirmed.status_code == 201, confirmed.text
        policy = confirmed.json()
        assert policy["is_default"] is False
        stored_limit = next(
            rule
            for rule in policy["versions"][0]["portfolio_rules"]
            if rule["rule_type"] == "maximum_position_weight"
        )
        assert stored_limit["value"] == 0.12
    finally:
        app.dependency_overrides.clear()


def test_unknown_preset_is_not_found_and_creates_no_policy():
    client = _client()
    try:
        customer_id = _create_customer(client)
        response = client.post(
            (
                f"/api/customers/{customer_id}/investment-policy-presets/"
                "not-a-preset/proposals"
            )
        )
        assert response.status_code == 404
        assert client.get(
            f"/api/customers/{customer_id}/investment-policies"
        ).json() == []
    finally:
        app.dependency_overrides.clear()
