"""Company-aware symbol search ranking, fallback, cache, and API tests."""
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402
from app.services import company_search  # noqa: E402
from app.services.company_search import (  # noqa: E402
    CompanyRecord,
    CompanySearchResult,
    CompanySearchService,
    MaintainedIndexProvider,
)


def offline_search(query, limit=8):
    service = CompanySearchService(
        providers=(MaintainedIndexProvider(),),
        cache_ttl_seconds=60,
    )
    return service.search(query, limit=limit)


def test_exact_company_names_and_tickers_rank_first():
    apple = offline_search("Apple")
    microsoft = offline_search("Microsoft")
    ticker = offline_search("MSFT")

    assert apple[0].ticker == "AAPL"
    assert apple[0].match_type == "exact_name"
    assert microsoft[0].ticker == "MSFT"
    assert ticker[0].ticker == "MSFT"
    assert ticker[0].match_type == "exact_ticker"
    assert ticker[0].match_score == 1


def test_typo_is_fuzzy_and_keeps_confidence_below_exact_match():
    results = offline_search("microsft")

    assert results[0].ticker == "MSFT"
    assert results[0].match_type == "fuzzy"
    assert 0.7 < results[0].match_score < 0.9


def test_berkshire_returns_both_share_classes_without_collapsing_them():
    results = offline_search("Berkshire Hathaway")

    assert [result.ticker for result in results[:2]] == ["BRK-A", "BRK-B"]
    assert all(result.match_type == "exact_name" for result in results[:2])


def test_ambiguous_name_returns_ranked_choices_instead_of_one_mapping():
    results = offline_search("Unity")

    assert [result.ticker for result in results[:2]] == ["U", "UNTY"]
    assert results[0].match_score > results[1].match_score


def test_alias_localized_alias_and_unsupported_queries():
    assert offline_search("Google")[0].ticker == "GOOGL"
    assert offline_search("Google")[0].match_type == "alias"

    localized = offline_search("微软")
    assert localized[0].ticker == "MSFT"
    assert localized[0].match_type == "localized_alias"
    assert offline_search("not-a-supported-company-query-xyz") == []


class FailingProvider:
    remote = True

    def search(self, query, limit):
        raise TimeoutError("provider unavailable")


class CountingProvider:
    remote = True

    def __init__(self):
        self.calls = 0

    def search(self, query, limit):
        self.calls += 1
        return [CompanyRecord(
            ticker="ACME",
            company_name="Acme Corporation",
            exchange="NYSE",
            country="United States",
            sector="Industrials",
            asset_type="equity",
            data_source="Test maintained provider",
        )]


def test_provider_failure_falls_back_to_maintained_index():
    service = CompanySearchService(
        providers=(FailingProvider(), MaintainedIndexProvider()),
        cache_ttl_seconds=60,
    )

    results = service.search("Apple")

    assert results[0].ticker == "AAPL"
    assert results[0].data_source.startswith("FinSight maintained symbol index")


def test_search_results_are_cached_by_normalized_query_and_limit():
    provider = CountingProvider()
    service = CompanySearchService(providers=(provider,), cache_ttl_seconds=60)

    first = service.search("Acme", limit=5)
    second = service.search("  ACME  ", limit=5)

    assert first == second
    assert provider.calls == 1


def test_search_api_returns_normalized_contract(monkeypatch):
    result = CompanySearchResult(
        ticker="AAPL",
        company_name="Apple Inc.",
        exchange="Nasdaq",
        country="United States",
        sector="Technology",
        asset_type="equity",
        match_score=0.98,
        match_type="exact_name",
        data_source="Yahoo Finance symbol search",
        matched_text="Apple Inc.",
    )
    calls = []
    monkeypatch.setattr(
        "app.main.company_search.search_companies",
        lambda query, limit: calls.append((query, limit)) or [result],
    )

    response = TestClient(app).get("/api/search/companies?q=Apple&limit=4")

    assert response.status_code == 200
    assert calls == [("Apple", 4)]
    payload = response.json()[0]
    assert payload == {
        "ticker": "AAPL",
        "company_name": "Apple Inc.",
        "exchange": "Nasdaq",
        "country": "United States",
        "sector": "Technology",
        "asset_type": "equity",
        "match_score": 0.98,
        "match_type": "exact_name",
        "data_source": "Yahoo Finance symbol search",
        "matched_text": "Apple Inc.",
    }


def test_search_api_validates_query_and_limit():
    client = TestClient(app)

    assert client.get("/api/search/companies?limit=5").status_code == 422
    assert client.get("/api/search/companies?q=Apple&limit=0").status_code == 422
    assert client.get("/api/search/companies?q=Apple&limit=21").status_code == 422
