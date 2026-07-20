"""Helpers for building and consuming provenance-aware API values."""
from datetime import date, datetime, timezone
from typing import Iterable

from ..models.schemas import FreshnessStatus


FRESHNESS_RANK = {
    FreshnessStatus.FRESH.value: 0,
    FreshnessStatus.HISTORICAL.value: 1,
    FreshnessStatus.UNKNOWN.value: 2,
    FreshnessStatus.STALE.value: 3,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def data_value(value):
    """Return the scalar from either a DataPoint dict/model or a raw value."""
    if value is None:
        return None
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    if hasattr(value, "value"):
        return value.value
    return value


def evidence_text(value):
    """Return claim text from either an Evidence dict/model or a raw string."""
    if value is None:
        return None
    if isinstance(value, dict) and "claim" in value:
        return value["claim"]
    if hasattr(value, "claim"):
        return value.claim
    return value


def freshness_for(as_of_date: date, fetched_at: datetime, fresh_days: int = 3) -> str:
    """Classify source recency without pretending an unknown date is current."""
    age_days = (fetched_at.date() - as_of_date).days
    return (
        FreshnessStatus.FRESH.value
        if age_days <= fresh_days
        else FreshnessStatus.STALE.value
    )


def provenance(
    *,
    provider: str,
    source: str,
    as_of_date: date,
    fetched_at: datetime,
    freshness_status: str,
    confidence: float,
    source_url: str | None = None,
) -> dict:
    return {
        "provider": provider,
        "source": source,
        "as_of_date": as_of_date,
        "fetched_at": fetched_at,
        "freshness_status": freshness_status,
        "confidence": confidence,
        "source_url": source_url,
    }


def data_point(
    value,
    *,
    unit: str | None = None,
    display_value: str | None = None,
    **meta,
) -> dict:
    return {
        "value": value,
        "unit": unit,
        "display_value": display_value,
        **meta,
    }


def evidence(claim: str, **meta) -> dict:
    return {"claim": claim, **meta}


def inherited_provenance(
    inputs: Iterable[dict | None],
    *,
    provider: str = "FinSight",
    source: str = "deterministic analysis rules v1",
    confidence: float | None = None,
) -> dict:
    """Build conservative metadata for a value/claim derived from input points."""
    points = [point for point in inputs if isinstance(point, dict)]
    now = utc_now()
    if not points:
        return provenance(
            provider=provider,
            source=source,
            as_of_date=now.date(),
            fetched_at=now,
            freshness_status=FreshnessStatus.UNKNOWN.value,
            confidence=confidence if confidence is not None else 0.5,
        )

    as_of = min(point["as_of_date"] for point in points)
    fetched_at = max(point["fetched_at"] for point in points)
    statuses = [str(point["freshness_status"]) for point in points]
    freshness = max(statuses, key=lambda status: FRESHNESS_RANK.get(status, 2))
    input_confidence = min(float(point["confidence"]) for point in points)
    return provenance(
        provider=provider,
        source=source,
        as_of_date=as_of,
        fetched_at=fetched_at,
        freshness_status=freshness,
        confidence=(
            min(input_confidence, confidence)
            if confidence is not None
            else input_confidence
        ),
    )


def generated_evidence(
    claim: str | None,
    *,
    provider: str,
    source: str,
    confidence: float,
    fetched_at: datetime | None = None,
) -> dict | None:
    if not claim:
        return None
    fetched_at = fetched_at or utc_now()
    return evidence(
        claim,
        **provenance(
            provider=provider,
            source=source,
            as_of_date=fetched_at.date(),
            fetched_at=fetched_at,
            freshness_status=FreshnessStatus.FRESH.value,
            confidence=confidence,
        ),
    )
