"""Deterministic company-name and ticker lookup used by the assistant.

Keeping this behind a service boundary makes it straightforward to replace the
bundled directory with an exchange/security-master provider later. Assistant
responses never guess a ticker from an unmatched company name.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CompanySearchResult:
    name: str
    ticker: str
    exchange: str
    aliases: tuple[str, ...] = ()


_COMPANIES = (
    CompanySearchResult("Apple Inc.", "AAPL", "Nasdaq", ("apple",)),
    CompanySearchResult("Microsoft Corporation", "MSFT", "Nasdaq", ("microsoft",)),
    CompanySearchResult("NVIDIA Corporation", "NVDA", "Nasdaq", ("nvidia",)),
    CompanySearchResult("Alphabet Inc.", "GOOGL", "Nasdaq", ("alphabet", "google")),
    CompanySearchResult("Amazon.com, Inc.", "AMZN", "Nasdaq", ("amazon",)),
    CompanySearchResult("Meta Platforms, Inc.", "META", "Nasdaq", ("meta", "facebook")),
    CompanySearchResult("Tesla, Inc.", "TSLA", "Nasdaq", ("tesla",)),
    CompanySearchResult("Berkshire Hathaway Inc.", "BRK.B", "NYSE", ("berkshire",)),
    CompanySearchResult("JPMorgan Chase & Co.", "JPM", "NYSE", ("jpmorgan", "jp morgan")),
    CompanySearchResult("Visa Inc.", "V", "NYSE", ("visa",)),
    CompanySearchResult("Walmart Inc.", "WMT", "NYSE", ("walmart",)),
    CompanySearchResult("Costco Wholesale Corporation", "COST", "Nasdaq", ("costco",)),
    CompanySearchResult("The Coca-Cola Company", "KO", "NYSE", ("coca cola", "coke")),
    CompanySearchResult("Netflix, Inc.", "NFLX", "Nasdaq", ("netflix",)),
    CompanySearchResult("Advanced Micro Devices, Inc.", "AMD", "Nasdaq", ("amd",)),
    CompanySearchResult("Salesforce, Inc.", "CRM", "NYSE", ("salesforce",)),
    CompanySearchResult("Adobe Inc.", "ADBE", "Nasdaq", ("adobe",)),
    CompanySearchResult("Intel Corporation", "INTC", "Nasdaq", ("intel",)),
    CompanySearchResult("The Walt Disney Company", "DIS", "NYSE", ("disney",)),
    CompanySearchResult("Toyota Motor Corporation", "TM", "NYSE", ("toyota",)),
)


def _normalize(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def search_companies(query: str, limit: int = 5) -> list[CompanySearchResult]:
    normalized = _normalize(query)
    if not normalized:
        return []
    query_tokens = set(normalized.split())
    ranked: list[tuple[int, CompanySearchResult]] = []
    for company in _COMPANIES:
        names = (company.name, company.ticker, *company.aliases)
        normalized_names = [_normalize(name) for name in names]
        if company.ticker.casefold() in query.casefold().split():
            score = 100
        elif any(name and name in normalized for name in normalized_names):
            score = 80 + max(len(name) for name in normalized_names if name in normalized)
        else:
            overlap = max(
                (len(query_tokens & set(name.split())) for name in normalized_names),
                default=0,
            )
            if not overlap:
                continue
            score = overlap * 10
        ranked.append((score, company))
    ranked.sort(key=lambda item: (-item[0], item[1].name))
    return [company for _, company in ranked[:limit]]

