"""Ticker input validation shared by API routes."""
import re


_TICKER_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9.-]{0,9}$")


def normalize_ticker(value: str) -> str:
    """Return a normalized Yahoo Finance-style equity ticker."""
    ticker = value.strip().upper()
    if not _TICKER_PATTERN.fullmatch(ticker):
        raise ValueError(
            "Use a valid ticker with up to 10 letters, numbers, periods, or hyphens"
        )
    return ticker


def normalize_comparison(value: str, minimum: int = 2, maximum: int = 5) -> list[str]:
    """Parse a comma-separated ticker list, preserving order and rejecting duplicates."""
    raw = [part.strip() for part in value.split(",") if part.strip()]
    if len(raw) < minimum:
        raise ValueError(f"Provide at least {minimum} tickers")
    if len(raw) > maximum:
        raise ValueError(f"Compare up to {maximum} tickers at a time")

    tickers = [normalize_ticker(part) for part in raw]
    if len(set(tickers)) != len(tickers):
        raise ValueError("Each comparison ticker must be unique")
    return tickers
