"""Unit tests for standardized provenance primitives."""
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.models.schemas import DataPoint, Evidence  # noqa: E402
from app.services.provenance import (  # noqa: E402
    freshness_for,
    generated_evidence,
    inherited_provenance,
)


def test_data_point_and_evidence_require_complete_provenance():
    common = {
        "provider": "Yahoo Finance",
        "source": "Ticker.info: currentPrice",
        "as_of_date": date(2026, 7, 19),
        "fetched_at": datetime(2026, 7, 20, tzinfo=timezone.utc),
        "freshness_status": "fresh",
        "confidence": 0.9,
        "source_url": "https://finance.yahoo.com/quote/TEST",
    }

    assert DataPoint(value=42.0, unit="USD", **common).value == 42.0
    assert Evidence(claim="Revenue is growing.", **common).claim.endswith("growing.")


def test_inherited_provenance_uses_most_conservative_input():
    base = {
        "as_of_date": date(2026, 7, 18),
        "fetched_at": datetime(2026, 7, 20, tzinfo=timezone.utc),
        "provider": "Yahoo Finance",
        "source": "test",
        "source_url": None,
    }
    meta = inherited_provenance(
        [
            {**base, "freshness_status": "fresh", "confidence": 0.9},
            {**base, "freshness_status": "stale", "confidence": 0.7},
        ],
        confidence=0.85,
    )

    assert meta["freshness_status"] == "stale"
    assert meta["confidence"] == 0.7


def test_freshness_and_generated_claim_metadata():
    fetched_at = datetime(2026, 7, 20, tzinfo=timezone.utc)
    assert freshness_for(date(2026, 7, 18), fetched_at) == "fresh"
    assert freshness_for(date(2026, 7, 1), fetched_at) == "stale"

    claim = generated_evidence(
        "A concise synthesis.",
        provider="Anthropic",
        source="claude-test",
        confidence=0.6,
        fetched_at=fetched_at,
    )
    assert claim["provider"] == "Anthropic"
    assert claim["as_of_date"] == fetched_at.date()
    assert claim["confidence"] == 0.6
