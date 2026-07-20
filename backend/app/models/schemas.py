"""Pydantic response models.

Financial values and claims deliberately carry their provenance alongside the
payload.  Keeping these two primitives in the API contract makes it difficult
for a new endpoint to accidentally return an unattributed number or narrative.
"""
from datetime import date, datetime
from enum import Enum
from typing import TypeAlias

from pydantic import BaseModel, Field


class FreshnessStatus(str, Enum):
    FRESH = "fresh"
    STALE = "stale"
    HISTORICAL = "historical"
    UNKNOWN = "unknown"


class Provenance(BaseModel):
    provider: str
    source: str
    as_of_date: date
    fetched_at: datetime
    freshness_status: FreshnessStatus
    confidence: float = Field(ge=0, le=1)
    source_url: str | None = None


DataValue: TypeAlias = float | int | str | None


class DataPoint(Provenance):
    """A financial value plus enough context to independently verify it."""

    value: DataValue
    unit: str | None = None
    display_value: str | None = None


class Evidence(Provenance):
    """A sourced or generated claim plus its provenance."""

    claim: str


class Overview(BaseModel):
    ticker: str
    name: str | None = None
    sector: str | None = None
    industry: str | None = None
    currency: str | None = None
    price: DataPoint | None = None
    change_percent: DataPoint | None = None
    market_cap: DataPoint | None = None
    trailing_pe: DataPoint | None = None
    forward_pe: DataPoint | None = None
    price_to_sales: DataPoint | None = None
    profit_margin: DataPoint | None = None
    operating_margin: DataPoint | None = None
    revenue_growth: DataPoint | None = None
    earnings_growth: DataPoint | None = None
    debt_to_equity: DataPoint | None = None
    current_ratio: DataPoint | None = None
    free_cash_flow: DataPoint | None = None
    beta: DataPoint | None = None
    dividend_yield: DataPoint | None = None
    fifty_two_week_low: DataPoint | None = None
    fifty_two_week_high: DataPoint | None = None
    analyst_target_mean: DataPoint | None = None
    recommendation: str | None = None
    summary: Evidence | None = None


class PricePoint(BaseModel):
    date: str
    close: DataPoint


class HistoryResponse(BaseModel):
    ticker: str
    period: str
    points: list[PricePoint]


class NewsItem(BaseModel):
    title: Evidence
    publisher: str | None = None
    link: str | None = None
    published_at: str | None = None


class NewsResponse(BaseModel):
    ticker: str
    items: list[NewsItem]
    ai_summary: Evidence | None = None


class EvidenceItem(BaseModel):
    metric: str
    value: DataPoint
    benchmark: Evidence
    metric_key: str | None = None
    benchmark_key: str | None = None
    benchmark_params: dict[str, str] = Field(default_factory=dict)


class Insight(BaseModel):
    code: str
    kind: str  # "risk" | "opportunity"
    title: Evidence
    severity: str  # "low" | "medium" | "high"
    explanation: Evidence
    evidence: list[EvidenceItem]


class AnalysisResponse(BaseModel):
    ticker: str
    insights: list[Insight]
    ai_narrative: Evidence | None = None
    disclaimer: str


class CompareRow(BaseModel):
    metric: str
    label: str
    values: dict[str, DataPoint | None]
    best: Evidence | None = None
    higher_is_better: bool | None = None


class CompareResponse(BaseModel):
    tickers: list[str]
    rows: list[CompareRow]
