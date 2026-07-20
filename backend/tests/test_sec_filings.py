"""SEC filing provider tests use fixtures only and never call EDGAR."""
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402
from app.services import sec_filings  # noqa: E402


NOW = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def empty_sec_cache():
    sec_filings.clear_cache()
    yield
    sec_filings.clear_cache()


def cache_metadata(hit=False):
    return {
        "hit": hit,
        "fetched_at": NOW,
        "expires_at": NOW + timedelta(hours=6),
    }


def filing_summary(accession="0000320193-26-000010", filing_type="10-K"):
    return {
        "accession_number": accession,
        "filing_type": filing_type,
        "filing_date": date(2026, 6, 30),
        "report_date": date(2026, 6, 28),
        "accepted_at": datetime(2026, 7, 2, 16, 30, tzinfo=timezone.utc),
        "primary_document": "test.htm",
        "items": ["2.02"] if filing_type == "8-K" else [],
        "description": "Quarterly results" if filing_type == "8-K" else "Annual report",
        "is_earnings_related": filing_type == "8-K",
        "source_url": "https://www.sec.gov/Archives/edgar/data/320193/test.htm",
        "index_url": "https://www.sec.gov/Archives/edgar/data/320193/test-index.html",
    }


def test_recent_filings_normalize_supported_forms_and_earnings_8k(monkeypatch):
    payload = {
        "name": "Test Company",
        "filings": {
            "recent": {
                "accessionNumber": [
                    "0000320193-26-000003",
                    "0000320193-26-000002",
                    "0000320193-26-000001",
                    "0000320193-26-000000",
                ],
                "form": ["8-K", "10-Q", "10-K", "10-K/A"],
                "filingDate": ["2026-07-18", "2026-05-01", "2026-02-01", "2026-02-02"],
                "reportDate": ["2026-07-18", "2026-03-31", "2025-12-31", "2025-12-31"],
                "acceptanceDateTime": [
                    "2026-07-18T16:30:00.000Z",
                    "2026-05-01T16:30:00.000Z",
                    "2026-02-01T16:30:00.000Z",
                    "2026-02-02T16:30:00.000Z",
                ],
                "primaryDocument": ["results.htm", "quarter.htm", "annual.htm", "amend.htm"],
                "primaryDocDescription": [
                    "Results of Operations",
                    "Quarterly report",
                    "Annual report",
                    "Amendment",
                ],
                "items": ["2.02,9.01", "", "", ""],
            }
        },
    }
    monkeypatch.setattr(
        sec_filings,
        "_company_for_ticker",
        lambda ticker: {"ticker": "TEST", "cik": "0000320193", "company_name": "Test"},
    )
    monkeypatch.setattr(
        sec_filings,
        "_cached_json",
        lambda url, ttl: (payload, cache_metadata()),
    )

    result = sec_filings.list_filings("TEST")

    assert [item["filing_type"] for item in result["filings"]] == ["8-K", "10-Q", "10-K"]
    assert result["filings"][0]["is_earnings_related"] is True
    assert result["filings"][0]["items"] == ["2.02", "9.01"]
    assert result["filings"][0]["source_url"].endswith("/results.htm")
    assert result["source"]["provider"] == "SEC EDGAR"
    assert result["cache"]["fetched_at"] == NOW


def test_cached_json_reuses_original_fetch_timestamp(monkeypatch):
    calls = []

    class Response:
        status_code = 200
        headers = {}
        content = b'{"ok": true}'
        text = '{"ok": true}'

        def json(self):
            return {"ok": True}

    monkeypatch.setattr(sec_filings, "_request", lambda url: calls.append(url) or Response())

    first, first_cache = sec_filings._cached_json("https://example.test/sec", 60)
    second, second_cache = sec_filings._cached_json("https://example.test/sec", 60)

    assert first == second == {"ok": True}
    assert calls == ["https://example.test/sec"]
    assert first_cache["hit"] is False
    assert second_cache["hit"] is True
    assert second_cache["fetched_at"] == first_cache["fetched_at"]


def test_extract_sections_prefers_full_10k_sections_over_table_of_contents():
    filler = "Material disclosure sentence. " * 12
    document = f"""
    <html><body>
      <div>ITEM 1. Business {filler}</div>
      <div>ITEM 1A. Risk Factors {filler}</div>
      <div>ITEM 7. Management's Discussion and Analysis {filler}</div>
      <div>ITEM 8. Financial Statements {filler}</div>
      <h2>ITEM 1. BUSINESS</h2><p>We design test products. {filler}</p>
      <h2>ITEM 1A. RISK FACTORS</h2>
      <p>ACTUAL RISK DISCLOSURE. Supply constraints may affect operations. {filler}</p>
      <h2>ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS</h2>
      <p>Revenue grew due to subscriptions. {filler}</p>
      <h2>ITEM 8. FINANCIAL STATEMENTS</h2><p>Audited statements follow. {filler}</p>
      <h2>ITEM 9. CHANGES IN ACCOUNTANTS</h2><p>None.</p>
    </body></html>
    """

    sections = sec_filings.extract_sections(
        document,
        "10-K",
        "https://www.sec.gov/example.htm",
    )

    assert [section["item"] for section in sections] == ["1", "1A", "7", "8"]
    risk = next(section for section in sections if section["item"] == "1A")
    assert "ACTUAL RISK DISCLOSURE" in risk["text"]
    assert risk["source_url"] == "https://www.sec.gov/example.htm"


def test_earnings_8k_includes_sec_hosted_ex99_release(monkeypatch):
    summary = filing_summary(filing_type="8-K")
    index_document = """
    <table class="tableFile">
      <tr><th>Seq</th><th>Description</th><th>Document</th><th>Type</th></tr>
      <tr>
        <td>1</td><td>Earnings release announcing quarterly results</td>
        <td><a href="/Archives/edgar/data/320193/fixture/ex991.htm">ex991.htm</a></td>
        <td>EX-99.1</td>
      </tr>
      <tr>
        <td>2</td><td>External decoy</td>
        <td><a href="https://example.com/ex992.htm">ex992.htm</a></td>
        <td>EX-99.2</td>
      </tr>
    </table>
    """
    primary_document = """
    <h2>ITEM 2.02. Results of Operations and Financial Condition</h2>
    <p>The earnings release is furnished as Exhibit 99.1. This paragraph contains
    enough text for extraction.</p>
    <h2>ITEM 9.01. Financial Statements and Exhibits</h2>
    <p>Exhibit 99.1 is incorporated into this report. This paragraph contains
    enough text for extraction.</p>
    """
    exhibit_document = """
    <h1>Quarterly earnings release</h1>
    <p>Net sales increased nine percent and services revenue reached a record.
    Gross margin expanded due to a favorable services mix. This exhibit contains
    the detailed operating results referenced by Item 2.02.</p>
    """
    monkeypatch.setattr(
        sec_filings,
        "_load_company_filings",
        lambda ticker: (
            {"ticker": "TEST", "cik": "0000320193", "company_name": "Test Company"},
            [summary],
            cache_metadata(True),
            "https://data.sec.gov/submissions/CIK0000320193.json",
        ),
    )

    def document_for(url):
        if url == summary["index_url"]:
            return index_document, cache_metadata(True)
        if url.endswith("ex991.htm"):
            return exhibit_document, cache_metadata(True)
        return primary_document, cache_metadata(True)

    monkeypatch.setattr(sec_filings, "_cached_document", document_for)

    detail = sec_filings.get_filing("TEST", summary["accession_number"])

    exhibit = next(section for section in detail["sections"] if section["item"] == "EX-99.1")
    assert "Net sales increased" in exhibit["text"]
    assert exhibit["source_url"].startswith("https://www.sec.gov/Archives/")
    assert all("example.com" not in section["source_url"] for section in detail["sections"])
    assert detail["source"]["source_url"] == summary["index_url"]


def test_question_fallback_selects_relevant_section_and_returns_original_citation(monkeypatch):
    detail = {
        "filing": filing_summary(),
        "sections": [
            {
                "section_id": "risk-factors",
                "title": "Risk factors",
                "text": "Supply interruptions could delay production and increase costs.",
                "source_url": "https://www.sec.gov/example.htm",
            },
            {
                "section_id": "mda",
                "title": "Management's discussion and analysis",
                "text": "Revenue increased 18 percent because subscription demand expanded.",
                "source_url": "https://www.sec.gov/example.htm",
            },
        ],
    }
    monkeypatch.setattr(sec_filings, "get_filing", lambda ticker, accession: detail)
    monkeypatch.setattr(sec_filings.ai, "answer_filing_question", lambda *args, **kwargs: None)

    result = sec_filings.answer_question(
        "TEST",
        "0000320193-26-000010",
        "Why did revenue increase?",
    )

    assert result["ai_used"] is False
    assert result["citations"][0]["section_id"] == "mda"
    assert "Revenue increased" in result["citations"][0]["quote"]
    assert result["answer"]["provider"] == "FinSight"
    assert result["answer"]["source_url"] == (
        "https://www.sec.gov/Archives/edgar/data/320193/test.htm"
    )


def test_filing_routes_expose_list_detail_questions_and_friendly_errors(monkeypatch):
    source = {
        "provider": "SEC EDGAR",
        "source": "fixture",
        "as_of_date": date(2026, 6, 30),
        "fetched_at": NOW,
        "freshness_status": "fresh",
        "confidence": 1.0,
        "source_url": "https://www.sec.gov/example.htm",
    }
    summary = filing_summary()
    listing = {
        "ticker": "TEST",
        "company_name": "Test Company",
        "cik": "0000320193",
        "filings": [summary],
        "source": source,
        "cache": cache_metadata(),
    }
    detail = {
        "ticker": "TEST",
        "company_name": "Test Company",
        "cik": "0000320193",
        "filing": summary,
        "sections": [{
            "section_id": "item-1a",
            "item": "1A",
            "title": "Risk factors",
            "text": "A cited risk.",
            "character_count": 13,
            "truncated": False,
            "source_url": "https://www.sec.gov/example.htm",
        }],
        "source": source,
        "cache": cache_metadata(),
    }
    answer = {
        "ticker": "TEST",
        "accession_number": summary["accession_number"],
        "question": "What is the risk?",
        "answer": {"claim": "A cited risk.", **source},
        "citations": [{
            "section_id": "item-1a",
            "section_title": "Risk factors",
            "quote": "A cited risk.",
            "source_url": "https://www.sec.gov/example.htm",
        }],
        "answered_at": NOW,
        "ai_used": False,
    }
    monkeypatch.setattr("app.main.sec_filings.list_filings", lambda ticker, limit: listing)
    monkeypatch.setattr("app.main.sec_filings.get_filing", lambda ticker, accession: detail)
    monkeypatch.setattr("app.main.sec_filings.answer_question", lambda *args, **kwargs: answer)
    client = TestClient(app)

    assert client.get("/api/filings/TEST").json()["filings"][0]["filing_type"] == "10-K"
    detail_response = client.get(
        f"/api/filings/TEST/{summary['accession_number']}"
    ).json()
    assert detail_response["sections"][0]["item"] == "1A"
    question_response = client.post(
        f"/api/filings/TEST/{summary['accession_number']}/questions",
        json={"question": "What is the risk?", "lang": "en"},
    )
    assert question_response.status_code == 200
    assert question_response.json()["citations"][0]["quote"] == "A cited risk."

    monkeypatch.setattr(
        "app.main.sec_filings.list_filings",
        lambda ticker, limit: (_ for _ in ()).throw(
            sec_filings.SecRateLimitError("SEC is busy")
        ),
    )
    error_response = client.get("/api/filings/TEST")
    assert error_response.status_code == 503
    assert error_response.headers["retry-after"] == "60"
