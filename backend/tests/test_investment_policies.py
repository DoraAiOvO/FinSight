"""Advanced investment-policy schema, versioning, and ownership API tests."""

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


def _rule(
    rule_type,
    value,
    *,
    effect="preference_fit_scoring",
    operator="equals",
    strength="soft",
):
    return {
        "rule_type": rule_type,
        "operator": operator,
        "value": value,
        "importance": 4,
        "hard_or_soft": strength,
        "rationale": "Express preference fit while preserving all objective evidence.",
        "enabled": True,
        "application_effect": effect,
    }


def _policy_payload():
    return {
        "name": "Long-term quality",
        "description": "Prefer durable businesses at explainable valuations.",
        "is_default": True,
        "initial_version": {
            "status": "published",
            "change_summary": "Initial policy baseline",
            "principles": [
                _rule("quality_first", True, effect="report_emphasis")
            ],
            "market_scopes": [
                _rule("country", ["US", "CA"], effect="filtering")
            ],
            "sector_preferences": [
                _rule("preferred_sector", "Technology", effect="ranking")
            ],
            "theme_preferences": [
                _rule("preferred_theme", "AI infrastructure", effect="ranking")
            ],
            "metric_rules": [
                _rule(
                    "minimum_revenue_growth",
                    0.1,
                    operator="greater_than_or_equal",
                )
            ],
            "constraints": [
                _rule(
                    "excluded_asset_type",
                    "crypto",
                    effect="filtering",
                    strength="hard",
                )
            ],
            "valuation_rules": [
                _rule("maximum_forward_pe", 35, operator="less_than_or_equal")
            ],
            "portfolio_rules": [
                _rule("maximum_position_weight", 0.1, operator="less_than_or_equal")
            ],
            "alert_rules": [
                _rule("valuation_threshold", 25, effect="alerts")
            ],
        },
    }


def test_policy_round_trip_supports_all_rule_families_and_multiple_policies():
    client = _client()
    try:
        customer_id = _create_customer(client)
        created = client.post(
            f"/api/customers/{customer_id}/investment-policies",
            json=_policy_payload(),
        )
        assert created.status_code == 201, created.text
        policy = created.json()
        assert policy["customer_id"] == customer_id
        assert policy["latest_version_number"] == 1
        assert policy["published_version_number"] == 1
        version = policy["versions"][0]

        for collection in (
            "principles",
            "market_scopes",
            "sector_preferences",
            "theme_preferences",
            "metric_rules",
            "constraints",
            "valuation_rules",
            "portfolio_rules",
            "alert_rules",
        ):
            rule = version[collection][0]
            assert {
                "rule_type",
                "operator",
                "value",
                "importance",
                "hard_or_soft",
                "rationale",
                "enabled",
                "created_at",
                "updated_at",
            } <= rule.keys()
        assert version["market_scopes"][0]["value"] == ["US", "CA"]
        assert version["alert_rules"][0]["application_effect"] == "alerts"

        second = client.post(
            f"/api/customers/{customer_id}/investment-policies",
            json={"name": "Income", "is_default": True},
        )
        assert second.status_code == 201, second.text
        listed = client.get(
            f"/api/customers/{customer_id}/investment-policies"
        )
        assert listed.status_code == 200
        assert [item["name"] for item in listed.json()] == [
            "Income",
            "Long-term quality",
        ]
        assert sum(item["is_default"] for item in listed.json()) == 1

        duplicate = client.post(
            f"/api/customers/{customer_id}/investment-policies",
            json={"name": "long-term QUALITY"},
        )
        assert duplicate.status_code == 409
    finally:
        app.dependency_overrides.clear()


def test_publishing_new_version_retires_previous_snapshot():
    client = _client()
    try:
        customer_id = _create_customer(client)
        created = client.post(
            f"/api/customers/{customer_id}/investment-policies",
            json=_policy_payload(),
        ).json()
        policy_id = created["id"]
        first_version_id = created["versions"][0]["id"]

        new_version = client.post(
            f"/api/customers/{customer_id}/investment-policies/{policy_id}/versions",
            json={
                "status": "published",
                "change_summary": "Raise the quality threshold",
                "metric_rules": [
                    _rule(
                        "minimum_revenue_growth",
                        0.15,
                        operator="greater_than_or_equal",
                    )
                ],
            },
        )
        assert new_version.status_code == 201, new_version.text
        assert new_version.json()["version_number"] == 2
        assert new_version.json()["status"] == "published"
        assert new_version.json()["effective_at"] is not None

        detail = client.get(
            f"/api/customers/{customer_id}/investment-policies/{policy_id}"
        ).json()
        assert [version["status"] for version in detail["versions"]] == [
            "retired",
            "published",
        ]
        old_snapshot = client.get(
            f"/api/customers/{customer_id}/investment-policies/{policy_id}/versions/{first_version_id}"
        )
        assert old_snapshot.status_code == 200
        assert old_snapshot.json()["metric_rules"][0]["value"] == 0.1
    finally:
        app.dependency_overrides.clear()


def test_policy_and_version_ids_are_scoped_to_the_owner():
    client = _client()
    try:
        owner_id = _create_customer(client)
        other_id = _create_customer(client)
        created = client.post(
            f"/api/customers/{owner_id}/investment-policies",
            json=_policy_payload(),
        ).json()
        policy_id = created["id"]
        version_id = created["versions"][0]["id"]

        assert client.get(
            f"/api/customers/{other_id}/investment-policies/{policy_id}"
        ).status_code == 404
        assert client.get(
            f"/api/customers/{other_id}/investment-policies/{policy_id}/versions/{version_id}"
        ).status_code == 404
        assert client.post(
            f"/api/customers/{other_id}/investment-policies/{policy_id}/versions",
            json={"change_summary": "Unauthorized"},
        ).status_code == 404
        assert client.delete(
            f"/api/customers/{other_id}/investment-policies/{policy_id}"
        ).status_code == 404

        owned = client.get(
            f"/api/customers/{owner_id}/investment-policies/{policy_id}"
        )
        assert owned.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_rule_effects_cannot_request_evidence_or_benchmark_mutation():
    client = _client()
    try:
        customer_id = _create_customer(client)
        payload = _policy_payload()
        payload["initial_version"]["metric_rules"][0][
            "application_effect"
        ] = "suppress_evidence"
        response = client.post(
            f"/api/customers/{customer_id}/investment-policies",
            json=payload,
        )
        assert response.status_code == 422

        payload["initial_version"]["metric_rules"][0][
            "application_effect"
        ] = "modify_benchmark"
        response = client.post(
            f"/api/customers/{customer_id}/investment-policies",
            json=payload,
        )
        assert response.status_code == 422
        assert client.get(
            f"/api/customers/{customer_id}/investment-policies"
        ).json() == []
    finally:
        app.dependency_overrides.clear()
