"""Evidence Auditor rules, blocking behavior, and API contract."""
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402
from app.models.schemas import ResearchReportDraft  # noqa: E402
from app.services import ai, evidence_auditor, valuations  # noqa: E402


NOW = datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc)


def meta(
    *,
    provider="Yahoo Finance",
    source="test fixture",
    freshness="fresh",
    as_of=date(2026, 7, 21),
):
    return {
        "provider": provider,
        "source": source,
        "as_of_date": as_of,
        "fetched_at": NOW,
        "freshness_status": freshness,
        "confidence": 0.9,
        "source_url": "https://example.com/source",
    }


def point(value, unit=None, **metadata):
    return {
        "value": value,
        "unit": unit,
        "display_value": None,
        **meta(**metadata),
    }


def claim(text, **metadata):
    return {"claim": text, **meta(**metadata)}


def generated_claim(text, citations):
    return {
        **claim(text, provider="Anthropic", source="claude-test"),
        "generated": True,
        "citations": citations,
        "statements": [{"text": text, "citations": citations}],
    }


def report(*, summary=None, title=None, overview_update=None, valuation=None):
    overview = {
        "ticker": "TEST",
        "name": "Test Corp",
        "currency": "USD",
        "price": point(100.0, "USD"),
    }
    overview.update(overview_update or {})
    return ResearchReportDraft.model_validate(
        {
            "captured_at": NOW,
            "overview": overview,
            "news": {
                "ticker": "TEST",
                "items": [
                    {
                        "title": title or claim("Revenue rose 15% year over year."),
                        "publisher": "Example News",
                        "link": "https://example.com/story",
                        "published_at": NOW.isoformat(),
                    }
                ],
                "ai_summary": summary,
            },
            "valuation": valuation,
        }
    )


def issue_codes(result):
    return {issue.code.value for issue in result.audit.issues}


def valuation_inputs(total_revenue=120.0):
    return {
        "ticker": "TEST",
        "currency": "USD",
        "total_revenue": point(
            total_revenue,
            "USD",
            provider="Second Provider",
            source="second fixture",
        ),
        "free_cash_flow": point(12.0, "USD"),
        "total_cash": point(10.0, "USD"),
        "total_debt": point(5.0, "USD"),
        "shares_outstanding": point(10.0, "shares"),
        "current_price": point(10.0, "USD"),
        "trailing_eps": point(1.0, "USD"),
        "revenue_growth": point(0.05, "ratio"),
        "free_cash_flow_margin": point(0.10, "ratio"),
    }


def test_supported_cited_statement_passes_and_remains_visible():
    draft = report(
        summary=generated_claim(
            "Revenue rose 15% year over year.",
            ["news.items.0.title"],
        )
    )

    result = evidence_auditor.audit_research_report(draft)

    assert result.audit.status.value == "passed"
    assert result.audit.blocked_statements == 0
    assert result.report.news.ai_summary.claim == "Revenue rose 15% year over year."
    assert result.audit.factual_conclusions_allowed is True


def test_ai_citation_envelope_is_parsed_into_independent_statements():
    raw = (
        '{"statements":['
        '{"text":"Growth was 15%.","citations":["overview.revenue_growth"]},'
        '{"text":"Margins improved.","citations":["analysis.insights.0.explanation"]}'
        "]}"
    )

    text, statements, citations = ai._parse_cited_response(raw)

    assert text == "Growth was 15%. Margins improved."
    assert len(statements) == 2
    assert citations == [
        "overview.revenue_growth",
        "analysis.insights.0.explanation",
    ]


def test_numeric_support_normalizes_ratios_but_not_unrelated_currency_values():
    assert evidence_auditor._unsupported_numbers(
        "Growth was 15%.",
        [point(0.15, "ratio")],
    ) == []
    assert evidence_auditor._unsupported_numbers(
        "Revenue was $10,000.",
        [point(100.0, "USD")],
    ) == [10_000.0]


def test_missing_citation_is_blocked_from_the_sanitized_report():
    draft = report(summary=generated_claim("Revenue accelerated.", []))

    result = evidence_auditor.audit_research_report(draft)

    assert result.audit.status.value == "blocked"
    assert result.report.news.ai_summary is None
    assert result.audit.blocked_statements == 1
    assert {"missing_citation", "unsupported_claim"} <= issue_codes(result)
    assert result.audit.factual_conclusions_allowed is False


def test_number_not_present_in_cited_evidence_is_blocked():
    draft = report(
        summary=generated_claim(
            "Revenue rose 99% year over year.",
            ["news.items.0.title"],
        )
    )

    result = evidence_auditor.audit_research_report(draft)

    assert result.report.news.ai_summary is None
    assert "inconsistent_number" in issue_codes(result)
    assert "unsupported_claim" in issue_codes(result)


def test_generated_conclusion_cannot_launder_support_from_another_section():
    draft = report(
        overview_update={"revenue_growth": point(0.15, "ratio")},
        summary=generated_claim(
            "Revenue rose 15% year over year.",
            ["overview.revenue_growth"],
        ),
    )

    result = evidence_auditor.audit_research_report(draft)

    assert result.report.news.ai_summary is None
    assert "unsupported_claim" in issue_codes(result)


def test_stale_evidence_and_incorrect_units_are_reported_and_bad_support_is_blocked():
    draft = report(
        title=claim(
            "Revenue rose 15% year over year.",
            freshness="stale",
            as_of=date(2025, 1, 1),
        ),
        overview_update={"revenue_growth": point(0.15, "USD")},
        summary=generated_claim(
            "Revenue rose 15% year over year.",
            ["overview.revenue_growth"],
        ),
    )

    result = evidence_auditor.audit_research_report(draft)

    assert {"stale_evidence", "incorrect_unit", "unsupported_claim"} <= issue_codes(result)
    assert result.report.news.ai_summary is None


def test_same_date_source_conflicts_and_inconsistent_numbers_are_detected():
    valuation = valuations.build_valuation(
        "TEST",
        valuation_inputs(),
        {"metrics": []},
    )
    draft = report(
        overview_update={"total_revenue": point(100.0, "USD")},
        valuation=valuation,
    )

    result = evidence_auditor.audit_research_report(draft)

    assert {"conflicting_sources", "inconsistent_number"} <= issue_codes(result)
    assert result.audit.status.value == "warning"


def test_audit_endpoint_returns_only_the_sanitized_report_and_contract():
    client = TestClient(app)
    draft = report(summary=generated_claim("Unsupported conclusion.", []))

    response = client.post(
        "/api/reports/audit",
        json=draft.model_dump(mode="json"),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["report"]["news"]["ai_summary"] is None
    assert payload["audit"]["status"] == "blocked"
    schema = app.openapi()
    assert "/api/reports/audit" in schema["paths"]
    response_ref = schema["paths"]["/api/reports/audit"]["post"]["responses"]["200"][
        "content"
    ]["application/json"]["schema"]["$ref"]
    assert response_ref.endswith("/ResearchReportAuditResponse")
    models = schema["components"]["schemas"]
    assert models["Evidence"]["properties"]["statements"]["items"][
        "$ref"
    ].endswith("/EvidenceStatement")
    assert models["ResearchReportAuditResponse"]["properties"]["audit"][
        "$ref"
    ].endswith("/EvidenceAudit")


def test_comparison_reports_use_the_same_audit_gate():
    client = TestClient(app)
    comparison = {
        "captured_at": NOW.isoformat(),
        "comparison": {
            "tickers": ["AAA", "BBB"],
            "rows": [
                {
                    "metric": "revenue_growth",
                    "label": "Revenue growth",
                    "values": {
                        "AAA": point(0.10, "ratio"),
                        "BBB": point(0.15, "ratio"),
                    },
                    "best": claim("BBB", provider="FinSight"),
                    "higher_is_better": True,
                }
            ],
        },
    }

    response = client.post(
        "/api/reports/audit",
        json=ResearchReportDraft.model_validate(comparison).model_dump(mode="json"),
    )

    assert response.status_code == 200, response.text
    assert response.json()["report"]["comparison"]["tickers"] == ["AAA", "BBB"]
    assert response.json()["audit"]["status"] == "passed"
