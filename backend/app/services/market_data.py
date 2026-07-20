"""Market data access layer built on yfinance, with a small in-memory cache."""
import math
import time
from datetime import date, datetime, timezone

import yfinance as yf

from ..config import settings
from ..models.schemas import FreshnessStatus
from .provenance import data_point, evidence, freshness_for, provenance

_cache: dict[str, tuple[float, dict]] = {}


def _cached(key: str):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < settings.CACHE_TTL_SECONDS:
        return hit[1]
    return None


def _store(key: str, value: dict):
    _cache[key] = (time.time(), value)
    return value


def get_raw_info(ticker: str) -> dict:
    """Fetch raw info dict from Yahoo Finance (cached)."""
    key = f"info:{ticker.upper()}"
    cached = _cached(key)
    if cached is not None:
        return cached
    info = yf.Ticker(ticker).info or {}
    if not info.get("symbol") and not info.get("shortName"):
        raise LookupError(f"No data found for ticker '{ticker}'")
    return _store(key, info)


def _info_with_fetch_time(ticker: str) -> tuple[dict, datetime]:
    """Return provider data plus the original cache/fetch timestamp."""
    info = get_raw_info(ticker)
    fetched_epoch = _cache[f"info:{ticker.upper()}"][0]
    return info, datetime.fromtimestamp(fetched_epoch, tz=timezone.utc)


def _provider_date(value, fallback: date) -> tuple[date, bool]:
    if value is None:
        return fallback, False
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc).date(), True
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date(), True
    except (TypeError, ValueError, OSError):
        return fallback, False


def _published_at(value) -> str | None:
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
        return str(value)
    except (ValueError, OSError):
        return str(value)


def normalize_dividend_yield(info: dict, price: float | None) -> float | None:
    """Return dividend yield as a decimal across yfinance response versions."""
    annual_dividend = info.get("dividendRate")
    if annual_dividend is not None and price:
        try:
            return float(annual_dividend) / float(price)
        except (TypeError, ValueError, ZeroDivisionError):
            pass

    raw_yield = info.get("dividendYield")
    if raw_yield is None:
        return None
    try:
        value = float(raw_yield)
    except (TypeError, ValueError):
        return None
    # Newer yfinance versions return percentage points (0.34 means 0.34%).
    return value / 100 if value > 0.2 else value


def extract_metrics(info: dict, ticker: str) -> dict:
    """Normalize the yfinance info dict into FinSight's metric schema."""
    price = info.get("currentPrice") or info.get("regularMarketPrice")
    prev = info.get("previousClose") or info.get("regularMarketPreviousClose")
    change = None
    if price is not None and prev:
        change = round((price - prev) / prev * 100, 2)
    return {
        "ticker": ticker.upper(),
        "name": info.get("shortName") or info.get("longName"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "currency": info.get("currency"),
        "price": price,
        "change_percent": change,
        "market_cap": info.get("marketCap"),
        "trailing_pe": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "price_to_sales": info.get("priceToSalesTrailing12Months"),
        "profit_margin": info.get("profitMargins"),
        "operating_margin": info.get("operatingMargins"),
        "revenue_growth": info.get("revenueGrowth"),
        "earnings_growth": info.get("earningsGrowth"),
        "debt_to_equity": info.get("debtToEquity"),
        "current_ratio": info.get("currentRatio"),
        "free_cash_flow": info.get("freeCashflow"),
        "beta": info.get("beta"),
        "dividend_yield": normalize_dividend_yield(info, price),
        "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
        "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
        "analyst_target_mean": info.get("targetMeanPrice"),
        "recommendation": info.get("recommendationKey"),
        "summary": (info.get("longBusinessSummary") or "")[:600] or None,
    }


def get_overview(ticker: str) -> dict:
    info, fetched_at = _info_with_fetch_time(ticker)
    metrics = extract_metrics(info, ticker)
    as_of_date, has_provider_date = _provider_date(
        info.get("regularMarketTime"), fetched_at.date()
    )
    freshness = (
        freshness_for(as_of_date, fetched_at)
        if has_provider_date
        else FreshnessStatus.UNKNOWN.value
    )
    source_url = f"https://finance.yahoo.com/quote/{ticker.upper()}"

    source_fields = {
        "price": "currentPrice or regularMarketPrice",
        "change_percent": "derived from current price and previous close",
        "market_cap": "marketCap",
        "trailing_pe": "trailingPE",
        "forward_pe": "forwardPE",
        "price_to_sales": "priceToSalesTrailing12Months",
        "profit_margin": "profitMargins",
        "operating_margin": "operatingMargins",
        "revenue_growth": "revenueGrowth",
        "earnings_growth": "earningsGrowth",
        "debt_to_equity": "debtToEquity",
        "current_ratio": "currentRatio",
        "free_cash_flow": "freeCashflow",
        "beta": "beta",
        "dividend_yield": "derived from dividendRate and current price",
        "fifty_two_week_low": "fiftyTwoWeekLow",
        "fifty_two_week_high": "fiftyTwoWeekHigh",
        "analyst_target_mean": "targetMeanPrice",
    }
    currency_fields = {
        "price",
        "market_cap",
        "free_cash_flow",
        "fifty_two_week_low",
        "fifty_two_week_high",
        "analyst_target_mean",
    }
    ratio_fields = {
        "profit_margin",
        "operating_margin",
        "revenue_growth",
        "earnings_growth",
        "dividend_yield",
    }
    derived_fields = {"change_percent", "dividend_yield"}

    for key, source_field in source_fields.items():
        value = metrics.get(key)
        if value is None:
            continue
        unit = metrics.get("currency") if key in currency_fields else None
        if key in ratio_fields:
            unit = "ratio"
        elif key in {"change_percent", "debt_to_equity"}:
            unit = "percent"
        metrics[key] = data_point(
            value,
            unit=unit,
            **provenance(
                provider="FinSight" if key in derived_fields else "Yahoo Finance",
                source=(
                    f"FinSight normalization: {source_field}"
                    if key in derived_fields
                    else f"yfinance Ticker.info: {source_field}"
                ),
                as_of_date=as_of_date,
                fetched_at=fetched_at,
                freshness_status=freshness,
                confidence=0.8 if key in derived_fields else 0.9,
                source_url=source_url,
            ),
        )

    if metrics.get("summary"):
        metrics["summary"] = evidence(
            metrics["summary"],
            **provenance(
                provider="Yahoo Finance",
                source="yfinance Ticker.info: longBusinessSummary",
                as_of_date=as_of_date,
                fetched_at=fetched_at,
                freshness_status=freshness,
                confidence=0.8,
                source_url=source_url,
            ),
        )
    return metrics


def normalize_history_points(
    rows,
    *,
    ticker: str | None = None,
    fetched_at: datetime | None = None,
) -> list[dict]:
    """Convert provider rows to finite closing-price points."""
    fetched_at = fetched_at or datetime.now(timezone.utc)
    points = []
    for index, row in rows:
        try:
            close = float(row["Close"])
        except (KeyError, TypeError, ValueError):
            continue
        if not math.isfinite(close):
            continue
        point_date = index.date()
        normalized_close = round(close, 2)
        if ticker is None:
            # Pure normalization callers can still use the helper without API
            # provenance; get_history always supplies a ticker.
            points.append({"date": index.strftime("%Y-%m-%d"), "close": normalized_close})
            continue
        points.append(
            {
                "date": index.strftime("%Y-%m-%d"),
                "close": data_point(
                    normalized_close,
                    unit="price",
                    **provenance(
                        provider="Yahoo Finance",
                        source="yfinance Ticker.history: Close",
                        as_of_date=point_date,
                        fetched_at=fetched_at,
                        freshness_status=FreshnessStatus.HISTORICAL.value,
                        confidence=0.95,
                        source_url=f"https://finance.yahoo.com/quote/{ticker.upper()}/history",
                    ),
                ),
            }
        )
    return points


def get_history(ticker: str, period: str = "6mo") -> list[dict]:
    """Daily closing prices for a period (1mo, 3mo, 6mo, 1y, 5y)."""
    key = f"hist:{ticker.upper()}:{period}"
    cached = _cached(key)
    if cached is not None:
        return cached["points"]
    fetched_at = datetime.now(timezone.utc)
    hist = yf.Ticker(ticker).history(period=period)
    points = normalize_history_points(hist.iterrows(), ticker=ticker, fetched_at=fetched_at)
    _store(key, {"points": points})
    return points


def get_news(ticker: str, limit: int = 10) -> list[dict]:
    key = f"news:{ticker.upper()}"
    cached = _cached(key)
    if cached is not None:
        return cached["items"][:limit]
    raw = yf.Ticker(ticker).news or []
    fetched_at = datetime.now(timezone.utc)
    items = []
    for entry in raw:
        content = entry.get("content", entry)  # yfinance >=0.2.50 nests under "content"
        title = content.get("title")
        if not title:
            continue
        provider = content.get("provider") or {}
        url = (content.get("canonicalUrl") or {}).get("url") or content.get("link")
        published_raw = content.get("pubDate") or content.get("providerPublishTime")
        published_at = _published_at(published_raw)
        as_of_date, has_provider_date = _provider_date(published_raw, fetched_at.date())
        items.append(
            {
                "title": evidence(
                    title,
                    **provenance(
                        provider=(
                            provider.get("displayName")
                            or content.get("publisher")
                            or "Unknown publisher"
                        ),
                        source="Yahoo Finance news feed",
                        as_of_date=as_of_date,
                        fetched_at=fetched_at,
                        freshness_status=(
                            freshness_for(as_of_date, fetched_at, fresh_days=7)
                            if has_provider_date
                            else FreshnessStatus.UNKNOWN.value
                        ),
                        confidence=0.85,
                        source_url=url,
                    ),
                ),
                "publisher": provider.get("displayName") or content.get("publisher"),
                "link": url,
                "published_at": published_at,
            }
        )
    _store(key, {"items": items})
    return items[:limit]
