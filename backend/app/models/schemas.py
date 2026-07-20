"""Pydantic response models."""
from pydantic import BaseModel, Field


class Overview(BaseModel):
    ticker: str
    name: str | None = None
    sector: str | None = None
    industry: str | None = None
    currency: str | None = None
    price: float | None = None
    change_percent: float | None = None
    market_cap: float | None = None
    trailing_pe: float | None = None
    forward_pe: float | None = None
    price_to_sales: float | None = None
    profit_margin: float | None = None
    operating_margin: float | None = None
    revenue_growth: float | None = None
    earnings_growth: float | None = None
    debt_to_equity: float | None = None
    current_ratio: float | None = None
    free_cash_flow: float | None = None
    beta: float | None = None
    dividend_yield: float | None = None
    fifty_two_week_low: float | None = None
    fifty_two_week_high: float | None = None
    analyst_target_mean: float | None = None
    recommendation: str | None = None
    summary: str | None = None


class PricePoint(BaseModel):
    date: str
    close: float


class HistoryResponse(BaseModel):
    ticker: str
    period: str
    points: list[PricePoint]


class NewsItem(BaseModel):
    title: str
    publisher: str | None = None
    link: str | None = None
    published_at: str | None = None


class NewsResponse(BaseModel):
    ticker: str
    items: list[NewsItem]
    ai_summary: str | None = None


class EvidenceItem(BaseModel):
    metric: str
    value: str
    benchmark: str
    metric_key: str | None = None
    benchmark_key: str | None = None
    benchmark_params: dict[str, str] = Field(default_factory=dict)


class Insight(BaseModel):
    code: str
    kind: str  # "risk" | "opportunity"
    title: str
    severity: str  # "low" | "medium" | "high"
    explanation: str
    evidence: list[EvidenceItem]


class AnalysisResponse(BaseModel):
    ticker: str
    insights: list[Insight]
    ai_narrative: str | None = None
    disclaimer: str


class CompareRow(BaseModel):
    metric: str
    label: str
    values: dict[str, float | str | None]
    best: str | None = None
    higher_is_better: bool | None = None


class CompareResponse(BaseModel):
    tickers: list[str]
    rows: list[CompareRow]
