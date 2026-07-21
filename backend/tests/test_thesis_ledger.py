"""Thesis Ledger API, validation, history, and research-memory integration tests."""

import sys
from datetime import datetime, timezone
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
    "experience_level": "intermediate",
    "research_horizon": "one_to_three_years",
    "priorities": ["growth", "stability"],
    "risk_comfort": "medium",
    "preferred_report_depth": "standard",
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


def _evidence(claim):
    return {
        "claim": claim,
        "source": "Q2 earnings release",
        "source_url": "https://example.com/earnings",
        "as_of_date": "2026-07-20",
        "confidence": 0.9,
    }


def _thesis_payload():
    return {
        "ticker": "test",
        "title": "Durable growth",
        "statement": "Revenue growth can remain durable over the next three years.",
        "confidence": 0.7,
        "assumptions": [
            {
                "description": "Revenue growth remains above 20%.",
                "condition_type": "metric",
                "metric_key": "revenue_growth",
                "operator": ">=",
                "target_value": "20%",
                "current_status": "monitoring",
                "supporting_evidence": [_evidence("Q2 revenue grew 24%.")],
            },
            {
                "description": "Pricing power remains intact.",
                "condition_type": "event",
                "event_condition": "No major competitor launches a comparable product at a materially lower price.",
                "current_status": "unreviewed",
                "contradicting_evidence": [],
            },
        ],
    }


def test_thesis_ledger_records_metric_and_event_assumptions_with_history():
    client = _client()
    try:
        customer_id = _create_customer(client)
        created = client.post(
            f"/api/customers/{customer_id}/theses", json=_thesis_payload()
        )
        assert created.status_code == 201, created.text
        thesis = created.json()
        assert thesis["ticker"] == "TEST"
        assert thesis["status"] == "active"
        assert [item["condition_type"] for item in thesis["assumptions"]] == [
            "metric",
            "event",
        ]
        metric = thesis["assumptions"][0]
        assert metric["supporting_evidence"][0]["claim"] == "Q2 revenue grew 24%."
        assert metric["history"][0]["change_type"] == "created"
        assert metric["history"][0]["previous_values"] is None
        assert metric["history"][0]["current_values"]["target_value"] == "20%"

        listed = client.get(
            f"/api/customers/{customer_id}/theses?ticker=test&status=active"
        )
        assert listed.status_code == 200
        assert listed.json()[0]["id"] == thesis["id"]
    finally:
        app.dependency_overrides.clear()


def test_assumption_updates_append_status_and_evidence_history():
    client = _client()
    try:
        customer_id = _create_customer(client)
        thesis = client.post(
            f"/api/customers/{customer_id}/theses", json=_thesis_payload()
        ).json()
        metric = thesis["assumptions"][0]
        endpoint = (
            f"/api/customers/{customer_id}/theses/{thesis['id']}"
            f"/assumptions/{metric['id']}"
        )

        supported = client.put(
            endpoint,
            json={
                "current_status": "supported",
                "change_reason": "Q2 results cleared the threshold.",
            },
        )
        assert supported.status_code == 200, supported.text
        assert supported.json()["current_status"] == "supported"
        assert supported.json()["last_evaluated_at"] is not None
        assert supported.json()["history"][0]["change_type"] == "status_changed"
        assert supported.json()["history"][0]["reason"].startswith("Q2 results")

        evidence = supported.json()["supporting_evidence"] + [
            _evidence("Management guided to more than 20% growth.")
        ]
        updated = client.put(
            endpoint,
            json={
                "supporting_evidence": evidence,
                "change_reason": "Added management guidance.",
            },
        )
        assert updated.status_code == 200, updated.text
        assert len(updated.json()["supporting_evidence"]) == 2
        assert [item["change_type"] for item in updated.json()["history"]] == [
            "updated",
            "status_changed",
            "created",
        ]
        assert all(
            item["changed_at"].endswith("Z")
            for item in updated.json()["history"]
        )
    finally:
        app.dependency_overrides.clear()


def test_thesis_conditions_are_validated_and_customer_scoped():
    client = _client()
    try:
        owner_id = _create_customer(client)
        other_id = _create_customer(client)
        created = client.post(
            f"/api/customers/{owner_id}/theses", json=_thesis_payload()
        ).json()
        assert client.get(
            f"/api/customers/{other_id}/theses/{created['id']}"
        ).status_code == 404

        invalid_metric = {
            **_thesis_payload(),
            "assumptions": [
                {
                    "description": "Growth remains measurable.",
                    "condition_type": "metric",
                    "metric_key": "revenue_growth",
                    "operator": ">",
                }
            ],
        }
        invalid_event = {
            **_thesis_payload(),
            "assumptions": [
                {
                    "description": "Competition stays rational.",
                    "condition_type": "event",
                    "event_condition": "No material price war begins.",
                    "metric_key": "revenue_growth",
                }
            ],
        }
        assert client.post(
            f"/api/customers/{owner_id}/theses", json=invalid_metric
        ).status_code == 422
        assert client.post(
            f"/api/customers/{owner_id}/theses", json=invalid_event
        ).status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_saved_research_uses_live_ledger_assumptions_for_change_tracking():
    client = _client()
    try:
        customer_id = _create_customer(client)
        thesis = client.post(
            f"/api/customers/{customer_id}/theses", json=_thesis_payload()
        ).json()
        assumption = thesis["assumptions"][0]
        snapshot = {
            "captured_at": datetime(2026, 7, 20, 12, tzinfo=timezone.utc).isoformat(),
            "overview": {"ticker": "TEST"},
            "thesis_assumptions": [],
        }
        saved = client.post(
            f"/api/customers/{customer_id}/research-sessions",
            json={"language": "en", "snapshot": snapshot},
        )
        assert saved.status_code == 201, saved.text
        assert saved.json()["snapshot"]["thesis_assumptions"][0][
            "current_status"
        ] == "monitoring"

        endpoint = (
            f"/api/customers/{customer_id}/theses/{thesis['id']}"
            f"/assumptions/{assumption['id']}"
        )
        assert client.put(
            endpoint,
            json={"current_status": "challenged", "change_reason": "Growth slowed."},
        ).status_code == 200
        changed = client.post(
            f"/api/customers/{customer_id}/what-changed/TEST",
            json={"snapshot": snapshot},
        )
        assert changed.status_code == 200, changed.text
        changes = {
            item["description"]: item
            for item in changed.json()["thesis_assumptions"]
        }
        revenue_change = changes["Revenue growth remains above 20%."]
        assert revenue_change["direction"] == "worsened"
        assert revenue_change["current_status"] == "challenged"
    finally:
        app.dependency_overrides.clear()
