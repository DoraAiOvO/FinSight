"""Pydantic response models.

Financial values and claims deliberately carry their provenance alongside the
payload.  Keeping these two primitives in the API contract makes it difficult
for a new endpoint to accidentally return an unattributed number or narrative.
"""
from datetime import date, datetime, timezone
from enum import Enum
from typing import Literal, TypeAlias
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class FreshnessStatus(str, Enum):
    FRESH = "fresh"
    STALE = "stale"
    HISTORICAL = "historical"
    UNKNOWN = "unknown"


class AuditIssueCode(str, Enum):
    UNSUPPORTED_CLAIM = "unsupported_claim"
    STALE_EVIDENCE = "stale_evidence"
    MISSING_CITATION = "missing_citation"
    CONFLICTING_SOURCES = "conflicting_sources"
    INCORRECT_UNIT = "incorrect_unit"
    INCONSISTENT_NUMBER = "inconsistent_number"


class AuditSeverity(str, Enum):
    WARNING = "warning"
    BLOCKING = "blocking"


class AuditStatus(str, Enum):
    PASSED = "passed"
    WARNING = "warning"
    BLOCKED = "blocked"


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


class AssistantIntent(str, Enum):
    SITE_HELP = "SITE_HELP"
    FINANCIAL_CONCEPT = "FINANCIAL_CONCEPT"
    COMPANY_LOOKUP = "COMPANY_LOOKUP"
    CURRENT_REPORT_QUESTION = "CURRENT_REPORT_QUESTION"
    COMPARISON_REQUEST = "COMPARISON_REQUEST"
    RECOMMENDATION_OR_PREDICTION = "RECOMMENDATION_OR_PREDICTION"
    GENERAL_EDUCATION = "GENERAL_EDUCATION"


class AssistantRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"


class ThesisStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class AssumptionConditionType(str, Enum):
    METRIC = "metric"
    EVENT = "event"


class AssumptionOperator(str, Enum):
    GREATER_THAN = ">"
    GREATER_THAN_OR_EQUAL = ">="
    LESS_THAN = "<"
    LESS_THAN_OR_EQUAL = "<="
    EQUAL = "=="
    NOT_EQUAL = "!="


class AssumptionStatus(str, Enum):
    UNREVIEWED = "unreviewed"
    MONITORING = "monitoring"
    SUPPORTED = "supported"
    CHALLENGED = "challenged"
    INVALIDATED = "invalidated"


class ValuationScenario(str, Enum):
    CONSERVATIVE = "conservative"
    BASE = "base"
    OPTIMISTIC = "optimistic"


class PeerMultipleMethod(str, Enum):
    TRAILING_PE = "trailing_pe"
    PRICE_TO_SALES = "price_to_sales"


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


class EvidenceStatement(BaseModel):
    """One independently auditable statement inside a generated conclusion."""

    text: str = Field(min_length=1)
    citations: list[str] = Field(default_factory=list)


class Evidence(Provenance):
    """A sourced or generated claim plus its provenance."""

    claim: str
    generated: bool = False
    citations: list[str] = Field(default_factory=list)
    statements: list[EvidenceStatement] = Field(default_factory=list)


class AssistantMessage(BaseModel):
    role: AssistantRole
    content: str = Field(min_length=1, max_length=2000)

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str):
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("message cannot be empty")
        return normalized


class AssistantReportEvidence(BaseModel):
    """One already-rendered report fact the assistant may quote verbatim."""

    evidence_id: str = Field(min_length=1, max_length=160)
    label: str = Field(min_length=1, max_length=200)
    value: str = Field(min_length=1, max_length=1000)
    source: str = Field(min_length=1, max_length=300)
    as_of_date: date | None = None
    source_url: str | None = Field(default=None, max_length=2000)


class AssistantReportContext(BaseModel):
    ticker: str = Field(min_length=1, max_length=80)
    company_name: str | None = Field(default=None, max_length=200)
    report_id: UUID | None = None
    evidence: list[AssistantReportEvidence] = Field(default_factory=list, max_length=80)


class AssistantCitation(BaseModel):
    evidence_id: str
    title: str
    source: str
    as_of_date: date | None = None
    source_url: str | None = None


class AssistantChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[AssistantMessage] = Field(default_factory=list, max_length=30)
    website_language: PreferredLanguage = PreferredLanguage.ENGLISH
    customer_id: UUID | None = None
    report_id: UUID | None = None
    current_report: AssistantReportContext | None = None

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str):
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("message cannot be empty")
        return normalized

    @model_validator(mode="after")
    def report_id_requires_customer(self):
        if self.report_id is not None and self.customer_id is None:
            raise ValueError("customer_id is required when report_id is used")
        return self


class AssistantChatResponse(BaseModel):
    reply: str
    intent: AssistantIntent
    detected_language: str
    detected_languages: list[str]
    code_switched: bool = False
    explanation_depth: ExplanationDepth = ExplanationDepth.STANDARD
    citations: list[AssistantCitation] = Field(default_factory=list)
    used_llm: bool = False
    grounded: bool = False
    context_truncated: bool = False


class AuditIssue(BaseModel):
    code: AuditIssueCode
    severity: AuditSeverity
    section: str
    path: str
    message: str
    claim: str | None = None
    related_paths: list[str] = Field(default_factory=list)


class EvidenceAudit(BaseModel):
    status: AuditStatus
    audited_at: datetime
    checks_performed: list[AuditIssueCode]
    issues: list[AuditIssue] = Field(default_factory=list)
    issue_counts: dict[AuditIssueCode, int] = Field(default_factory=dict)
    blocked_paths: list[str] = Field(default_factory=list)
    blocked_statements: int = 0
    evidence_checked: int = 0
    data_points_checked: int = 0
    factual_conclusions_allowed: bool = True


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


class ValuationAssumptions(BaseModel):
    projection_years: int = Field(default=5, ge=3, le=10)
    revenue_growth: float = Field(ge=-0.5, le=1.0)
    free_cash_flow_margin: float = Field(ge=-0.5, le=0.8)
    discount_rate: float = Field(ge=0.02, le=0.5)
    terminal_growth: float = Field(ge=-0.05, le=0.1)
    annual_share_dilution: float = Field(default=0, ge=-0.1, le=0.25)

    @model_validator(mode="after")
    def discount_rate_exceeds_terminal_growth(self):
        if self.discount_rate <= self.terminal_growth:
            raise ValueError("discount_rate must exceed terminal_growth")
        return self


class ValuationAssumptionSet(BaseModel):
    projection_years: int
    revenue_growth: DataPoint
    free_cash_flow_margin: DataPoint
    discount_rate: DataPoint
    terminal_growth: DataPoint
    annual_share_dilution: DataPoint


class ValuationInputSet(BaseModel):
    total_revenue: DataPoint
    free_cash_flow: DataPoint
    total_cash: DataPoint
    total_debt: DataPoint
    shares_outstanding: DataPoint
    current_price: DataPoint
    trailing_eps: DataPoint | None = None


class DcfProjectionYear(BaseModel):
    year: int
    projected_revenue: DataPoint
    projected_free_cash_flow: DataPoint
    diluted_shares: DataPoint
    discount_factor: DataPoint
    present_value: DataPoint


class DcfResult(BaseModel):
    assumptions: ValuationAssumptionSet
    projections: list[DcfProjectionYear]
    present_value_explicit_cash_flows: DataPoint
    terminal_value: DataPoint
    present_value_terminal_value: DataPoint
    enterprise_value: DataPoint
    equity_value: DataPoint
    intrinsic_value_per_share: DataPoint
    current_price: DataPoint
    upside_downside: DataPoint


class ReverseDcfResult(BaseModel):
    target_price: DataPoint
    implied_revenue_growth: DataPoint | None = None
    search_lower_bound: DataPoint
    search_upper_bound: DataPoint
    converged: bool
    explanation: Evidence


class PeerMultipleEstimate(BaseModel):
    method: PeerMultipleMethod
    peer_median_multiple: DataPoint
    company_basis: DataPoint
    implied_value_per_share: DataPoint
    sample_size: int = Field(ge=2)
    peer_tickers: list[str] = Field(default_factory=list)
    explanation: Evidence


class SensitivityCell(BaseModel):
    terminal_growth: DataPoint
    intrinsic_value_per_share: DataPoint | None = None


class SensitivityRow(BaseModel):
    discount_rate: DataPoint
    cells: list[SensitivityCell]


class SensitivityAnalysis(BaseModel):
    terminal_growth_rates: list[DataPoint]
    rows: list[SensitivityRow]


class ScenarioValuation(BaseModel):
    scenario: ValuationScenario
    dcf: DcfResult


class MarginOfSafetyRange(BaseModel):
    low: DataPoint
    base: DataPoint
    high: DataPoint
    current_price: DataPoint


class ValuationResponse(BaseModel):
    ticker: str
    currency: str
    inputs: ValuationInputSet
    base_case: DcfResult
    reverse_dcf: ReverseDcfResult
    peer_multiples: list[PeerMultipleEstimate] = Field(default_factory=list)
    scenarios: list[ScenarioValuation]
    margin_of_safety_range: MarginOfSafetyRange
    sensitivity: SensitivityAnalysis
    methodology: Evidence
    limitations: list[Evidence] = Field(default_factory=list)
    disclaimer: str


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


class ThesisEvidence(BaseModel):
    claim: str = Field(min_length=1, max_length=2000)
    source: str = Field(min_length=1, max_length=300)
    source_url: str | None = Field(default=None, max_length=2000)
    as_of_date: date = Field(default_factory=date.today)
    recorded_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    confidence: float = Field(default=0.5, ge=0, le=1)

    @field_validator("claim", "source")
    @classmethod
    def normalize_required_text(cls, value: str):
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("value cannot be empty")
        return normalized

    @field_validator("source_url")
    @classmethod
    def normalize_optional_url(cls, value: str | None):
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class ThesisAssumptionCreate(BaseModel):
    description: str = Field(min_length=1, max_length=2000)
    condition_type: AssumptionConditionType
    metric_key: str | None = Field(default=None, max_length=120)
    operator: AssumptionOperator | None = None
    target_value: str | None = Field(default=None, max_length=120)
    event_condition: str | None = Field(default=None, max_length=2000)
    current_status: AssumptionStatus = AssumptionStatus.UNREVIEWED
    supporting_evidence: list[ThesisEvidence] = Field(
        default_factory=list, max_length=20
    )
    contradicting_evidence: list[ThesisEvidence] = Field(
        default_factory=list, max_length=20
    )
    position: int = Field(default=0, ge=0, le=100)

    @field_validator("description", "metric_key", "target_value", "event_condition")
    @classmethod
    def normalize_assumption_text(cls, value: str | None):
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None

    @model_validator(mode="after")
    def condition_is_complete(self):
        if not self.description:
            raise ValueError("description cannot be empty")
        if self.condition_type == AssumptionConditionType.METRIC:
            if not self.metric_key or self.operator is None or not self.target_value:
                raise ValueError(
                    "metric conditions require metric_key, operator, and target_value"
                )
            if self.event_condition is not None:
                raise ValueError("metric conditions cannot include event_condition")
        else:
            if not self.event_condition:
                raise ValueError("event conditions require event_condition")
            if any(
                value is not None
                for value in (self.metric_key, self.operator, self.target_value)
            ):
                raise ValueError("event conditions cannot include metric fields")
        return self


class ThesisAssumptionUpdate(BaseModel):
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    condition_type: AssumptionConditionType | None = None
    metric_key: str | None = Field(default=None, max_length=120)
    operator: AssumptionOperator | None = None
    target_value: str | None = Field(default=None, max_length=120)
    event_condition: str | None = Field(default=None, max_length=2000)
    current_status: AssumptionStatus | None = None
    supporting_evidence: list[ThesisEvidence] | None = Field(
        default=None, max_length=20
    )
    contradicting_evidence: list[ThesisEvidence] | None = Field(
        default=None, max_length=20
    )
    position: int | None = Field(default=None, ge=0, le=100)
    change_reason: str | None = Field(default=None, max_length=1000)

    @field_validator(
        "description", "metric_key", "target_value", "event_condition", "change_reason"
    )
    @classmethod
    def normalize_update_text(cls, value: str | None):
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None


class ThesisAssumptionHistoryResponse(BaseModel):
    id: UUID
    change_type: Literal["created", "updated", "status_changed"]
    reason: str | None = None
    previous_values: dict | None = None
    current_values: dict
    changed_at: datetime


class ThesisAssumptionResponse(ThesisAssumptionCreate):
    id: UUID
    last_evaluated_at: datetime | None = None
    history: list[ThesisAssumptionHistoryResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ThesisCreate(BaseModel):
    ticker: str = Field(min_length=1, max_length=32)
    title: str = Field(min_length=1, max_length=200)
    statement: str = Field(min_length=1, max_length=5000)
    status: ThesisStatus = ThesisStatus.ACTIVE
    confidence: float | None = Field(default=None, ge=0, le=1)
    research_session_id: UUID | None = None
    assumptions: list[ThesisAssumptionCreate] = Field(
        default_factory=list, max_length=20
    )

    @field_validator("title", "statement")
    @classmethod
    def normalize_thesis_text(cls, value: str):
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("value cannot be empty")
        return normalized


class ThesisUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    statement: str | None = Field(default=None, min_length=1, max_length=5000)
    status: ThesisStatus | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)

    @field_validator("title", "statement")
    @classmethod
    def normalize_optional_thesis_text(cls, value: str | None):
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None


class ThesisResponse(BaseModel):
    id: UUID
    ticker: str
    title: str
    statement: str
    status: ThesisStatus
    confidence: float | None = None
    research_session_id: UUID | None = None
    assumptions: list[ThesisAssumptionResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ThesisAssumptionSnapshot(BaseModel):
    assumption_id: UUID | None = None
    description: str = Field(min_length=1, max_length=2000)
    current_status: str = Field(min_length=1, max_length=32)
    condition_type: AssumptionConditionType | None = None
    metric_key: str | None = Field(default=None, max_length=120)
    operator: AssumptionOperator | None = None
    target_value: str | None = Field(default=None, max_length=120)
    event_condition: str | None = Field(default=None, max_length=2000)


class ResearchSnapshot(BaseModel):
    captured_at: datetime
    overview: Overview
    analysis: AnalysisResponse | None = None
    news: NewsResponse | None = None
    filings: FilingListResponse | None = None
    valuation: ValuationResponse | None = None
    thesis_assumptions: list[ThesisAssumptionSnapshot] = Field(default_factory=list)
    audit: EvidenceAudit | None = None


class ResearchReportDraft(BaseModel):
    captured_at: datetime
    overview: Overview | None = None
    history: HistoryResponse | None = None
    analysis: AnalysisResponse | None = None
    news: NewsResponse | None = None
    filings: FilingListResponse | None = None
    valuation: ValuationResponse | None = None
    comparison: CompareResponse | None = None

    @model_validator(mode="after")
    def contains_a_report(self):
        if self.overview is None and self.comparison is None:
            raise ValueError("overview or comparison is required")
        if self.overview is None and any(
            section is not None
            for section in (
                self.history,
                self.analysis,
                self.news,
                self.filings,
                self.valuation,
            )
        ):
            raise ValueError("company report sections require an overview")
        return self


class ResearchReportAuditResponse(BaseModel):
    report: ResearchReportDraft
    audit: EvidenceAudit


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
