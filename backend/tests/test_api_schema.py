"""API contract tests for provenance-aware response schemas."""
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402


NOW = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)


def meta(provider="Yahoo Finance", source="test fixture", confidence=0.9):
    return {
        "provider": provider,
        "source": source,
        "as_of_date": date(2026, 7, 19),
        "fetched_at": NOW,
        "freshness_status": "fresh",
        "confidence": confidence,
        "source_url": "https://example.com/source",
    }


def point(value, unit=None):
    return {"value": value, "unit": unit, "display_value": None, **meta()}


def claim(text, provider="FinSight"):
    return {"claim": text, **meta(provider=provider, confidence=0.8)}


def overview(ticker):
    return {
        "ticker": ticker,
        "name": f"{ticker} Corp",
        "currency": "USD",
        "price": point(100.0, "USD"),
        "trailing_pe": point(45.0),
        "market_cap": point(1_000_000, "USD"),
        "summary": claim("Company profile.", provider="Yahoo Finance"),
    }


def assert_provenance(payload):
    required = {
        "provider",
        "source",
        "as_of_date",
        "fetched_at",
        "freshness_status",
        "confidence",
        "source_url",
    }
    assert required <= payload.keys()


def test_openapi_exposes_standardized_data_point_and_evidence_contracts():
    schema = app.openapi()
    models = schema["components"]["schemas"]
    provenance_fields = {
        "provider",
        "source",
        "as_of_date",
        "fetched_at",
        "freshness_status",
        "confidence",
    }

    assert provenance_fields <= set(models["DataPoint"]["required"])
    assert provenance_fields <= set(models["Evidence"]["required"])
    assert "value" in models["DataPoint"]["required"]
    assert "claim" in models["Evidence"]["required"]
    assert models["Overview"]["properties"]["price"]["anyOf"][0]["$ref"].endswith("/DataPoint")
    assert models["PricePoint"]["properties"]["close"]["$ref"].endswith("/DataPoint")
    narrative_ref = models["AnalysisResponse"]["properties"]["ai_narrative"]["anyOf"][0]
    assert narrative_ref["$ref"].endswith("/Evidence")


def test_overview_analysis_comparison_and_news_responses_include_provenance(monkeypatch):
    monkeypatch.setattr("app.main.market_data.get_overview", overview)
    monkeypatch.setattr(
        "app.main.market_data.get_history",
        lambda ticker, period: [{"date": "2026-07-19", "close": point(99.5, "price")}],
    )
    monkeypatch.setattr(
        "app.main.market_data.get_news",
        lambda ticker: [
            {
                "title": claim("A sourced headline", provider="Example News"),
                "publisher": "Example News",
                "link": "https://example.com/story",
                "published_at": "2026-07-19T12:00:00Z",
            }
        ],
    )
    monkeypatch.setattr(
        "app.main.ai.summarize_news",
        lambda ticker, items, lang="en": claim("AI headline themes", provider="Anthropic"),
    )
    monkeypatch.setattr(
        "app.main.ai.narrate_analysis",
        lambda ticker, metrics, insights, lang="en": claim("AI analysis", provider="Anthropic"),
    )
    client = TestClient(app)

    overview_response = client.get("/api/stocks/TEST")
    assert overview_response.status_code == 200
    assert_provenance(overview_response.json()["price"])

    history_response = client.get("/api/stocks/TEST/history?period=1mo")
    assert history_response.status_code == 200
    assert_provenance(history_response.json()["points"][0]["close"])

    analysis_response = client.get("/api/analysis/TEST")
    assert analysis_response.status_code == 200
    analysis = analysis_response.json()
    assert_provenance(analysis["ai_narrative"])
    assert_provenance(analysis["insights"][0]["title"])
    assert_provenance(analysis["insights"][0]["explanation"])
    assert_provenance(analysis["insights"][0]["evidence"][0]["value"])
    assert_provenance(analysis["insights"][0]["evidence"][0]["benchmark"])

    compare_response = client.get("/api/compare?tickers=AAA,BBB")
    assert compare_response.status_code == 200
    compare = compare_response.json()
    assert_provenance(compare["rows"][0]["values"]["AAA"])
    assert_provenance(compare["rows"][0]["best"])

    news_response = client.get("/api/news/TEST")
    assert news_response.status_code == 200
    news = news_response.json()
    assert_provenance(news["items"][0]["title"])
    assert_provenance(news["ai_summary"])
