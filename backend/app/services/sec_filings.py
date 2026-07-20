"""SEC EDGAR filing retrieval, section extraction, and grounded Q&A.

The SEC asks automated clients to identify themselves and stay below ten
requests per second. This module uses a declared User-Agent, serializes requests
to a conservative eight-per-second ceiling, and caches both metadata and filing
documents so one research session does not repeatedly hit EDGAR.
"""
from __future__ import annotations

import re
import threading
import time
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from ..config import settings
from ..models.schemas import FreshnessStatus
from . import ai
from .provenance import evidence, freshness_for, provenance, utc_now


SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_ARCHIVES_ROOT = "https://www.sec.gov/Archives/edgar/data"
SUPPORTED_FORMS = ("10-K", "10-Q", "8-K")
MAX_DOCUMENT_BYTES = 15_000_000
MAX_SECTION_CHARACTERS = 50_000
_ACCESSION_PATTERN = re.compile(r"^\d{10}-\d{2}-\d{6}$")
_DOCUMENT_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")
_ITEM_HEADING = re.compile(
    r"(?im)(?:^|\n)\s*ITEM\s+"
    r"(?P<item>\d{1,2}[A-Z]?(?:\.\d{2})?)"
    r"\s*[.\-:\u2014]?\s*(?P<title>[^\n]{0,180})"
)


class SecError(RuntimeError):
    """Base class for user-safe SEC failures."""


class SecNotFoundError(SecError):
    pass


class SecUnavailableError(SecError):
    pass


class SecRateLimitError(SecUnavailableError):
    pass


class SecParseError(SecUnavailableError):
    pass


_cache: dict[str, tuple[float, datetime, Any]] = {}
_cache_lock = threading.Lock()
_request_lock = threading.Lock()
_last_request_at = 0.0


def clear_cache() -> None:
    """Clear process-local SEC caches. Used by tests and local debugging."""
    with _cache_lock:
        _cache.clear()


def _cache_read(key: str, ttl_seconds: int):
    with _cache_lock:
        hit = _cache.get(key)
        if hit is None:
            return None
        stored_epoch, fetched_at, value = hit
        if time.time() - stored_epoch >= ttl_seconds:
            _cache.pop(key, None)
            return None
    expires_at = fetched_at + timedelta(seconds=ttl_seconds)
    return value, {
        "hit": True,
        "fetched_at": fetched_at,
        "expires_at": expires_at,
    }


def _cache_write(key: str, value: Any, ttl_seconds: int):
    fetched_at = utc_now()
    with _cache_lock:
        _cache[key] = (time.time(), fetched_at, value)
        if len(_cache) > 256:
            oldest = min(_cache, key=lambda item: _cache[item][0])
            _cache.pop(oldest, None)
    return value, {
        "hit": False,
        "fetched_at": fetched_at,
        "expires_at": fetched_at + timedelta(seconds=ttl_seconds),
    }


def _request(url: str) -> httpx.Response:
    global _last_request_at
    headers = {
        "User-Agent": settings.SEC_USER_AGENT,
        "Accept-Encoding": "gzip, deflate",
        "Accept": "application/json, text/html;q=0.9, */*;q=0.5",
    }
    response = None
    for attempt in range(3):
        try:
            with _request_lock:
                wait_for = 0.125 - (time.monotonic() - _last_request_at)
                if wait_for > 0:
                    time.sleep(wait_for)
                response = httpx.get(
                    url,
                    headers=headers,
                    timeout=settings.SEC_HTTP_TIMEOUT_SECONDS,
                    follow_redirects=True,
                )
                _last_request_at = time.monotonic()
        except httpx.TimeoutException as exc:
            raise SecUnavailableError("SEC EDGAR timed out; try again shortly") from exc
        except httpx.HTTPError as exc:
            raise SecUnavailableError("SEC EDGAR is temporarily unreachable") from exc

        if response.status_code not in {429, 500, 502, 503, 504}:
            break
        if attempt < 2:
            retry_after = response.headers.get("Retry-After", "")
            delay = float(retry_after) if retry_after.isdigit() else 0.5 * (attempt + 1)
            time.sleep(min(delay, 2.0))

    if response is None:
        raise SecUnavailableError("SEC EDGAR did not return a response")
    if response.status_code in {403, 429}:
        raise SecRateLimitError("SEC EDGAR is limiting automated access; try again later")
    if response.status_code == 404:
        raise SecNotFoundError("The requested SEC filing was not found")
    if response.status_code >= 400:
        raise SecUnavailableError(
            f"SEC EDGAR returned an upstream error ({response.status_code})"
        )
    return response


def _cached_json(url: str, ttl_seconds: int):
    key = f"json:{url}"
    cached = _cache_read(key, ttl_seconds)
    if cached is not None:
        return cached
    response = _request(url)
    try:
        payload = response.json()
    except ValueError as exc:
        raise SecParseError("SEC EDGAR returned invalid JSON") from exc
    return _cache_write(key, payload, ttl_seconds)


def _cached_document(url: str):
    ttl_seconds = settings.SEC_DOCUMENT_CACHE_TTL_SECONDS
    key = f"document:{url}"
    cached = _cache_read(key, ttl_seconds)
    if cached is not None:
        return cached
    response = _request(url)
    content_length = response.headers.get("Content-Length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_DOCUMENT_BYTES:
        raise SecParseError("This filing is too large to extract safely")
    if len(response.content) > MAX_DOCUMENT_BYTES:
        raise SecParseError("This filing is too large to extract safely")
    return _cache_write(key, response.text, ttl_seconds)


def _company_index() -> dict[str, dict]:
    payload, _ = _cached_json(SEC_TICKERS_URL, 24 * 60 * 60)
    companies: dict[str, dict] = {}
    if isinstance(payload, dict) and "fields" in payload and "data" in payload:
        fields = payload["fields"]
        for values in payload["data"]:
            row = dict(zip(fields, values))
            ticker = str(row.get("ticker") or "").upper()
            if ticker:
                companies[ticker] = row
    elif isinstance(payload, dict):
        for value in payload.values():
            if not isinstance(value, dict):
                continue
            ticker = str(value.get("ticker") or "").upper()
            if ticker:
                companies[ticker] = {
                    "cik": value.get("cik_str"),
                    "name": value.get("title"),
                    "ticker": ticker,
                    "exchange": None,
                }
    if not companies:
        raise SecParseError("SEC ticker directory did not contain company records")
    return companies


def _company_for_ticker(ticker: str) -> dict:
    company = _company_index().get(ticker.upper())
    if company is None:
        raise SecNotFoundError(f"No SEC filer was found for ticker '{ticker.upper()}'")
    try:
        cik = f"{int(company['cik']):010d}"
    except (KeyError, TypeError, ValueError) as exc:
        raise SecParseError("SEC ticker directory contained an invalid CIK") from exc
    return {
        "ticker": ticker.upper(),
        "cik": cik,
        "company_name": str(company.get("name") or ticker.upper()),
    }


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    raw = str(value).strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    try:
        return datetime.strptime(raw[:14], "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _split_items(value: Any) -> list[str]:
    if not value:
        return []
    values = re.split(r"[,;\s]+", str(value))
    return [item for item in values if re.fullmatch(r"\d{1,2}\.\d{2}", item)]


def _submission_rows(recent: dict) -> list[dict]:
    accessions = recent.get("accessionNumber") or []
    if not isinstance(accessions, list):
        return []
    rows = []
    for index in range(len(accessions)):
        row = {}
        for key, values in recent.items():
            row[key] = values[index] if isinstance(values, list) and index < len(values) else None
        rows.append(row)
    return rows


def _archive_urls(cik: str, accession: str, primary_document: str) -> tuple[str, str]:
    cik_path = str(int(cik))
    accession_path = accession.replace("-", "")
    base = f"{SEC_ARCHIVES_ROOT}/{cik_path}/{accession_path}"
    index_url = f"{base}/{accession}-index.html"
    source_url = (
        f"{base}/{primary_document}"
        if _DOCUMENT_PATTERN.fullmatch(primary_document or "")
        else index_url
    )
    return source_url, index_url


def _filing_summary(company: dict, row: dict) -> dict | None:
    filing_type = str(row.get("form") or "").upper()
    accession = str(row.get("accessionNumber") or "")
    filing_date = _parse_date(row.get("filingDate"))
    primary_document = str(row.get("primaryDocument") or "")
    if (
        filing_type not in SUPPORTED_FORMS
        or not _ACCESSION_PATTERN.fullmatch(accession)
        or filing_date is None
        or not primary_document
    ):
        return None
    items = _split_items(row.get("items"))
    description = str(row.get("primaryDocDescription") or "").strip() or None
    source_url, index_url = _archive_urls(
        company["cik"], accession, primary_document
    )
    earnings_words = f"{description or ''} {row.get('act') or ''}".lower()
    return {
        "accession_number": accession,
        "filing_type": filing_type,
        "filing_date": filing_date,
        "report_date": _parse_date(row.get("reportDate")),
        "accepted_at": _parse_datetime(row.get("acceptanceDateTime")),
        "primary_document": primary_document,
        "items": items,
        "description": description,
        "is_earnings_related": filing_type == "8-K"
        and ("2.02" in items or "earning" in earnings_words or "results" in earnings_words),
        "source_url": source_url,
        "index_url": index_url,
    }


def _load_company_filings(ticker: str):
    company = _company_for_ticker(ticker)
    submissions_url = SEC_SUBMISSIONS_URL.format(cik=company["cik"])
    payload, cache = _cached_json(submissions_url, settings.SEC_CACHE_TTL_SECONDS)
    recent = payload.get("filings", {}).get("recent", {}) if isinstance(payload, dict) else {}
    filings = [
        summary
        for row in _submission_rows(recent)
        if (summary := _filing_summary(company, row)) is not None
    ]
    company["company_name"] = str(payload.get("name") or company["company_name"])
    return company, filings, cache, submissions_url


def _source_metadata(
    *,
    source: str,
    source_url: str,
    as_of_date: date,
    fetched_at: datetime,
    historical: bool = False,
) -> dict:
    return provenance(
        provider="SEC EDGAR",
        source=source,
        as_of_date=as_of_date,
        fetched_at=fetched_at,
        freshness_status=(
            FreshnessStatus.HISTORICAL.value
            if historical
            else freshness_for(as_of_date, fetched_at, fresh_days=30)
        ),
        confidence=1.0,
        source_url=source_url,
    )


def list_filings(ticker: str, limit: int = 12) -> dict:
    company, filings, cache, submissions_url = _load_company_filings(ticker)
    selected = filings[:limit]
    return {
        **company,
        "filings": selected,
        "source": _source_metadata(
            source="EDGAR Submissions API",
            source_url=submissions_url,
            as_of_date=cache["fetched_at"].date(),
            fetched_at=cache["fetched_at"],
        ),
        "cache": cache,
    }


_SECTION_SPECS = {
    "10-K": [
        ("1", ("business",), "Business"),
        ("1A", ("risk",), "Risk factors"),
        ("7", ("management", "discussion"), "Management's discussion and analysis"),
        ("8", ("financial", "statement"), "Financial statements"),
    ],
    "10-Q": [
        ("1", ("financial", "statement"), "Financial statements"),
        ("2", ("management", "discussion"), "Management's discussion and analysis"),
        ("1A", ("risk",), "Risk factors"),
        ("4", ("controls", "procedures"), "Controls and procedures"),
    ],
}


def _plain_filing_text(document: str) -> str:
    soup = BeautifulSoup(document, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    text = soup.get_text("\n")
    text = text.replace("\xa0", " ").replace("\u200b", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _item_candidates(text: str) -> list[dict]:
    matches = list(_ITEM_HEADING.finditer(text))
    candidates = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        content = text[match.start():end].strip()
        if len(content) < 120:
            continue
        title = " ".join(match.group("title").split()).strip(" .:-\u2014")
        if not title:
            following = [line.strip() for line in content.splitlines()[1:4] if line.strip()]
            if following and len(following[0]) <= 180:
                title = following[0].strip(" .:-\u2014")
        candidates.append(
            {
                "item": match.group("item").upper(),
                "title": title,
                "text": content,
            }
        )
    return candidates


def _candidate_score(candidate: dict, keywords: tuple[str, ...]) -> int:
    preview = f"{candidate['title']} {candidate['text'][:1200]}".lower()
    keyword_score = sum(50_000 for keyword in keywords if keyword in preview)
    return keyword_score + min(len(candidate["text"]), 45_000)


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:80] or "section"


def extract_sections(
    document: str,
    filing_type: str,
    source_url: str,
    filing_items: list[str] | None = None,
) -> list[dict]:
    """Extract a bounded set of decision-useful filing sections."""
    text = _plain_filing_text(document)
    if not text:
        raise SecParseError("The SEC filing did not contain readable text")
    candidates = _item_candidates(text)

    specs = _SECTION_SPECS.get(filing_type)
    if specs is None:
        discovered = []
        desired_items = filing_items or ["2.02", "7.01", "8.01", "9.01"]
        for item in desired_items:
            if item not in discovered:
                discovered.append(item)
        specs = [(item, tuple(), f"Item {item}") for item in discovered[:8]]

    sections = []
    used_ids: set[str] = set()
    for item, keywords, fallback_title in specs:
        matching = [candidate for candidate in candidates if candidate["item"] == item]
        if not matching:
            continue
        candidate = max(matching, key=lambda value: _candidate_score(value, keywords))
        full_text = candidate["text"]
        clipped = full_text[:MAX_SECTION_CHARACTERS].rstrip()
        title = candidate["title"] or fallback_title
        section_id = _slug(f"item-{item}-{title}")
        if section_id in used_ids:
            section_id = f"{section_id}-{len(sections) + 1}"
        used_ids.add(section_id)
        sections.append(
            {
                "section_id": section_id,
                "item": item,
                "title": title,
                "text": clipped,
                "character_count": len(full_text),
                "truncated": len(clipped) < len(full_text),
                "source_url": source_url,
            }
        )

    if not sections:
        clipped = text[:MAX_SECTION_CHARACTERS].rstrip()
        sections.append(
            {
                "section_id": "filing-text",
                "item": "filing",
                "title": "Filing text",
                "text": clipped,
                "character_count": len(text),
                "truncated": len(clipped) < len(text),
                "source_url": source_url,
            }
        )
    return sections


def _safe_archive_url(base_url: str, href: str) -> str | None:
    candidate = urljoin(base_url, href)
    parsed = urlparse(candidate)
    if (
        parsed.scheme == "https"
        and parsed.netloc.lower() == "www.sec.gov"
        and parsed.path.startswith("/Archives/edgar/data/")
    ):
        return candidate
    return None


def _earnings_exhibit_links(index_document: str, index_url: str) -> list[dict]:
    """Return SEC-hosted EX-99 earnings documents from a filing index page."""
    soup = BeautifulSoup(index_document, "html.parser")
    exhibits = []
    for row in soup.find_all("tr"):
        cells = [" ".join(cell.get_text(" ", strip=True).split()) for cell in row.find_all("td")]
        link = row.find("a", href=True)
        if len(cells) < 4 or link is None:
            continue
        exhibit_type = next(
            (cell.upper() for cell in cells if cell.upper().startswith("EX-99")),
            "",
        )
        if not exhibit_type:
            continue
        description = cells[1] if len(cells) > 1 else exhibit_type
        searchable = f"{description} {link.get('href', '')}".lower()
        if not any(word in searchable for word in ("earning", "result", "release", "ex99")):
            continue
        source_url = _safe_archive_url(index_url, str(link["href"]))
        if source_url is None:
            continue
        exhibits.append(
            {
                "item": exhibit_type,
                "title": description or f"{exhibit_type} earnings exhibit",
                "source_url": source_url,
            }
        )
        if len(exhibits) == 2:
            break
    return exhibits


def _combine_cache_metadata(caches: list[dict]) -> dict:
    return {
        "hit": all(cache["hit"] for cache in caches),
        "fetched_at": max(cache["fetched_at"] for cache in caches),
        "expires_at": min(cache["expires_at"] for cache in caches),
    }


def get_filing(ticker: str, accession_number: str) -> dict:
    if not _ACCESSION_PATTERN.fullmatch(accession_number):
        raise SecNotFoundError("Invalid SEC accession number")
    company, filings, _, _ = _load_company_filings(ticker)
    filing = next(
        (item for item in filings if item["accession_number"] == accession_number),
        None,
    )
    if filing is None:
        raise SecNotFoundError(
            f"Filing '{accession_number}' was not found for {ticker.upper()}"
        )
    document, cache = _cached_document(filing["source_url"])
    document_caches = [cache]
    sections = extract_sections(
        document,
        filing["filing_type"],
        filing["source_url"],
        filing["items"],
    )
    if filing["is_earnings_related"]:
        index_document, index_cache = _cached_document(filing["index_url"])
        document_caches.append(index_cache)
        for exhibit in _earnings_exhibit_links(index_document, filing["index_url"]):
            exhibit_document, exhibit_cache = _cached_document(exhibit["source_url"])
            document_caches.append(exhibit_cache)
            exhibit_text = _plain_filing_text(exhibit_document)
            if len(exhibit_text) < 120:
                continue
            clipped = exhibit_text[:MAX_SECTION_CHARACTERS].rstrip()
            sections.append(
                {
                    "section_id": _slug(f"{exhibit['item']}-{exhibit['title']}"),
                    "item": exhibit["item"],
                    "title": exhibit["title"],
                    "text": clipped,
                    "character_count": len(exhibit_text),
                    "truncated": len(clipped) < len(exhibit_text),
                    "source_url": exhibit["source_url"],
                }
            )
    cache = _combine_cache_metadata(document_caches)
    return {
        **company,
        "filing": filing,
        "sections": sections,
        "source": _source_metadata(
            source=f"EDGAR {filing['filing_type']} filing package",
            source_url=filing["index_url"],
            as_of_date=filing["filing_date"],
            fetched_at=cache["fetched_at"],
            historical=True,
        ),
        "cache": cache,
    }


_STOPWORDS = {
    "about", "after", "also", "and", "are", "because", "been", "before",
    "could", "does", "filing", "for", "from", "have", "how", "into", "its",
    "most", "our", "that", "the", "their", "this", "was", "were", "what",
    "when", "where", "which", "with", "would", "you", "your",
}


def _tokens(value: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9][a-z0-9'-]{2,}", value.lower())
        if token not in _STOPWORDS
    ]


def _section_chunks(text: str, size: int = 2400) -> list[str]:
    paragraphs = [" ".join(part.split()) for part in text.split("\n") if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > size:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(
                paragraph[start:start + size].strip()
                for start in range(0, len(paragraph), size)
            )
        elif len(current) + len(paragraph) + 1 > size:
            chunks.append(current)
            current = paragraph
        else:
            current = f"{current} {paragraph}".strip()
    if current:
        chunks.append(current)
    return chunks or [text[:size]]


def _citation_quote(chunk: str, query_tokens: list[str], limit: int = 420) -> str:
    lowered = chunk.lower()
    positions = [lowered.find(token) for token in query_tokens if lowered.find(token) >= 0]
    focus = min(positions) if positions else 0
    start = max(0, focus - 110)
    end = min(len(chunk), start + limit)
    if start:
        boundary = chunk.find(" ", start)
        start = boundary + 1 if boundary >= 0 else start
    if end < len(chunk):
        boundary = chunk.rfind(" ", start, end)
        end = boundary if boundary > start else end
    quote = chunk[start:end].strip()
    return f"…{quote}" if start else quote


def _relevant_passages(question: str, sections: list[dict]) -> list[dict]:
    query_tokens = _tokens(question)
    scored = []
    for section in sections:
        title_tokens = Counter(_tokens(section["title"]))
        for chunk in _section_chunks(section["text"]):
            chunk_tokens = Counter(_tokens(chunk))
            score = sum(
                chunk_tokens[token] + (title_tokens[token] * 5)
                for token in query_tokens
            )
            scored.append((score, section, chunk))
    scored.sort(key=lambda value: (value[0], len(value[2])), reverse=True)
    passages = []
    used_sections = set()
    for score, section, chunk in scored:
        if section["section_id"] in used_sections and len(passages) < 2:
            continue
        used_sections.add(section["section_id"])
        passages.append(
            {
                "section_id": section["section_id"],
                "section_title": section["title"],
                "text": chunk,
                "quote": _citation_quote(chunk, query_tokens),
                "source_url": section["source_url"],
                "score": score,
            }
        )
        if len(passages) == 3:
            break
    return passages


_FALLBACK_ANSWERS = {
    "en": "The strongest matching passage is in {title}: {quote}",
    "es": "El pasaje más relevante está en {title}: {quote}",
    "fr": "Le passage le plus pertinent se trouve dans {title} : {quote}",
    "zh": "最相关的原文位于“{title}”：{quote}",
}


def answer_question(
    ticker: str,
    accession_number: str,
    question: str,
    lang: str = "en",
) -> dict:
    detail = get_filing(ticker, accession_number)
    passages = _relevant_passages(question, detail["sections"])
    if not passages:
        raise SecParseError("No readable filing passages were available for this question")
    answer_text = ai.answer_filing_question(question, passages, lang=lang)
    ai_used = bool(answer_text)
    if not answer_text:
        answer_text = _FALLBACK_ANSWERS.get(lang, _FALLBACK_ANSWERS["en"]).format(
            title=passages[0]["section_title"],
            quote=passages[0]["quote"],
        )
    answered_at = utc_now()
    filing = detail["filing"]
    answer = evidence(
        answer_text,
        **provenance(
            provider="Anthropic" if ai_used else "FinSight",
            source=settings.AI_MODEL if ai_used else "deterministic SEC passage retrieval v1",
            as_of_date=filing["filing_date"],
            fetched_at=answered_at,
            freshness_status=FreshnessStatus.HISTORICAL.value,
            confidence=0.65 if ai_used else 0.8,
            source_url=filing["source_url"],
        ),
    )
    return {
        "ticker": ticker.upper(),
        "accession_number": accession_number,
        "question": question,
        "answer": answer,
        "citations": [
            {
                "section_id": passage["section_id"],
                "section_title": passage["section_title"],
                "quote": passage["quote"],
                "source_url": passage["source_url"],
            }
            for passage in passages
        ],
        "answered_at": answered_at,
        "ai_used": ai_used,
    }
