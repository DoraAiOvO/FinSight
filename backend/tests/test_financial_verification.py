import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.models.schemas import (
    AccountingStandard,
    CompanyEntity,
    DataSource,
    DataSourceType,
    FinancialMetric,
    FinancialPeriod,
    Listing,
    VerificationStatus,
)
from app.services.financial_verification import (
    build_financial_evidence,
    normalize_sec_payloads,
    normalized_ai_evidence,
)
from app.main import app
from app.services import ai


FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "financial_verification_golden.json").read_text()
)
NOW = datetime(2026, 4, 1, tzinfo=timezone.utc)


def build_case(case):
    entity_id = f"sec:{case['cik']}"
    listing_id = f"listing:{case['ticker']}"
    company = CompanyEntity(
        entity_id=entity_id,
        legal_name=f"{case['ticker']} Golden Company",
        cik=case["cik"],
        country="US",
    )
    listing = Listing(
        listing_id=listing_id,
        entity_id=entity_id,
        ticker=case["ticker"],
        exchange="NYSE",
        currency=case["observations"][0]["currency"],
    )
    sources = {}
    periods = {}
    metrics = []
    base_period = case["period"]
    for index, observation in enumerate(case["observations"]):
        provider = observation["provider"]
        source_id = f"source:{case['id']}:{provider}"
        sources.setdefault(
            source_id,
            DataSource(
                data_source_id=source_id,
                provider=provider,
                source_type=(
                    DataSourceType.SEC_COMPANY_FACTS
                    if provider == "SEC EDGAR"
                    else DataSourceType.YAHOO_FINANCE
                ),
                source_document=(
                    f"https://www.sec.gov/Archives/{case['id']}"
                    if provider == "SEC EDGAR"
                    else f"https://finance.yahoo.com/quote/{case['ticker']}"
                ),
                source_url=None,
                is_official=provider == "SEC EDGAR",
                fetched_at=NOW,
            ),
        )
        period_payload = {
            **base_period,
            **{
                key: observation[key]
                for key in ("period_type", "period_start", "fiscal_quarter")
                if key in observation
            },
        }
        period_id = (
            f"period:{period_payload['period_type']}:{period_payload['period_end']}:"
            f"{period_payload['fiscal_quarter']}"
        )
        periods.setdefault(
            period_id,
            FinancialPeriod(
                period_id=period_id,
                period_type=period_payload["period_type"],
                period_start=period_payload["period_start"],
                period_end=period_payload["period_end"],
                fiscal_year=period_payload["fiscal_year"],
                fiscal_quarter=period_payload["fiscal_quarter"],
            ),
        )
        metrics.append(
            FinancialMetric(
                metric_id=f"metric:{case['id']}:{index}",
                entity_id=entity_id,
                listing_id=listing_id,
                financial_period_id=period_id,
                data_source_id=source_id,
                metric_key=observation["metric_key"],
                value=observation["value"],
                unit=observation["unit"],
                currency=observation["currency"],
                period_type=period_payload["period_type"],
                period_start=period_payload["period_start"],
                period_end=period_payload["period_end"],
                fiscal_year=period_payload["fiscal_year"],
                fiscal_quarter=period_payload["fiscal_quarter"],
                filing_date=(
                    period_payload["filing_date"] if provider == "SEC EDGAR" else None
                ),
                accounting_standard=(
                    case["accounting_standard"] if provider == "SEC EDGAR" else "UNKNOWN"
                ),
                provider=provider,
                source_document=sources[source_id].source_document,
                source_concept=observation["concept"],
                fetched_at=NOW,
                verification_status=(
                    "OFFICIAL" if provider == "SEC EDGAR" else "SINGLE_SOURCE"
                ),
            )
        )
    return build_financial_evidence(
        company,
        [listing],
        periods.values(),
        sources.values(),
        metrics,
        now=NOW,
    )


def selected(evidence, key, period_type=None):
    metric_map = {item.metric_id: item for item in evidence.metrics}
    matches = [
        (result, metric_map[result.selected_metric_id])
        for result in evidence.verification_results
        if result.metric_key == key and result.selected_metric_id
    ]
    if period_type:
        matches = [item for item in matches if item[1].period_type.value == period_type]
    assert matches
    return matches[0]


def test_golden_numeric_matching_and_official_selection():
    case = FIXTURE["cases"][0]
    evidence = build_case(case)
    result, metric = selected(evidence, "total_revenue", "ANNUAL")
    assert result.verification_status.value == case["expected"]["total_revenue_status"]
    assert metric.value == case["expected"]["selected_total_revenue"]
    assert metric.provider == "SEC EDGAR"
    assert len(result.candidate_metric_ids) == 2


def test_golden_derived_calculations_have_visible_formulas():
    case = FIXTURE["cases"][0]
    evidence = build_case(case)
    _, margin = selected(evidence, "profit_margin", "ANNUAL")
    _, free_cash_flow = selected(evidence, "free_cash_flow", "ANNUAL")
    assert margin.value == pytest.approx(case["expected"]["profit_margin"])
    assert margin.calculation_formula == "net_income / total_revenue"
    assert free_cash_flow.value == pytest.approx(case["expected"]["free_cash_flow"])
    assert free_cash_flow.calculation_formula == "operating_cash_flow - capital_expenditure"


def test_golden_conflict_preserves_both_values_and_official_primary():
    case = FIXTURE["cases"][1]
    evidence = build_case(case)
    result, metric = selected(evidence, "total_assets", "INSTANT")
    assert result.verification_status.value == case["expected"]["status"]
    assert metric.value == case["expected"]["selected_total_assets"]
    assert len(evidence.conflicts) == 1
    assert len(evidence.conflicts[0].values) == case["expected"]["preserved_value_count"]
    assert sorted(evidence.conflicts[0].values) == [5000.0, 5250.0]
    assert not normalized_ai_evidence(evidence)


def test_golden_period_alignment_does_not_compare_annual_with_quarter():
    case = FIXTURE["cases"][2]
    evidence = build_case(case)
    annual, _ = selected(evidence, "total_revenue", "ANNUAL")
    quarter, _ = selected(evidence, "total_revenue", "QUARTER")
    assert annual.verification_status.value == case["expected"]["annual_status"]
    assert quarter.verification_status.value == case["expected"]["quarter_status"]
    assert len(evidence.conflicts) == case["expected"]["conflict_count"]
    assert case["expected"]["missing_metric_key"] in evidence.missing_metric_keys


@pytest.mark.parametrize(
    "changes",
    [
        {"value": float("nan")},
        {"unit": "ratio", "currency": "USD"},
        {"period_start": "2026-01-01", "period_end": "2025-12-31"},
        {"accounting_standard": "UNKNOWN"},
    ],
)
def test_financial_metric_rejects_non_finite_unit_currency_period_and_accounting(changes):
    base = {
        "metric_id": "metric:validation",
        "entity_id": "sec:0000000001",
        "listing_id": "listing:VAL",
        "financial_period_id": "period:validation",
        "data_source_id": "source:validation",
        "metric_key": "total_revenue",
        "value": 100.0,
        "unit": "currency",
        "currency": "USD",
        "period_type": "ANNUAL",
        "period_start": "2025-01-01",
        "period_end": "2025-12-31",
        "fiscal_year": 2025,
        "fiscal_quarter": None,
        "filing_date": "2026-02-01",
        "accounting_standard": "US_GAAP",
        "provider": "SEC EDGAR",
        "source_document": "https://sec.example/filing",
        "source_concept": "us-gaap:Revenue",
        "fetched_at": NOW,
        "verification_status": "OFFICIAL",
    }
    with pytest.raises(ValidationError):
        FinancialMetric.model_validate({**base, **changes})


def test_sec_company_facts_and_submissions_normalize_to_official_metric():
    company_facts = {
        "cik": "0000000404",
        "company_name": "Fixture SEC Company",
        "source_url": "https://data.sec.gov/api/xbrl/companyfacts/CIK0000000404.json",
        "fetched_at": NOW,
        "facts": {
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {
                        "USD": [{
                            "start": "2025-01-01", "end": "2025-12-31",
                            "val": 321.0, "accn": "0000000404-26-000001",
                            "fy": 2025, "fp": "FY", "form": "10-K",
                            "filed": "2026-02-10"
                        }]
                    }
                }
            }
        },
    }
    submissions = {
        "cik": "0000000404",
        "company_name": "Fixture SEC Company",
        "source_url": "https://data.sec.gov/submissions/CIK0000000404.json",
        "fetched_at": NOW,
        "filings": [{
            "accessionNumber": "0000000404-26-000001",
            "primaryDocument": "fixture-20251231.htm",
        }],
    }
    normalized = normalize_sec_payloads(company_facts, submissions, "FIX")
    revenue = next(item for item in normalized["metrics"] if item.metric_key == "total_revenue")
    assert revenue.value == 321.0
    assert revenue.verification_status == VerificationStatus.OFFICIAL
    assert revenue.source_document.endswith("fixture-20251231.htm")
    assert any(source.source_type == DataSourceType.SEC_SUBMISSIONS for source in normalized["sources"].values())


def test_financial_evidence_api_preserves_conflicts(monkeypatch):
    evidence = build_case(FIXTURE["cases"][1])
    monkeypatch.setattr(
        "app.main.market_data.get_overview",
        lambda ticker: {"ticker": ticker, "name": "Golden Bank"},
    )
    monkeypatch.setattr(
        "app.main.financial_verification.get_financial_evidence",
        lambda ticker, overview: evidence,
    )
    response = TestClient(app).get("/api/financials/BNK/evidence")
    assert response.status_code == 200
    payload = response.json()
    assert payload["conflicts"][0]["values"] == [5000.0, 5250.0]
    assert len(payload["metrics"]) >= 2


def test_analysis_prompt_uses_verified_value_not_raw_insight_value(monkeypatch):
    prompts = []

    def capture(prompt, **kwargs):
        prompts.append(prompt)
        return None

    monkeypatch.setattr(ai, "_ask_cited", capture)
    ai.narrate_analysis(
        "SAFE",
        {
            "company_name": "Safe Company",
            "verified_financial_metrics": [{
                "metric_key": "total_revenue",
                "value": 100.0,
                "unit": "currency",
                "period_type": "ANNUAL",
                "period_end": "2025-12-31",
                "provider": "SEC EDGAR",
                "verification_status": "OFFICIAL",
                "calculation_formula": None,
            }],
        },
        [{
            "kind": "opportunity",
            "title": {"claim": "Revenue evidence"},
            "evidence": [{
                "metric_key": "total_revenue",
                "metric": "Revenue",
                "value": {"value": 999999999.0},
                "benchmark": {"claim": "Unverified provider payload"},
            }],
        }],
    )
    assert prompts
    assert "total_revenue=100.0" in prompts[0]
    assert "999999999" not in prompts[0]
    assert "Unverified provider payload" not in prompts[0]
