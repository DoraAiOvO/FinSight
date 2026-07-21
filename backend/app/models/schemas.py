"""Pydantic response models.

Financial values and claims deliberately carry their provenance alongside the
payload.  Keeping these two primitives in the API contract makes it difficult
for a new endpoint to accidentally return an unattributed number or narrative.
"""
from datetime import date, datetime
from enum import Enum
from typing import Literal, TypeAlias
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class FreshnessStatus(str, Enum):
    FRESH = "fresh"
    STALE = "stale"
    HISTORICAL = "historical"
    UNKNOWN = "unknown"


class ExperienceLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class ResearchHorizon(str, Enum):
    SHORT_TERM = "short_term"
    ONE_TO_THREE_YEARS = "one_to_three_years"
    FIVE_PLUS_YEARS = "five_plus_years"


class ResearchPriority(str, Enum):
    GROWTH = "growth"
    STABILITY = "stability"
    INCOME = "income"
    VALUE = "value"
    INNOVATION = "innovation"


class RiskComfort(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ReportDepth(str, Enum):
    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


class PreferredLanguage(str, Enum):
    ENGLISH = "en"
    SPANISH = "es"
    FRENCH = "fr"
    CHINESE = "zh"


class ExplanationDepth(str, Enum):
    SIMPLE = "simple"
    STANDARD = "standard"
    PROFESSIONAL = "professional"


class ReportSection(str, Enum):
    OVERVIEW = "overview"
    ANALYSIS = "analysis"
    PRICE_HISTORY = "price_history"
    NEWS = "news"


class CustomerProfilePreferences(BaseModel):
    experience_level: ExperienceLevel
    research_horizon: ResearchHorizon
    priorities: list[ResearchPriority] = Field(min_length=1, max_length=5)
    risk_comfort: RiskComfort
    preferred_report_depth: ReportDepth
    preferred_language: PreferredLanguage
    industries_of_interest: list[str] = Field(min_length=1, max_length=8)

    @field_validator("priorities")
    @classmethod
    def priorities_are_unique(cls, values: list[ResearchPriority]):
        if len(values) != len(set(values)):
            raise ValueError("priorities must be unique")
        return values

    @field_validator("industries_of_interest")
    @classmethod
    def normalize_industries(cls, values: list[str]):
        normalized = [value.strip() for value in values]
        if any(not value or len(value) > 80 for value in normalized):
            raise ValueError("industries must contain 1 to 80 characters")
        if len({value.casefold() for value in normalized}) != len(normalized):
            raise ValueError("industries must be unique")
        return normalized


class CustomerProfileResponse(CustomerProfilePreferences):
    customer_id: UUID
    created_at: datetime
    updated_at: datetime


class ReportPresentation(BaseModel):
    personalized: bool = False
    section_order: list[ReportSection] = Field(
        default_factory=lambda: [
            ReportSection.OVERVIEW,
            ReportSection.PRICE_HISTORY,
            ReportSection.ANALYSIS,
            ReportSection.NEWS,
        ]
    )
    explanation_depth: ExplanationDepth = ExplanationDepth.STANDARD
    report_depth: ReportDepth = ReportDepth.STANDARD
    highlighted_insight_codes: list[str] = Field(default_factory=list)
    highlighted_metric_keys: list[str] = Field(default_factory=list)
    industry_match: bool = False


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
    exchange: str | None = None
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
    total_revenue: DataPoint | None = None
    free_cash_flow_margin: DataPoint | None = None
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


class BenchmarkReference(BaseModel):
    scope: Literal["industry", "sector", "peers", "historical"]
    name: str
    median: DataPoint
    lower_bound: DataPoint
    upper_bound: DataPoint
    range_kind: Literal["middle_50_percent", "observed_range"]
    sample_size: int = Field(ge=1)
    sample_tickers: list[str] = Field(default_factory=list)
    period: str | None = None
    rationale: Evidence
    rationale_key: str
    rationale_params: dict[str, str] = Field(default_factory=dict)


class MetricBenchmark(BaseModel):
    metric_key: str
    label: str
    company_value: DataPoint
    references: list[BenchmarkReference]
    primary_scope: Literal["industry", "sector", "peers", "historical"] | None = None
    primary_rationale: Evidence | None = None


class SelectedPeer(BaseModel):
    ticker: str
    name: str | None = None
    sector: str | None = None
    industry: str | None = None
    market_cap: DataPoint | None = None
    selection_reason: Evidence
    selection_reason_key: str
    selection_reason_params: dict[str, str] = Field(default_factory=dict)


class BenchmarkContext(BaseModel):
    industry: str | None = None
    sector: str | None = None
    selected_peers: list[SelectedPeer] = Field(default_factory=list)
    metrics: list[MetricBenchmark] = Field(default_factory=list)
    methodology: Evidence
    limitations: list[Evidence] = Field(default_factory=list)


class Insight(BaseModel):
    code: str
    kind: str  # "risk" | "opportunity"
    title: Evidence
    severity: str  # "low" | "medium" | "high"
    explanation: Evidence
    evidence: list[EvidenceItem]
    highlighted: bool = False


class AnalysisResponse(BaseModel):
    ticker: str
    insights: list[Insight]
    benchmarks: BenchmarkContext
    ai_narrative: Evidence | None = None
    presentation: ReportPresentation = Field(default_factory=ReportPresentation)
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


class CacheMetadata(BaseModel):
    hit: bool
    fetched_at: datetime
    expires_at: datetime


class FilingSummary(BaseModel):
    accession_number: str
    filing_type: Literal["10-K", "10-Q", "8-K"]
    filing_date: date
    report_date: date | None = None
    accepted_at: datetime | None = None
    primary_document: str
    items: list[str] = Field(default_factory=list)
    description: str | None = None
    is_earnings_related: bool = False
    source_url: str
    index_url: str


class FilingListResponse(BaseModel):
    ticker: str
    company_name: str
    cik: str
    filings: list[FilingSummary]
    source: Provenance
    cache: CacheMetadata


class FilingSection(BaseModel):
    section_id: str
    item: str
    title: str
    text: str
    character_count: int
    truncated: bool = False
    source_url: str


class FilingDetailResponse(BaseModel):
    ticker: str
    company_name: str
    cik: str
    filing: FilingSummary
    sections: list[FilingSection]
    source: Provenance
    cache: CacheMetadata


class FilingQuestionRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    lang: PreferredLanguage = PreferredLanguage.ENGLISH

    @field_validator("question")
    @classmethod
    def question_is_meaningful(cls, value: str):
        normalized = " ".join(value.split())
        if len(normalized) < 3:
            raise ValueError("question must contain at least 3 characters")
        return normalized


class FilingCitation(BaseModel):
    section_id: str
    section_title: str
    quote: str
    source_url: str


class FilingQuestionResponse(BaseModel):
    ticker: str
    accession_number: str
    question: str
    answer: Evidence
    citations: list[FilingCitation]
    answered_at: datetime
    ai_used: bool


class WatchlistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    is_default: bool = False

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str):
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("watchlist name cannot be empty")
        return normalized


class WatchlistItemCreate(BaseModel):
    ticker: str = Field(min_length=1, max_length=32)
    notes: str | None = Field(default=None, max_length=2000)


class WatchlistItemResponse(BaseModel):
    id: UUID
    ticker: str
    notes: str | None = None
    added_at: datetime


class WatchlistResponse(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    is_default: bool
    items: list[WatchlistItemResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ThesisAssumptionSnapshot(BaseModel):
    assumption_id: UUID | None = None
    description: str = Field(min_length=1, max_length=2000)
    current_status: str = Field(min_length=1, max_length=32)
    metric_key: str | None = Field(default=None, max_length=120)
    target_value: str | None = Field(default=None, max_length=120)


class ResearchSnapshot(BaseModel):
    captured_at: datetime
    overview: Overview
    analysis: AnalysisResponse | None = None
    news: NewsResponse | None = None
    filings: FilingListResponse | None = None
    thesis_assumptions: list[ThesisAssumptionSnapshot] = Field(default_factory=list)


class ResearchSessionCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    language: PreferredLanguage = PreferredLanguage.ENGLISH
    snapshot: ResearchSnapshot

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None):
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None


class ResearchSessionSummary(BaseModel):
    id: UUID
    ticker: str
    title: str | None = None
    status: str
    language: PreferredLanguage
    created_at: datetime
    completed_at: datetime | None = None


class ResearchSessionResponse(ResearchSessionSummary):
    snapshot: ResearchSnapshot


class WhatChangedRequest(BaseModel):
    snapshot: ResearchSnapshot
    baseline_session_id: UUID | None = None


ChangeDirection = Literal[
    "new",
    "removed",
    "improved",
    "worsened",
    "changed",
    "resolved",
    "unchanged",
]


class MetricChange(BaseModel):
    metric_key: str
    label: str
    direction: ChangeDirection
    previous: DataPoint | None = None
    current: DataPoint | None = None
    relative_change: float | None = None


class NewsChange(BaseModel):
    change_key: str
    direction: Literal["new", "removed"]
    item: NewsItem


class FilingChange(BaseModel):
    accession_number: str
    direction: Literal["new"] = "new"
    filing: FilingSummary


class SignalChange(BaseModel):
    code: str
    kind: Literal["risk", "opportunity"]
    direction: ChangeDirection
    title: Evidence
    previous_severity: str | None = None
    current_severity: str | None = None


class ThesisAssumptionChange(BaseModel):
    change_key: str
    description: str
    direction: ChangeDirection
    previous_status: str | None = None
    current_status: str | None = None


class ChangeSummary(BaseModel):
    new: int = 0
    improved: int = 0
    worsened: int = 0
    changed: int = 0
    resolved: int = 0
    unchanged: int = 0


class WhatChangedResponse(BaseModel):
    ticker: str
    compared_at: datetime
    has_baseline: bool
    baseline_session: ResearchSessionSummary | None = None
    summary: ChangeSummary = Field(default_factory=ChangeSummary)
    financial_metrics: list[MetricChange] = Field(default_factory=list)
    news: list[NewsChange] = Field(default_factory=list)
    filings: list[FilingChange] = Field(default_factory=list)
    risk_signals: list[SignalChange] = Field(default_factory=list)
    opportunity_signals: list[SignalChange] = Field(default_factory=list)
    thesis_assumptions: list[ThesisAssumptionChange] = Field(default_factory=list)
