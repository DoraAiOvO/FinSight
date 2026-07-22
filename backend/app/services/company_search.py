"""Provider-backed, deterministic company and symbol search.

Yahoo Finance supplies the live symbol search.  A small maintained exchange-
listed index supplies aliases, localized names, metadata, and an offline
fallback.  Matching and ranking are code-defined; an LLM is never involved in
mapping a company name to a ticker.
"""
from __future__ import annotations

import re
import threading
import time
import unicodedata
from dataclasses import dataclass, replace
from difflib import SequenceMatcher
from typing import Protocol

import yfinance as yf

from ..config import settings


MATCH_TYPES = (
    "exact_ticker",
    "exact_name",
    "prefix",
    "partial_token",
    "alias",
    "localized_alias",
    "fuzzy",
)


@dataclass(frozen=True)
class CompanyRecord:
    ticker: str
    company_name: str
    exchange: str
    country: str | None
    sector: str | None
    asset_type: str
    data_source: str
    aliases: tuple[str, ...] = ()
    localized_aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class CompanySearchResult:
    ticker: str
    company_name: str
    exchange: str
    country: str | None
    sector: str | None
    asset_type: str
    match_score: float
    match_type: str
    data_source: str
    matched_text: str

    @property
    def name(self) -> str:
        """Backward-compatible name used by the grounded assistant lookup."""
        return self.company_name


class CompanyProvider(Protocol):
    remote: bool

    def search(self, query: str, limit: int) -> list[CompanyRecord]: ...


_INDEX_SOURCE = "FinSight maintained symbol index · exchange snapshot 2026-07-22"

# This compact fallback is intentionally factual and reviewable.  It is not a
# substitute for the live provider; it keeps popular lookups and product aliases
# available during provider outages and gives us a controlled home for localized
# aliases that exchange feeds commonly omit.
_MAINTAINED_INDEX = (
    CompanyRecord("AAPL", "Apple Inc.", "Nasdaq", "United States", "Technology", "equity", _INDEX_SOURCE, ("apple computer",), ("苹果", "苹果公司")),
    CompanyRecord("APLE", "Apple Hospitality REIT, Inc.", "NYSE", "United States", "Real Estate", "equity", _INDEX_SOURCE, ("apple hospitality",), ()),
    CompanyRecord("MSFT", "Microsoft Corporation", "Nasdaq", "United States", "Technology", "equity", _INDEX_SOURCE, ("microsoft", "windows maker"), ("微软", "微软公司")),
    CompanyRecord("NVDA", "NVIDIA Corporation", "Nasdaq", "United States", "Technology", "equity", _INDEX_SOURCE, ("nvidia",), ("英伟达", "辉达")),
    CompanyRecord("GOOGL", "Alphabet Inc. Class A", "Nasdaq", "United States", "Communication Services", "equity", _INDEX_SOURCE, ("google", "alphabet"), ("谷歌", "谷歌母公司")),
    CompanyRecord("GOOG", "Alphabet Inc. Class C", "Nasdaq", "United States", "Communication Services", "equity", _INDEX_SOURCE, ("google", "alphabet"), ("谷歌", "谷歌母公司")),
    CompanyRecord("AMZN", "Amazon.com, Inc.", "Nasdaq", "United States", "Consumer Cyclical", "equity", _INDEX_SOURCE, ("amazon",), ("亚马逊",)),
    CompanyRecord("META", "Meta Platforms, Inc.", "Nasdaq", "United States", "Communication Services", "equity", _INDEX_SOURCE, ("facebook", "meta"), ("脸书", "元宇宙平台")),
    CompanyRecord("TSLA", "Tesla, Inc.", "Nasdaq", "United States", "Consumer Cyclical", "equity", _INDEX_SOURCE, ("tesla motors", "tesla"), ("特斯拉",)),
    CompanyRecord("BRK-A", "Berkshire Hathaway Inc. Class A", "NYSE", "United States", "Financial Services", "equity", _INDEX_SOURCE, ("berkshire", "berkshire hathaway class a"), ("伯克希尔哈撒韦",)),
    CompanyRecord("BRK-B", "Berkshire Hathaway Inc. Class B", "NYSE", "United States", "Financial Services", "equity", _INDEX_SOURCE, ("berkshire", "berkshire hathaway class b"), ("伯克希尔哈撒韦",)),
    CompanyRecord("JPM", "JPMorgan Chase & Co.", "NYSE", "United States", "Financial Services", "equity", _INDEX_SOURCE, ("jp morgan", "jpmorgan", "chase bank"), ("摩根大通",)),
    CompanyRecord("V", "Visa Inc.", "NYSE", "United States", "Financial Services", "equity", _INDEX_SOURCE, ("visa",), ("维萨",)),
    CompanyRecord("WMT", "Walmart Inc.", "NYSE", "United States", "Consumer Defensive", "equity", _INDEX_SOURCE, ("wal-mart", "walmart"), ("沃尔玛",)),
    CompanyRecord("COST", "Costco Wholesale Corporation", "Nasdaq", "United States", "Consumer Defensive", "equity", _INDEX_SOURCE, ("costco",), ("开市客", "好市多")),
    CompanyRecord("KO", "The Coca-Cola Company", "NYSE", "United States", "Consumer Defensive", "equity", _INDEX_SOURCE, ("coca cola", "coke"), ("可口可乐",)),
    CompanyRecord("NFLX", "Netflix, Inc.", "Nasdaq", "United States", "Communication Services", "equity", _INDEX_SOURCE, ("netflix",), ("奈飞", "网飞")),
    CompanyRecord("AMD", "Advanced Micro Devices, Inc.", "Nasdaq", "United States", "Technology", "equity", _INDEX_SOURCE, ("amd",), ("超威半导体",)),
    CompanyRecord("CRM", "Salesforce, Inc.", "NYSE", "United States", "Technology", "equity", _INDEX_SOURCE, ("salesforce",), ("赛富时",)),
    CompanyRecord("ADBE", "Adobe Inc.", "Nasdaq", "United States", "Technology", "equity", _INDEX_SOURCE, ("adobe",), ("奥多比",)),
    CompanyRecord("INTC", "Intel Corporation", "Nasdaq", "United States", "Technology", "equity", _INDEX_SOURCE, ("intel",), ("英特尔",)),
    CompanyRecord("DIS", "The Walt Disney Company", "NYSE", "United States", "Communication Services", "equity", _INDEX_SOURCE, ("disney", "walt disney"), ("迪士尼",)),
    CompanyRecord("TM", "Toyota Motor Corporation", "NYSE", "Japan", "Consumer Cyclical", "equity", _INDEX_SOURCE, ("toyota",), ("丰田", "丰田汽车")),
    CompanyRecord("TSM", "Taiwan Semiconductor Manufacturing Company Limited", "NYSE", "Taiwan", "Technology", "equity", _INDEX_SOURCE, ("tsmc", "taiwan semiconductor"), ("台积电", "台湾积体电路制造")),
    CompanyRecord("BABA", "Alibaba Group Holding Limited", "NYSE", "China", "Consumer Cyclical", "equity", _INDEX_SOURCE, ("alibaba",), ("阿里巴巴", "阿里")),
    CompanyRecord("SONY", "Sony Group Corporation", "NYSE", "Japan", "Technology", "equity", _INDEX_SOURCE, ("sony",), ("索尼",)),
    CompanyRecord("U", "Unity Software Inc.", "NYSE", "United States", "Technology", "equity", _INDEX_SOURCE, ("unity", "unity technologies"), ("Unity 引擎",)),
    CompanyRecord("UNTY", "Unity Bancorp, Inc.", "Nasdaq", "United States", "Financial Services", "equity", _INDEX_SOURCE, ("unity bank",), ()),
)

_LEGAL_SUFFIXES = {
    "co", "company", "corp", "corporation", "inc", "incorporated", "limited",
    "ltd", "plc", "holdings", "holding", "group",
}
_EXCHANGE_COUNTRIES = {
    "ASE": "United States", "AMEX": "United States", "NASDAQ": "United States",
    "NCM": "United States", "NGM": "United States", "NMS": "United States",
    "NYQ": "United States", "NYSE": "United States", "PCX": "United States",
    "TOR": "Canada", "TSX": "Canada", "LSE": "United Kingdom",
    "HKG": "Hong Kong", "JPX": "Japan", "GER": "Germany", "FRA": "Germany",
}


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    characters = []
    for character in decomposed:
        if unicodedata.combining(character):
            continue
        characters.append(character if character.isalnum() else " ")
    return " ".join("".join(characters).split())


def _ticker_key(value: str) -> str:
    return re.sub(r"[.\-]", "", value.casefold().strip())


def _name_variants(value: str) -> tuple[str, ...]:
    normalized = _normalize(value)
    tokens = normalized.split()
    variants = [normalized]
    while tokens and (tokens[-1] in _LEGAL_SUFFIXES or tokens[-1] in {"a", "b", "c"}):
        tokens.pop()
        if tokens and tokens[-1] == "class":
            tokens.pop()
    while tokens and tokens[-1] in _LEGAL_SUFFIXES:
        tokens.pop()
    if tokens and tokens[0] == "the":
        tokens = tokens[1:]
    shortened = " ".join(tokens)
    if shortened and shortened not in variants:
        variants.append(shortened)
    return tuple(variants)


def _best_prefix(query: str, values: tuple[str, ...]) -> tuple[float, str] | None:
    candidates = [value for value in values if value and value.startswith(query)]
    if not candidates:
        return None
    matched = min(candidates, key=len)
    return min(0.94, 0.84 + (len(query) / max(len(matched), 1)) * 0.1), matched


def _score_record(record: CompanyRecord, query: str) -> tuple[float, str, str] | None:
    raw_query = query.strip()
    normalized = _normalize(raw_query)
    if not normalized:
        return None

    if _ticker_key(raw_query) == _ticker_key(record.ticker):
        return 1.0, "exact_ticker", record.ticker

    name_variants = _name_variants(record.company_name)
    if normalized == name_variants[0]:
        return 1.0, "exact_name", record.company_name
    if normalized in name_variants[1:]:
        return 0.98, "exact_name", record.company_name

    aliases = tuple((_normalize(alias), alias) for alias in record.aliases)
    localized = tuple((_normalize(alias), alias) for alias in record.localized_aliases)
    for alias, display in localized:
        if normalized == alias:
            return 0.97, "localized_alias", display
    for alias, display in aliases:
        if normalized == alias:
            return 0.96, "alias", display

    searchable = name_variants + tuple(alias for alias, _ in aliases + localized)
    prefix = _best_prefix(normalized, searchable)
    if prefix:
        return prefix[0], "prefix", prefix[1]

    query_tokens = normalized.split()
    partial_matches: list[tuple[float, str]] = []
    for candidate in searchable:
        candidate_tokens = candidate.split()
        if len(candidate) >= 3 and candidate in normalized:
            partial_matches.append((0.8, candidate))
            continue
        if normalized in candidate:
            partial_matches.append((0.78 + min(0.11, len(normalized) / max(len(candidate), 1) * 0.11), candidate))
            continue
        if query_tokens and all(
            any(token in candidate_token for candidate_token in candidate_tokens)
            for token in query_tokens
        ):
            coverage = len(query_tokens) / max(len(candidate_tokens), 1)
            partial_matches.append((0.76 + min(0.12, coverage * 0.12), candidate))
    if partial_matches:
        score, matched = max(partial_matches)
        return score, "partial_token", matched

    fuzzy_candidates = [candidate for candidate in searchable if candidate]
    if not fuzzy_candidates:
        return None
    matched = max(
        fuzzy_candidates,
        key=lambda candidate: SequenceMatcher(None, normalized, candidate).ratio(),
    )
    similarity = SequenceMatcher(None, normalized, matched).ratio()
    threshold = 0.82 if len(normalized) < 4 else 0.68
    if similarity < threshold:
        return None
    return min(0.85, round(0.55 + similarity * 0.31, 4)), "fuzzy", matched


class YahooFinanceCompanyProvider:
    remote = True

    def search(self, query: str, limit: int) -> list[CompanyRecord]:
        kwargs = {
            "max_results": max(limit * 3, 12),
            "news_count": 0,
            "lists_count": 0,
            "include_cb": False,
            "recommended": 0,
            "timeout": settings.COMPANY_SEARCH_TIMEOUT_SECONDS,
            "raise_errors": True,
        }
        try:
            response = yf.Search(query, enable_fuzzy_query=True, **kwargs)
        except TypeError:  # Compatibility with older supported yfinance builds.
            response = yf.Search(query, **kwargs)

        records = []
        for quote in response.quotes:
            ticker = str(quote.get("symbol") or "").strip().upper()
            company_name = str(quote.get("longname") or quote.get("shortname") or "").strip()
            if not ticker or not company_name:
                continue
            quote_type = str(quote.get("quoteType") or "equity").casefold()
            exchange_code = str(quote.get("exchange") or "").upper()
            exchange = str(quote.get("exchDisp") or exchange_code or "Unknown")
            country = quote.get("country") or _EXCHANGE_COUNTRIES.get(exchange_code)
            sector = quote.get("sectorDisp") or quote.get("sector")
            records.append(CompanyRecord(
                ticker=ticker,
                company_name=company_name,
                exchange=exchange,
                country=str(country) if country else None,
                sector=str(sector) if sector else None,
                asset_type={
                    "mutualfund": "mutual_fund",
                    "cryptocurrency": "crypto",
                }.get(quote_type, quote_type),
                data_source="Yahoo Finance symbol search",
            ))
        return records


class MaintainedIndexProvider:
    remote = False

    def search(self, query: str, limit: int) -> list[CompanyRecord]:
        ranked = []
        for record in _MAINTAINED_INDEX:
            score = _score_record(record, query)
            if score:
                ranked.append((score[0], record.company_name, record.ticker, record))
        ranked.sort(key=lambda item: (-item[0], item[1], item[2]))
        return [item[3] for item in ranked[: max(limit * 3, 20)]]


class _TTLCache:
    def __init__(self, ttl_seconds: int, maximum: int = 256):
        self.ttl_seconds = ttl_seconds
        self.maximum = maximum
        self._values: dict[tuple[str, int, bool], tuple[float, tuple[CompanySearchResult, ...]]] = {}
        self._lock = threading.Lock()

    def get(self, key: tuple[str, int, bool]) -> tuple[CompanySearchResult, ...] | None:
        now = time.monotonic()
        with self._lock:
            cached = self._values.get(key)
            if cached is None:
                return None
            if now - cached[0] >= self.ttl_seconds:
                self._values.pop(key, None)
                return None
            return cached[1]

    def set(self, key: tuple[str, int, bool], value: tuple[CompanySearchResult, ...]) -> None:
        with self._lock:
            if len(self._values) >= self.maximum:
                oldest = min(self._values, key=lambda item: self._values[item][0])
                self._values.pop(oldest, None)
            self._values[key] = (time.monotonic(), value)

    def clear(self) -> None:
        with self._lock:
            self._values.clear()


class CompanySearchService:
    def __init__(
        self,
        providers: tuple[CompanyProvider, ...] | None = None,
        cache_ttl_seconds: int | None = None,
    ):
        self.providers = providers or (YahooFinanceCompanyProvider(), MaintainedIndexProvider())
        self.cache = _TTLCache(
            cache_ttl_seconds if cache_ttl_seconds is not None
            else settings.COMPANY_SEARCH_CACHE_TTL_SECONDS
        )

    def search(
        self,
        query: str,
        limit: int = 8,
        *,
        include_provider: bool = True,
    ) -> list[CompanySearchResult]:
        normalized = _normalize(query)
        if not normalized:
            return []
        key = (normalized, limit, include_provider)
        cached = self.cache.get(key)
        if cached is not None:
            return list(cached)

        records: dict[str, CompanyRecord] = {}
        for provider in self.providers:
            if provider.remote and not include_provider:
                continue
            try:
                candidates = provider.search(query, limit)
            except Exception:
                # Provider outages are expected operational failures. Continue to
                # the maintained index instead of failing the autocomplete.
                continue
            for candidate in candidates:
                record_key = _ticker_key(candidate.ticker)
                current = records.get(record_key)
                if current is None:
                    records[record_key] = candidate
                    continue
                # Preserve live provider attribution while filling missing metadata
                # and aliases from the maintained fallback.
                records[record_key] = replace(
                    current,
                    country=current.country or candidate.country,
                    sector=current.sector or candidate.sector,
                    aliases=tuple(dict.fromkeys(current.aliases + candidate.aliases)),
                    localized_aliases=tuple(dict.fromkeys(
                        current.localized_aliases + candidate.localized_aliases
                    )),
                )

        ranked: list[CompanySearchResult] = []
        for record in records.values():
            match = _score_record(record, query)
            if match is None:
                continue
            score, match_type, matched_text = match
            ranked.append(CompanySearchResult(
                ticker=record.ticker,
                company_name=record.company_name,
                exchange=record.exchange,
                country=record.country,
                sector=record.sector,
                asset_type=record.asset_type,
                match_score=round(score, 4),
                match_type=match_type,
                data_source=record.data_source,
                matched_text=matched_text,
            ))
        ranked.sort(key=lambda item: (
            -item.match_score,
            item.company_name.casefold(),
            item.ticker,
        ))
        results = tuple(ranked[:limit])
        self.cache.set(key, results)
        return list(results)


_default_service = CompanySearchService()


def search_companies(
    query: str,
    limit: int = 8,
    *,
    include_provider: bool = True,
) -> list[CompanySearchResult]:
    return _default_service.search(query, limit, include_provider=include_provider)


def clear_search_cache() -> None:
    _default_service.cache.clear()
