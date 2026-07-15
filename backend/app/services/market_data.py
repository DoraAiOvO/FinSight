"""Market data access layer built on yfinance, with a small in-memory cache."""
import time

import yfinance as yf

from ..config import settings

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
        "dividend_yield": info.get("dividendYield"),
        "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
        "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
        "analyst_target_mean": info.get("targetMeanPrice"),
        "recommendation": info.get("recommendationKey"),
        "summary": (info.get("longBusinessSummary") or "")[:600] or None,
    }


def get_overview(ticker: str) -> dict:
    return extract_metrics(get_raw_info(ticker), ticker)


def get_history(ticker: str, period: str = "6mo") -> list[dict]:
    """Daily closing prices for a period (1mo, 3mo, 6mo, 1y, 5y)."""
    key = f"hist:{ticker.upper()}:{period}"
    cached = _cached(key)
    if cached is not None:
        return cached["points"]
    hist = yf.Ticker(ticker).history(period=period)
    points = [
        {"date": idx.strftime("%Y-%m-%d"), "close": round(float(row["Close"]), 2)}
        for idx, row in hist.iterrows()
    ]
    _store(key, {"points": points})
    return points


def get_news(ticker: str, limit: int = 10) -> list[dict]:
    key = f"news:{ticker.upper()}"
    cached = _cached(key)
    if cached is not None:
        return cached["items"][:limit]
    raw = yf.Ticker(ticker).news or []
    items = []
    for entry in raw:
        content = entry.get("content", entry)  # yfinance >=0.2.50 nests under "content"
        title = content.get("title")
        if not title:
            continue
        provider = content.get("provider") or {}
        url = (content.get("canonicalUrl") or {}).get("url") or content.get("link")
        items.append(
            {
                "title": title,
                "publisher": provider.get("displayName") or content.get("publisher"),
                "link": url,
                "published_at": content.get("pubDate") or content.get("providerPublishTime"),
            }
        )
    _store(key, {"items": items})
    return items[:limit]
