"""Natural-language policy extraction, review, and confirmation tests."""

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

FAMILIES = (
    "principles",
    "market_scopes",
    "sector_preferences",
    "theme_preferences",
    "metric_rules",
    "constraints",
    "valuation_rules",
    "portfolio_rules",
    "alert_rules",
)


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


def _rule(rule_type, operator, value, *, family="metric_rules"):
    effects = {
        "constraints": "filtering",
        "alert_rules": "alerts",
        "sector_preferences": "ranking",
    }
    return {
        "rule_type": rule_type,
        "operator": operator,
        "value": value,
        "importance": 4,
        "hard_or_soft": "hard" if family == "constraints" else "soft",
        "rationale": "Directly stated by the user.",
        "enabled": True,
        "application_effect": effects.get(family, "preference_fit_scoring"),
    }


def _extraction(**families):
    rules = {family: [] for family in FAMILIES}
    rules.update(families)
    return {
        "name": "Quality technology",
        "description": "A multilingual, user-authored policy.",
        "detected_languages": ["es", "en"],
        "rules": rules,
        "issues": [],
    }


def _confirm_payload(proposal, issue_ids=()):
    return {
        "confirmed": True,
        "policy": proposal["proposed_policy"],
        "make_default": True,
        "acknowledged_issue_ids": list(issue_ids),
    }


def test_code_switched_extraction_is_review_only_and_normalizes_terms(monkeypatch):
    client = _client()
    monkeypatch.setattr(
        "app.services.policy_builder.ai.extract_investment_policy",
        lambda *args, **kwargs: _extraction(
            sector_preferences=[
                _rule(
                    "preferred_sector",
                    "equals",
                    "tecnología",
                    family="sector_preferences",
                )
            ],
            constraints=[
                _rule(
                    "excluded_tickers",
                    "not_in",
                    ["tsla", "brk.b"],
                    family="constraints",
                )
            ],
            valuation_rules=[
                _rule("P/E ratio", "less_than_or_equal", 25)
            ],
        ),
    )
    try:
        customer_id = _create_customer(client)
        response = client.post(
            f"/api/customers/{customer_id}/investment-policy-proposals",
            json={
                "preferences": (
                    "Quiero empresas de tecnología, keep forward P/E under 25, "
                    "pero avoid tsla y brk.b."
                )
            },
        )
        assert response.status_code == 201, response.text
        proposal = response.json()
        assert proposal["requires_confirmation"] is True
        assert proposal["detected_languages"] == ["es", "en"]
        version = proposal["proposed_policy"]["initial_version"]
        assert version["status"] == "draft"
        assert version["sector_preferences"][0]["value"] == "Technology"
        assert version["constraints"][0]["value"] == ["TSLA", "BRK.B"]
        assert version["valuation_rules"][0]["rule_type"] == "price_to_earnings"

        # Extraction persists only a proposal; it cannot affect analysis.
        listed = client.get(
            f"/api/customers/{customer_id}/investment-policies"
        )
        assert listed.status_code == 200
        assert listed.json() == []
    finally:
        app.dependency_overrides.clear()


def test_confirmation_is_explicit_and_creates_a_published_version(monkeypatch):
    client = _client()
    monkeypatch.setattr(
        "app.services.policy_builder.ai.extract_investment_policy",
        lambda *args, **kwargs: _extraction(
            principles=[_rule("quality_first", "equals", True)]
        ),
    )
    try:
        customer_id = _create_customer(client)
        proposal = client.post(
            f"/api/customers/{customer_id}/investment-policy-proposals",
            json={"text": "Prefer high-quality companies."},
        ).json()
        confirm_url = (
            f"/api/customers/{customer_id}/investment-policy-proposals/"
            f"{proposal['proposal_id']}/confirm"
        )

        implicit = _confirm_payload(proposal)
        implicit["confirmed"] = False
        assert client.post(confirm_url, json=implicit).status_code == 422
        assert client.get(
            f"/api/customers/{customer_id}/investment-policies"
        ).json() == []

        confirmed = client.post(confirm_url, json=_confirm_payload(proposal))
        assert confirmed.status_code == 201, confirmed.text
        policy = confirmed.json()
        assert policy["latest_version_number"] == 1
        assert policy["published_version_number"] == 1
        assert policy["versions"][0]["status"] == "published"
        assert policy["is_default"] is True
        assert client.post(
            confirm_url, json=_confirm_payload(proposal)
        ).status_code == 409
    finally:
        app.dependency_overrides.clear()


def test_ambiguous_instruction_must_be_shown_and_acknowledged(monkeypatch):
    client = _client()
    extraction = _extraction(
        metric_rules=[_rule("minimum_revenue_growth", "approximately", 0.1)]
    )
    extraction["issues"] = [
        {
            "code": "ambiguous_instruction",
            "severity": "warning",
            "message": "The phrase 'about 10%' has no exact boundary.",
            "source_text": "maybe growth about 10%",
            "rule_families": ["metric_rules"],
        }
    ]
    monkeypatch.setattr(
        "app.services.policy_builder.ai.extract_investment_policy",
        lambda *args, **kwargs: extraction,
    )
    try:
        customer_id = _create_customer(client)
        proposal = client.post(
            f"/api/customers/{customer_id}/investment-policy-proposals",
            json={"preferences": "Maybe revenue growth about 10%."},
        ).json()
        assert [issue["code"] for issue in proposal["issues"]] == [
            "ambiguous_instruction"
        ]
        confirm_url = (
            f"/api/customers/{customer_id}/investment-policy-proposals/"
            f"{proposal['proposal_id']}/confirm"
        )
        not_reviewed = client.post(confirm_url, json=_confirm_payload(proposal))
        assert not_reviewed.status_code == 400
        assert "acknowledge" in not_reviewed.json()["detail"]

        issue_ids = [issue["issue_id"] for issue in proposal["issues"]]
        confirmed = client.post(
            confirm_url,
            json=_confirm_payload(proposal, issue_ids),
        )
        assert confirmed.status_code == 201, confirmed.text
    finally:
        app.dependency_overrides.clear()


def test_conflicting_bounds_are_blocked_until_user_edits_them(monkeypatch):
    client = _client()
    monkeypatch.setattr(
        "app.services.policy_builder.ai.extract_investment_policy",
        lambda *args, **kwargs: _extraction(
            metric_rules=[
                _rule("revenue_growth", "greater_than_or_equal", 0.3),
                _rule("revenue_growth", "less_than_or_equal", 0.2),
            ]
        ),
    )
    try:
        customer_id = _create_customer(client)
        proposal = client.post(
            f"/api/customers/{customer_id}/investment-policy-proposals",
            json={
                "natural_language_preferences": (
                    "Revenue growth must be at least 30% and no more than 20%."
                )
            },
        ).json()
        conflicts = [
            issue
            for issue in proposal["issues"]
            if issue["code"] == "conflicting_instructions"
        ]
        assert conflicts
        confirm_url = (
            f"/api/customers/{customer_id}/investment-policy-proposals/"
            f"{proposal['proposal_id']}/confirm"
        )
        issue_ids = [issue["issue_id"] for issue in proposal["issues"]]
        unresolved = client.post(
            confirm_url, json=_confirm_payload(proposal, issue_ids)
        )
        assert unresolved.status_code == 400
        assert "Resolve conflicting" in unresolved.json()["detail"]

        edited = _confirm_payload(proposal, issue_ids)
        edited["policy"]["initial_version"]["metric_rules"][1]["value"] = 0.35
        confirmed = client.post(confirm_url, json=edited)
        assert confirmed.status_code == 201, confirmed.text
        stored_rules = confirmed.json()["versions"][0]["metric_rules"]
        assert [rule["value"] for rule in stored_rules] == [0.3, 0.35]
    finally:
        app.dependency_overrides.clear()


def test_failed_ai_extraction_never_saves_a_policy(monkeypatch):
    client = _client()
    monkeypatch.setattr(
        "app.services.policy_builder.ai.extract_investment_policy",
        lambda *args, **kwargs: None,
    )
    try:
        customer_id = _create_customer(client)
        response = client.post(
            f"/api/customers/{customer_id}/investment-policy-proposals",
            json={"preferences": "Prefer profitable businesses."},
        )
        assert response.status_code == 503
        assert "no policy was saved" in response.json()["detail"]
        assert client.get(
            f"/api/customers/{customer_id}/investment-policies"
        ).json() == []
    finally:
        app.dependency_overrides.clear()
