"""Persistent watchlist, saved-research, and change-report API tests."""

import sys
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402


NOW = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
PROFILE = {
    "experience_level": "intermediate",
    "research_horizon": "one_to_three_years",
    "priorities": ["growth", "stability"],
    "risk_comfort": "medium",
    "preferred_report_depth": "standard",
    "preferred_language": "en",
    "industries_of_interest": ["Technology"],
}


def _point(value, display_value=None):
    return {
        "value": value,
        "unit": None,
        "display_value": display_value,
        "provider": "Test provider",
        "source": "Research fixture",
        "as_of_date": date(2026, 7, 20).isoformat(),
        "fetched_at": NOW.isoformat(),
        "freshness_status": "fresh",
        "confidence": 0.95,
        "source_url": "https://example.com/evidence",
    }


def _claim(text):
    return {
        "claim": text,
        "provider": "FinSight rules",
        "source": "Research fixture",
        "as_of_date": date(2026, 7, 20).isoformat(),
        "fetched_at": NOW.isoformat(),
        "freshness_status": "fresh",
        "confidence": 0.9,
        "source_url": "https://example.com/evidence",
    }


def _insight(code, kind, severity):
    return {
        "code": code,
        "kind": kind,
        "title": _claim(code.replace("_", " ").title()),
        "severity": severity,
        "explanation": _claim("Deterministic test explanation."),
        "evidence": [],
        "highlighted": False,
    }


def _analysis(insights):
    return {
        "ticker": "TEST",
        "insights": insights,
        "benchmarks": {
            "industry": "Software",
            "sector": "Technology",
            "selected_peers": [],
            "metrics": [],
            "methodology": _claim("Test methodology."),
            "limitations": [],
        },
        "ai_narrative": None,
        "presentation": {},
        "disclaimer": "Educational research only.",
    }


def _news(title, link):
    return {
        "title": _claim(title),
        "publisher": "Example News",
        "link": link,
        "published_at": NOW.isoformat(),
    }


def _filing(accession, filing_type="10-Q"):
    return {
        "accession_number": accession,
        "filing_type": filing_type,
        "filing_date": date(2026, 7, 20).isoformat(),
        "report_date": date(2026, 6, 30).isoformat(),
        "accepted_at": NOW.isoformat(),
        "primary_document": "report.htm",
        "items": ["Part I"],
        "description": "Quarterly report",
        "is_earnings_related": True,
        "source_url": f"https://sec.example/{accession}",
        "index_url": f"https://sec.example/{accession}/index",
    }


def _snapshot(
    *,
    price=100.0,
    revenue_growth=0.10,
    profit_margin=0.20,
    news=None,
    filings=None,
    insights=None,
    assumption_status="supported",
):
    return {
        "captured_at": NOW.isoformat(),
        "overview": {
            "ticker": "TEST",
            "name": "Test Company",
            "price": _point(price, f"${price:.2f}"),
            "revenue_growth": _point(revenue_growth),
            "profit_margin": _point(profit_margin),
        },
        "analysis": _analysis(insights or []),
        "news": {
            "ticker": "TEST",
            "items": news or [],
            "ai_summary": None,
        },
        "filings": {
            "ticker": "TEST",
            "company_name": "Test Company",
            "cik": "0000000001",
            "filings": filings or [],
            "source": {
                key: value for key, value in _claim("source").items() if key != "claim"
            },
            "cache": {
                "hit": False,
                "fetched_at": NOW.isoformat(),
                "expires_at": datetime(2026, 7, 20, 18, 0, tzinfo=timezone.utc).isoformat(),
            },
        },
        "thesis_assumptions": [
            {
                "description": "Revenue growth stays positive",
                "current_status": assumption_status,
                "metric_key": "revenue_growth",
                "target_value": "0",
            }
        ],
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


def test_watchlists_persist_groups_and_normalized_items():
    client = _client()
    try:
        customer_id = _create_customer(client)
        first = client.post(
            f"/api/customers/{customer_id}/watchlists",
            json={"name": "Core research"},
        )
        assert first.status_code == 201
        assert first.json()["is_default"] is True
        watchlist_id = first.json()["id"]

        added = client.post(
            f"/api/customers/{customer_id}/watchlists/{watchlist_id}/items",
            json={"ticker": "test", "notes": "Track durable growth"},
        )
        assert added.status_code == 201
        assert added.json()["items"][0]["ticker"] == "TEST"
        duplicate = client.post(
            f"/api/customers/{customer_id}/watchlists/{watchlist_id}/items",
            json={"ticker": "TEST"},
        )
        assert duplicate.status_code == 409

        second = client.post(
            f"/api/customers/{customer_id}/watchlists",
            json={"name": "Ideas", "is_default": True},
        )
        assert second.status_code == 201
        listed = client.get(f"/api/customers/{customer_id}/watchlists")
        assert listed.status_code == 200
        assert [item["name"] for item in listed.json()] == ["Ideas", "Core research"]
        assert sum(item["is_default"] for item in listed.json()) == 1

        removed = client.delete(
            f"/api/customers/{customer_id}/watchlists/{watchlist_id}/items/TEST"
        )
        assert removed.status_code == 200
        assert removed.json()["items"] == []

        deleted = client.delete(
            f"/api/customers/{customer_id}/watchlists/{second.json()['id']}"
        )
        assert deleted.status_code == 204
        remaining = client.get(f"/api/customers/{customer_id}/watchlists").json()
        assert remaining[0]["is_default"] is True
    finally:
        app.dependency_overrides.clear()


def test_saved_research_sessions_round_trip_and_delete():
    client = _client()
    try:
        customer_id = _create_customer(client)
        saved = client.post(
            f"/api/customers/{customer_id}/research-sessions",
            json={
                "title": "Initial TEST research",
                "language": "en",
                "snapshot": _snapshot(),
            },
        )
        assert saved.status_code == 201, saved.text
        session_id = saved.json()["id"]
        assert saved.json()["snapshot"]["overview"]["ticker"] == "TEST"
        assert saved.json()["snapshot"]["audit"]["checks_performed"] == [
            "unsupported_claim",
            "stale_evidence",
            "missing_citation",
            "conflicting_sources",
            "incorrect_unit",
            "inconsistent_number",
        ]

        listed = client.get(
            f"/api/customers/{customer_id}/research-sessions?ticker=TEST"
        )
        assert listed.status_code == 200
        assert listed.json()[0]["id"] == session_id
        detail = client.get(
            f"/api/customers/{customer_id}/research-sessions/{session_id}"
        )
        assert detail.status_code == 200
        assert detail.json()["snapshot"]["thesis_assumptions"][0][
            "current_status"
        ] == "supported"

        deleted = client.delete(
            f"/api/customers/{customer_id}/research-sessions/{session_id}"
        )
        assert deleted.status_code == 204
        assert client.get(
            f"/api/customers/{customer_id}/research-sessions/{session_id}"
        ).status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_saved_research_reaudits_and_removes_unsupported_generated_conclusions():
    client = _client()
    try:
        customer_id = _create_customer(client)
        snapshot = _snapshot()
        snapshot["news"]["ai_summary"] = {
            **_claim("Unsupported generated conclusion."),
            "provider": "Anthropic",
            "source": "test model",
            "generated": True,
            "citations": [],
            "statements": [
                {"text": "Unsupported generated conclusion.", "citations": []}
            ],
        }

        saved = client.post(
            f"/api/customers/{customer_id}/research-sessions",
            json={"language": "en", "snapshot": snapshot},
        )

        assert saved.status_code == 201, saved.text
        result = saved.json()["snapshot"]
        assert result["news"]["ai_summary"] is None
        assert result["audit"]["status"] == "blocked"
        assert result["audit"]["blocked_statements"] == 1
    finally:
        app.dependency_overrides.clear()


def test_what_changed_compares_all_six_research_categories():
    client = _client()
    try:
        customer_id = _create_customer(client)
        baseline = _snapshot(
            news=[_news("Existing headline", "https://news.example/existing")],
            filings=[_filing("0001-26-000001")],
            insights=[
                _insight("competition", "risk", "low"),
                _insight("growth_runway", "opportunity", "high"),
            ],
        )
        saved = client.post(
            f"/api/customers/{customer_id}/research-sessions",
            json={"language": "en", "snapshot": baseline},
        )
        assert saved.status_code == 201, saved.text

        current = _snapshot(
            price=110.0,
            revenue_growth=0.18,
            profit_margin=0.15,
            news=[
                _news("Existing headline", "https://news.example/existing"),
                _news("New product launch", "https://news.example/product"),
            ],
            filings=[_filing("0001-26-000001"), _filing("0001-26-000002", "8-K")],
            insights=[
                _insight("competition", "risk", "high"),
                _insight("new_regulation", "risk", "medium"),
            ],
            assumption_status="challenged",
        )
        changed = client.post(
            f"/api/customers/{customer_id}/what-changed/TEST",
            json={"snapshot": current},
        )
        assert changed.status_code == 200, changed.text
        payload = changed.json()
        assert payload["has_baseline"] is True
        metrics = {item["metric_key"]: item for item in payload["financial_metrics"]}
        assert metrics["price"]["direction"] == "changed"
        assert metrics["revenue_growth"]["direction"] == "improved"
        assert metrics["profit_margin"]["direction"] == "worsened"
        assert [item["item"]["title"]["claim"] for item in payload["news"]] == [
            "New product launch"
        ]
        assert payload["filings"][0]["accession_number"] == "0001-26-000002"
        risks = {item["code"]: item for item in payload["risk_signals"]}
        assert risks["competition"]["direction"] == "worsened"
        assert risks["new_regulation"]["direction"] == "new"
        opportunities = {item["code"]: item for item in payload["opportunity_signals"]}
        assert opportunities["growth_runway"]["direction"] == "worsened"
        assert payload["thesis_assumptions"][0]["direction"] == "worsened"
        assert payload["summary"]["new"] >= 3
        assert payload["summary"]["worsened"] >= 3

        partial = _snapshot()
        partial["analysis"] = None
        unavailable_analysis = client.post(
            f"/api/customers/{customer_id}/what-changed/TEST",
            json={"snapshot": partial},
        )
        assert unavailable_analysis.status_code == 200
        assert unavailable_analysis.json()["risk_signals"] == []
        assert unavailable_analysis.json()["opportunity_signals"] == []
    finally:
        app.dependency_overrides.clear()


def test_what_changed_requires_a_saved_baseline_and_matching_ticker():
    client = _client()
    try:
        customer_id = _create_customer(client)
        no_baseline = client.post(
            f"/api/customers/{customer_id}/what-changed/TEST",
            json={"snapshot": _snapshot()},
        )
        assert no_baseline.status_code == 200
        assert no_baseline.json()["has_baseline"] is False
        assert no_baseline.json()["financial_metrics"] == []

        mismatched = _snapshot()
        mismatched["overview"]["ticker"] = "OTHER"
        response = client.post(
            f"/api/customers/{customer_id}/what-changed/TEST",
            json={"snapshot": mismatched},
        )
        assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_workspace_records_are_scoped_to_the_owning_customer():
    client = _client()
    try:
        owner_id = _create_customer(client)
        other_id = _create_customer(client)
        watchlist = client.post(
            f"/api/customers/{owner_id}/watchlists",
            json={"name": "Private research"},
        ).json()
        research = client.post(
            f"/api/customers/{owner_id}/research-sessions",
            json={"language": "en", "snapshot": _snapshot()},
        ).json()

        assert client.post(
            f"/api/customers/{other_id}/watchlists/{watchlist['id']}/items",
            json={"ticker": "TEST"},
        ).status_code == 404
        assert client.get(
            f"/api/customers/{other_id}/research-sessions/{research['id']}"
        ).status_code == 404
    finally:
        app.dependency_overrides.clear()
