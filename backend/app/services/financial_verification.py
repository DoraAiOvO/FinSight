"""Normalized, validation-first financial evidence and source reconciliation.

Provider payloads terminate at this boundary. Downstream API and AI callers may
consume only ``FinancialMetric`` instances produced here.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
import time
from typing import Any, Iterable

import yfinance as yf
from pydantic import ValidationError

from ..config import settings
from ..models.schemas import (
    AccountingStandard,
    CompanyEntity,
    DataSource,
    DataSourceType,
    FinancialEvidenceResponse,
    FinancialMetric,
    FinancialPeriod,
    FinancialPeriodType,
    FinancialUnit,
    Listing,
    SourceConflict,
    VerificationResult,
    VerificationStatus,
)
from . import sec_filings


DEFAULT_TOLERANCES: dict[str, dict[str, float]] = {
    "default": {"relative": 0.005, "absolute": 1e-9},
    "total_revenue": {"relative": 0.01, "absolute": 1.0},
    "net_income": {"relative": 0.01, "absolute": 1.0},
    "operating_income": {"relative": 0.01, "absolute": 1.0},
    "operating_cash_flow": {"relative": 0.01, "absolute": 1.0},
    "capital_expenditure": {"relative": 0.02, "absolute": 1.0},
    "free_cash_flow": {"relative": 0.02, "absolute": 1.0},
    "total_assets": {"relative": 0.005, "absolute": 1.0},
    "total_liabilities": {"relative": 0.005, "absolute": 1.0},
    "stockholders_equity": {"relative": 0.005, "absolute": 1.0},
    "total_debt": {"relative": 0.01, "absolute": 1.0},
    "cash_and_equivalents": {"relative": 0.01, "absolute": 1.0},
    "diluted_eps": {"relative": 0.01, "absolute": 0.01},
    "profit_margin": {"relative": 0.01, "absolute": 0.0005},
    "operating_margin": {"relative": 0.01, "absolute": 0.0005},
    "debt_to_equity": {"relative": 0.01, "absolute": 0.001},
}


METRIC_SPECS: dict[str, dict[str, Any]] = {
    "total_revenue": {
        "unit": FinancialUnit.CURRENCY,
        "concepts": {
            "us-gaap": [
                "RevenueFromContractWithCustomerExcludingAssessedTax",
                "Revenues",
                "SalesRevenueNet",
            ],
            "ifrs-full": ["Revenue"],
        },
    },
    "net_income": {
        "unit": FinancialUnit.CURRENCY,
        "concepts": {
            "us-gaap": ["NetIncomeLoss", "ProfitLoss"],
            "ifrs-full": ["ProfitLoss"],
        },
    },
    "operating_income": {
        "unit": FinancialUnit.CURRENCY,
        "concepts": {
            "us-gaap": ["OperatingIncomeLoss"],
            "ifrs-full": ["ProfitLossFromOperatingActivities"],
        },
    },
    "operating_cash_flow": {
        "unit": FinancialUnit.CURRENCY,
        "concepts": {
            "us-gaap": ["NetCashProvidedByUsedInOperatingActivities"],
            "ifrs-full": ["CashFlowsFromUsedInOperatingActivities"],
        },
    },
    "capital_expenditure": {
        "unit": FinancialUnit.CURRENCY,
        "concepts": {
            "us-gaap": [
                "PaymentsToAcquirePropertyPlantAndEquipment",
                "PaymentsForProceedsFromProductiveAssets",
            ],
            "ifrs-full": ["PurchaseOfPropertyPlantAndEquipment"],
        },
    },
    "total_assets": {
        "unit": FinancialUnit.CURRENCY,
        "instant": True,
        "concepts": {"us-gaap": ["Assets"], "ifrs-full": ["Assets"]},
    },
    "total_liabilities": {
        "unit": FinancialUnit.CURRENCY,
        "instant": True,
        "concepts": {
            "us-gaap": ["Liabilities"],
            "ifrs-full": ["Liabilities"],
        },
    },
    "stockholders_equity": {
        "unit": FinancialUnit.CURRENCY,
        "instant": True,
        "concepts": {
            "us-gaap": [
                "StockholdersEquity",
                "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
            ],
            "ifrs-full": ["Equity"],
        },
    },
    "total_debt": {
        "unit": FinancialUnit.CURRENCY,
        "instant": True,
        "concepts": {
            "us-gaap": [
                "LongTermDebtAndFinanceLeaseObligations",
                "LongTermDebtAndCapitalLeaseObligations",
                "LongTermDebt",
            ],
            "ifrs-full": ["Borrowings"],
        },
    },
    "cash_and_equivalents": {
        "unit": FinancialUnit.CURRENCY,
        "instant": True,
        "concepts": {
            "us-gaap": ["CashAndCashEquivalentsAtCarryingValue"],
            "ifrs-full": ["CashAndCashEquivalents"],
        },
    },
    "diluted_eps": {
        "unit": FinancialUnit.CURRENCY_PER_SHARE,
        "concepts": {
            "us-gaap": ["EarningsPerShareDiluted"],
            "ifrs-full": ["DilutedEarningsLossPerShare"],
        },
    },
    "shares_outstanding": {
        "unit": FinancialUnit.SHARES,
        "instant": True,
        "concepts": {
            "dei": ["EntityCommonStockSharesOutstanding"],
            "us-gaap": ["CommonStockSharesOutstanding"],
            "ifrs-full": ["NumberOfSharesOutstanding"],
        },
    },
}


YAHOO_ROWS = {
    "income": {
        "total_revenue": "TotalRevenue",
        "net_income": "NetIncome",
        "operating_income": "OperatingIncome",
        "diluted_eps": "DilutedEPS",
    },
    "balance": {
        "total_assets": "TotalAssets",
        "total_liabilities": "TotalLiabilitiesNetMinorityInterest",
        "stockholders_equity": "StockholdersEquity",
        "total_debt": "TotalDebt",
        "cash_and_equivalents": "CashCashEquivalentsAndShortTermInvestments",
        "shares_outstanding": "OrdinarySharesNumber",
    },
    "cash": {
        "operating_cash_flow": "OperatingCashFlow",
        "capital_expenditure": "CapitalExpenditure",
        "free_cash_flow": "FreeCashFlow",
    },
}


OVERVIEW_SPECS = {
    "price": FinancialUnit.CURRENCY,
    "market_cap": FinancialUnit.CURRENCY,
    "trailing_pe": FinancialUnit.MULTIPLE,
    "forward_pe": FinancialUnit.MULTIPLE,
    "price_to_sales": FinancialUnit.MULTIPLE,
    "profit_margin": FinancialUnit.RATIO,
    "operating_margin": FinancialUnit.RATIO,
    "revenue_growth": FinancialUnit.RATIO,
    "earnings_growth": FinancialUnit.RATIO,
    "debt_to_equity": FinancialUnit.PERCENT,
    "current_ratio": FinancialUnit.MULTIPLE,
    "free_cash_flow": FinancialUnit.CURRENCY,
    "total_revenue": FinancialUnit.CURRENCY,
    "free_cash_flow_margin": FinancialUnit.RATIO,
    "beta": FinancialUnit.MULTIPLE,
    "dividend_yield": FinancialUnit.RATIO,
    "fifty_two_week_low": FinancialUnit.CURRENCY,
    "fifty_two_week_high": FinancialUnit.CURRENCY,
    "analyst_target_mean": FinancialUnit.CURRENCY,
}


EXPECTED_METRICS = {
    "total_revenue",
    "net_income",
    "operating_income",
    "operating_cash_flow",
    "total_assets",
    "total_liabilities",
    "stockholders_equity",
    "free_cash_flow",
    "profit_margin",
}


_cache: dict[str, tuple[float, dict]] = {}


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join("" if part is None else str(part) for part in parts)
    return f"{prefix}_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:24]}"


def _overview_cache_key(ticker: str, overview: dict | None) -> str:
    values = []
    for key in sorted(OVERVIEW_SPECS):
        item = (overview or {}).get(key)
        value = item.get("value") if isinstance(item, dict) else item
        values.append((key, value))
    digest = hashlib.sha256(repr(values).encode("utf-8")).hexdigest()[:16]
    return f"{ticker.upper()}:{digest}"


def clear_cache() -> None:
    _cache.clear()


def _date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)


def _finite(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def metric_tolerance(metric_key: str) -> tuple[float, float]:
    configured: dict[str, Any] = {}
    try:
        raw = json.loads(settings.METRIC_TOLERANCES_JSON)
        configured = raw if isinstance(raw, dict) else {}
    except (TypeError, json.JSONDecodeError):
        configured = {}
    defaults = DEFAULT_TOLERANCES.get(metric_key, DEFAULT_TOLERANCES["default"])
    override = configured.get(metric_key, {})
    if not isinstance(override, dict):
        override = {}
    try:
        relative = float(override.get("relative", defaults["relative"]))
        absolute = float(override.get("absolute", defaults["absolute"]))
    except (TypeError, ValueError):
        relative, absolute = defaults["relative"], defaults["absolute"]
    if not math.isfinite(relative) or relative < 0:
        relative = defaults["relative"]
    if not math.isfinite(absolute) or absolute < 0:
        absolute = defaults["absolute"]
    return relative, absolute


def _period_type(record: dict, *, instant: bool) -> FinancialPeriodType | None:
    if instant:
        return FinancialPeriodType.INSTANT
    start = _date(record.get("start"))
    end = _date(record.get("end"))
    if start is None or end is None:
        return None
    days = (end - start).days + 1
    form = str(record.get("form") or "").upper()
    fp = str(record.get("fp") or "").upper()
    if form in {"10-K", "20-F", "40-F"} or fp == "FY":
        return FinancialPeriodType.ANNUAL
    if form in {"10-Q", "6-K"} and days <= 120:
        return FinancialPeriodType.QUARTER
    if form in {"10-Q", "6-K"}:
        return FinancialPeriodType.YTD
    if 300 <= days <= 400:
        return FinancialPeriodType.ANNUAL
    if 70 <= days <= 120:
        return FinancialPeriodType.QUARTER
    return None


def _fiscal_quarter(record: dict, period_type: FinancialPeriodType) -> int | None:
    if period_type == FinancialPeriodType.ANNUAL:
        return None
    fp = str(record.get("fp") or "").upper()
    if len(fp) == 2 and fp.startswith("Q") and fp[1].isdigit():
        quarter = int(fp[1])
        return quarter if 1 <= quarter <= 4 else None
    return None


def _filing_document(cik: str, accession: str, primary_document: str | None) -> str:
    cik_path = str(int(cik))
    accession_path = accession.replace("-", "")
    root = f"https://www.sec.gov/Archives/edgar/data/{cik_path}/{accession_path}"
    return f"{root}/{primary_document}" if primary_document else f"{root}/{accession}-index.html"


def _period(metric: FinancialMetric) -> FinancialPeriod:
    return FinancialPeriod(
        period_id=metric.financial_period_id,
        period_type=metric.period_type,
        period_start=metric.period_start,
        period_end=metric.period_end,
        fiscal_year=metric.fiscal_year,
        fiscal_quarter=metric.fiscal_quarter,
    )


def _append_metric(payload: dict, raw: dict) -> None:
    try:
        metric = FinancialMetric.model_validate(raw)
    except ValidationError as error:
        payload["validation_failures"].append(
            f"{raw.get('provider', 'provider')}:{raw.get('metric_key', 'unknown')}: "
            f"{error.errors()[0]['msg']}"
        )
        return
    payload["metrics"].append(metric)
    period = _period(metric)
    payload["periods"][period.period_id] = period


def normalize_sec_payloads(company_facts: dict, submissions: dict, ticker: str) -> dict:
    """Normalize already-fetched SEC Company Facts and Submissions payloads."""
    cik = str(company_facts.get("cik") or submissions.get("cik") or "").zfill(10)
    entity_id = f"sec:{cik}"
    listing_id = f"listing:{ticker.upper()}"
    company = CompanyEntity(
        entity_id=entity_id,
        legal_name=str(company_facts.get("company_name") or submissions.get("company_name") or ticker),
        cik=cik,
        country=None,
    )
    listing = Listing(
        listing_id=listing_id,
        entity_id=entity_id,
        ticker=ticker.upper(),
        exchange=None,
        currency=None,
    )
    result = {
        "company": company,
        "listings": [listing],
        "periods": {},
        "sources": {},
        "metrics": [],
        "validation_failures": [],
    }
    filing_rows = {
        str(row.get("accessionNumber")): row
        for row in submissions.get("filings", [])
        if row.get("accessionNumber")
    }
    submissions_source = DataSource(
        data_source_id=_stable_id("source", "SEC Submissions", cik),
        provider="SEC EDGAR",
        source_type=DataSourceType.SEC_SUBMISSIONS,
        source_document=str(submissions.get("source_url") or "SEC Submissions API"),
        source_url=submissions.get("source_url"),
        is_official=True,
        fetched_at=_datetime(submissions.get("fetched_at")),
    )
    result["sources"][submissions_source.data_source_id] = submissions_source
    facts_root = company_facts.get("facts") or {}
    fetched_at = _datetime(company_facts.get("fetched_at"))

    for metric_key, spec in METRIC_SPECS.items():
        for namespace, concepts in spec["concepts"].items():
            namespace_facts = facts_root.get(namespace) or {}
            standard = (
                AccountingStandard.IFRS
                if namespace == "ifrs-full"
                else AccountingStandard.US_GAAP
            )
            for concept_rank, concept in enumerate(concepts):
                concept_payload = namespace_facts.get(concept) or {}
                units = concept_payload.get("units") or {}
                for provider_unit, observations in units.items():
                    if not isinstance(observations, list):
                        continue
                    for observation in observations:
                        if str(observation.get("form") or "").upper() not in {
                            "10-K", "10-Q", "20-F", "40-F", "6-K"
                        }:
                            continue
                        value = _finite(observation.get("val"))
                        period_end = _date(observation.get("end"))
                        filing_date = _date(observation.get("filed"))
                        accession = str(observation.get("accn") or "")
                        period_type = _period_type(
                            observation, instant=bool(spec.get("instant"))
                        )
                        if value is None or period_end is None or not accession or period_type is None:
                            continue
                        fiscal_quarter = _fiscal_quarter(observation, period_type)
                        if period_type == FinancialPeriodType.QUARTER and fiscal_quarter is None:
                            result["validation_failures"].append(
                                f"SEC EDGAR:{metric_key}: quarter fact lacks fiscal quarter"
                            )
                            continue
                        try:
                            fiscal_year = int(observation.get("fy"))
                        except (TypeError, ValueError):
                            fiscal_year = period_end.year
                        source_row = filing_rows.get(accession, {})
                        document = _filing_document(
                            cik, accession, source_row.get("primaryDocument")
                        )
                        data_source_id = _stable_id("source", "SEC Company Facts", accession)
                        if data_source_id not in result["sources"]:
                            result["sources"][data_source_id] = DataSource(
                                data_source_id=data_source_id,
                                provider="SEC EDGAR",
                                source_type=DataSourceType.SEC_COMPANY_FACTS,
                                source_document=document,
                                source_url=document,
                                is_official=True,
                                fetched_at=fetched_at,
                            )
                        unit = spec["unit"]
                        currency = None
                        if unit == FinancialUnit.CURRENCY:
                            currency = provider_unit.upper() if len(provider_unit) == 3 else None
                        elif unit == FinancialUnit.CURRENCY_PER_SHARE:
                            currency = provider_unit.split("/")[0].upper()
                            if len(currency) != 3:
                                currency = None
                        if unit == FinancialUnit.CURRENCY and metric_key == "capital_expenditure":
                            value = abs(value)
                        period_start = (
                            None
                            if period_type == FinancialPeriodType.INSTANT
                            else _date(observation.get("start"))
                        )
                        period_id = _stable_id(
                            "period", period_type.value, period_start, period_end,
                            fiscal_year, fiscal_quarter,
                        )
                        metric_id = _stable_id(
                            "metric", metric_key, namespace, concept, accession,
                            period_start, period_end, value, provider_unit,
                        )
                        _append_metric(
                            result,
                            {
                                "metric_id": metric_id,
                                "entity_id": entity_id,
                                "listing_id": listing_id,
                                "financial_period_id": period_id,
                                "data_source_id": data_source_id,
                                "metric_key": metric_key,
                                "value": value,
                                "unit": unit,
                                "currency": currency,
                                "period_type": period_type,
                                "period_start": period_start,
                                "period_end": period_end,
                                "fiscal_year": fiscal_year,
                                "fiscal_quarter": fiscal_quarter,
                                "filing_date": filing_date,
                                "accounting_standard": standard,
                                "provider": "SEC EDGAR",
                                "source_document": document,
                                "source_concept": f"{namespace}:{concept}",
                                "fetched_at": fetched_at,
                                "verification_status": VerificationStatus.OFFICIAL,
                                "validation_warnings": [f"concept_priority={concept_rank}"],
                            },
                        )
    return result


def _frame_value(frame: Any, row: str, column: Any) -> float | None:
    try:
        return _finite(frame.at[row, column])
    except (AttributeError, KeyError, TypeError, ValueError):
        return None


def normalize_yahoo_statements(
    ticker: str,
    *,
    entity_id: str,
    listing_id: str,
    currency: str | None,
    fetched_at: datetime,
) -> dict:
    """Normalize Yahoo annual statement tables as secondary evidence."""
    result = {"periods": {}, "sources": {}, "metrics": [], "validation_failures": []}
    source_url = f"https://finance.yahoo.com/quote/{ticker.upper()}/financials"
    data_source = DataSource(
        data_source_id=_stable_id("source", "Yahoo statements", ticker.upper()),
        provider="Yahoo Finance",
        source_type=DataSourceType.YAHOO_FINANCE,
        source_document=source_url,
        source_url=source_url,
        is_official=False,
        fetched_at=fetched_at,
    )
    result["sources"][data_source.data_source_id] = data_source
    try:
        company = yf.Ticker(ticker)
        frames = {
            "income": company.get_income_stmt(freq="yearly"),
            "balance": company.get_balance_sheet(freq="yearly"),
            "cash": company.get_cash_flow(freq="yearly"),
        }
    except Exception as error:
        result["validation_failures"].append(
            f"Yahoo Finance: annual statements unavailable ({type(error).__name__})"
        )
        return result
    columns = sorted(
        set().union(*(set(getattr(frame, "columns", [])) for frame in frames.values())),
        reverse=True,
    )
    for column in columns:
        period_end = _date(column)
        if period_end is None:
            continue
        fiscal_year = period_end.year
        inferred_start = period_end - timedelta(days=364)
        for frame_name, rows in YAHOO_ROWS.items():
            for metric_key, row in rows.items():
                value = _frame_value(frames[frame_name], row, column)
                if value is None:
                    continue
                spec = METRIC_SPECS.get(metric_key, {})
                instant = bool(spec.get("instant"))
                period_type = FinancialPeriodType.INSTANT if instant else FinancialPeriodType.ANNUAL
                period_start = None if instant else inferred_start
                unit = spec.get("unit", FinancialUnit.CURRENCY)
                normalized_currency = currency if unit in {
                    FinancialUnit.CURRENCY, FinancialUnit.CURRENCY_PER_SHARE
                } else None
                if metric_key == "capital_expenditure":
                    value = abs(value)
                period_id = _stable_id(
                    "period", period_type.value, period_start, period_end, fiscal_year, None
                )
                _append_metric(
                    result,
                    {
                        "metric_id": _stable_id(
                            "metric", metric_key, "Yahoo", row, period_end, value
                        ),
                        "entity_id": entity_id,
                        "listing_id": listing_id,
                        "financial_period_id": period_id,
                        "data_source_id": data_source.data_source_id,
                        "metric_key": metric_key,
                        "value": value,
                        "unit": unit,
                        "currency": normalized_currency,
                        "period_type": period_type,
                        "period_start": period_start,
                        "period_end": period_end,
                        "fiscal_year": fiscal_year,
                        "fiscal_quarter": None,
                        "filing_date": None,
                        "accounting_standard": AccountingStandard.UNKNOWN,
                        "provider": "Yahoo Finance",
                        "source_document": source_url,
                        "source_concept": f"yfinance yearly {frame_name}:{row}",
                        "fetched_at": fetched_at,
                        "verification_status": VerificationStatus.SINGLE_SOURCE,
                        "validation_warnings": ["period_start inferred from yearly frequency"],
                    },
                )
    return result


def normalize_overview_metrics(
    ticker: str,
    overview: dict,
    *,
    entity_id: str,
    listing_id: str,
) -> dict:
    """Normalize current Yahoo overview observations without trusting raw fields."""
    result = {"periods": {}, "sources": {}, "metrics": [], "validation_failures": []}
    fetched_at = datetime.now(timezone.utc)
    source_url = f"https://finance.yahoo.com/quote/{ticker.upper()}"
    data_source = DataSource(
        data_source_id=_stable_id("source", "Yahoo overview", ticker.upper()),
        provider="Yahoo Finance",
        source_type=DataSourceType.YAHOO_FINANCE,
        source_document=source_url,
        source_url=source_url,
        is_official=False,
        fetched_at=fetched_at,
    )
    result["sources"][data_source.data_source_id] = data_source
    default_currency = str(overview.get("currency") or "").upper() or None
    for metric_key, unit in OVERVIEW_SPECS.items():
        point = overview.get(metric_key)
        if not isinstance(point, dict):
            continue
        value = _finite(point.get("value"))
        period_end = _date(point.get("as_of_date"))
        if value is None or period_end is None:
            continue
        point_fetched_at = _datetime(point.get("fetched_at"))
        is_market_instant = metric_key in {
            "price", "market_cap", "trailing_pe", "forward_pe", "price_to_sales",
            "beta", "fifty_two_week_low", "fifty_two_week_high", "analyst_target_mean",
        }
        period_type = FinancialPeriodType.INSTANT if is_market_instant else FinancialPeriodType.TTM
        period_start = None if is_market_instant else period_end - timedelta(days=364)
        currency = default_currency if unit in {
            FinancialUnit.CURRENCY, FinancialUnit.CURRENCY_PER_SHARE
        } else None
        status = (
            VerificationStatus.SINGLE_SOURCE
            if is_market_instant
            else VerificationStatus.PERIOD_UNCLEAR
        )
        period_id = _stable_id(
            "period", period_type.value, period_start, period_end, None, None
        )
        _append_metric(
            result,
            {
                "metric_id": _stable_id(
                    "metric", metric_key, "Yahoo overview", period_end, value
                ),
                "entity_id": entity_id,
                "listing_id": listing_id,
                "financial_period_id": period_id,
                "data_source_id": data_source.data_source_id,
                "metric_key": metric_key,
                "value": value,
                "unit": unit,
                "currency": currency,
                "period_type": period_type,
                "period_start": period_start,
                "period_end": period_end,
                "fiscal_year": None,
                "fiscal_quarter": None,
                "filing_date": None,
                "accounting_standard": AccountingStandard.UNKNOWN,
                "provider": "Yahoo Finance",
                "source_document": str(point.get("source_url") or source_url),
                "source_concept": str(point.get("source") or f"Yahoo overview:{metric_key}"),
                "fetched_at": point_fetched_at,
                "verification_status": status,
                "validation_warnings": (
                    ["provider did not identify the exact trailing period"]
                    if status == VerificationStatus.PERIOD_UNCLEAR else []
                ),
            },
        )
    return result


def _merge_normalized(target: dict, source: dict) -> None:
    target["periods"].update(source.get("periods", {}))
    target["sources"].update(source.get("sources", {}))
    target["metrics"].extend(source.get("metrics", []))
    target["validation_failures"].extend(source.get("validation_failures", []))


def _group_key(metric: FinancialMetric) -> tuple:
    return (
        metric.metric_key,
        metric.period_type,
        metric.period_end,
        metric.fiscal_year,
        metric.fiscal_quarter,
    )


def _concept_priority(metric: FinancialMetric) -> int:
    for warning in metric.validation_warnings:
        if warning.startswith("concept_priority="):
            try:
                return int(warning.split("=", 1)[1])
            except ValueError:
                pass
    return 99


def _candidate_rank(metric: FinancialMetric, sources: dict[str, DataSource]) -> tuple:
    source = sources.get(metric.data_source_id)
    official = bool(source and source.is_official) or metric.provider == "SEC EDGAR"
    calculated_from_sec = metric.provider == "FinSight" and "sec.gov" in metric.source_document
    return (
        0 if official else 1 if calculated_from_sec else 2,
        _concept_priority(metric),
        -(metric.filing_date.toordinal() if metric.filing_date else 0),
        metric.metric_id,
    )


def _matches(left: FinancialMetric, right: FinancialMetric, relative: float, absolute: float) -> bool:
    if left.unit != right.unit or left.currency != right.currency:
        return False
    difference = abs(left.value - right.value)
    scale = max(abs(left.value), abs(right.value))
    return difference <= max(absolute, relative * scale)


def _derive_metrics(
    metrics: list[FinancialMetric],
    sources: dict[str, DataSource],
) -> list[FinancialMetric]:
    selected: dict[tuple, dict[str, FinancialMetric]] = defaultdict(dict)
    for metric in sorted(metrics, key=lambda item: _candidate_rank(item, sources)):
        signature = _group_key(metric)[1:]
        selected[signature].setdefault(metric.metric_key, metric)
    derived: list[FinancialMetric] = []
    formulas = {
        "profit_margin": ("net_income", "total_revenue", "net_income / total_revenue", FinancialUnit.RATIO),
        "operating_margin": ("operating_income", "total_revenue", "operating_income / total_revenue", FinancialUnit.RATIO),
        "free_cash_flow": ("operating_cash_flow", "capital_expenditure", "operating_cash_flow - capital_expenditure", FinancialUnit.CURRENCY),
        "debt_to_equity": ("total_debt", "stockholders_equity", "total_debt / stockholders_equity", FinancialUnit.RATIO),
    }
    for signature, available in selected.items():
        for metric_key, (numerator_key, denominator_key, formula, unit) in formulas.items():
            numerator = available.get(numerator_key)
            denominator = available.get(denominator_key)
            if numerator is None or denominator is None or denominator.value == 0:
                continue
            if numerator.unit != denominator.unit or numerator.currency != denominator.currency:
                continue
            value = (
                numerator.value - denominator.value
                if metric_key == "free_cash_flow"
                else numerator.value / denominator.value
            )
            if not math.isfinite(value):
                continue
            base = numerator
            currency = numerator.currency if unit == FinancialUnit.CURRENCY else None
            source_document = " | ".join(dict.fromkeys([
                numerator.source_document, denominator.source_document
            ]))[:2000]
            data_source_id = _stable_id(
                "source", "FinSight calculation", base.financial_period_id, formula
            )
            if data_source_id not in sources:
                sources[data_source_id] = DataSource(
                    data_source_id=data_source_id,
                    provider="FinSight",
                    source_type=DataSourceType.CALCULATION,
                    source_document=source_document,
                    source_url=None,
                    is_official=False,
                    fetched_at=max(numerator.fetched_at, denominator.fetched_at),
                )
            raw = {
                **base.model_dump(),
                "metric_id": _stable_id(
                    "metric", metric_key, numerator.metric_id, denominator.metric_id, formula
                ),
                "data_source_id": data_source_id,
                "metric_key": metric_key,
                "value": value,
                "unit": unit,
                "currency": currency,
                "filing_date": max(
                    (item for item in [numerator.filing_date, denominator.filing_date] if item),
                    default=None,
                ),
                "provider": "FinSight",
                "source_document": source_document,
                "source_concept": f"calculation:{numerator.metric_id},{denominator.metric_id}",
                "fetched_at": max(numerator.fetched_at, denominator.fetched_at),
                "verification_status": VerificationStatus.CALCULATED,
                "calculation_formula": formula,
                "validation_warnings": [],
            }
            try:
                derived.append(FinancialMetric.model_validate(raw))
            except ValidationError:
                continue
    return derived


def reconcile_metrics(
    metrics: Iterable[FinancialMetric],
    sources: Iterable[DataSource],
    *,
    now: datetime | None = None,
) -> tuple[list[FinancialMetric], list[VerificationResult], list[SourceConflict]]:
    """Compare like periods, preserve candidates, and prefer official filings."""
    now = now or datetime.now(timezone.utc)
    source_map = {source.data_source_id: source for source in sources}
    candidates = list(metrics)
    candidates.extend(_derive_metrics(candidates, source_map))
    groups: dict[tuple, list[FinancialMetric]] = defaultdict(list)
    for metric in candidates:
        groups[_group_key(metric)].append(metric)
    updated: dict[str, FinancialMetric] = {item.metric_id: item for item in candidates}
    results: list[VerificationResult] = []
    conflicts: list[SourceConflict] = []

    for group_key, group in sorted(groups.items(), key=lambda item: str(item[0])):
        metric_key = group_key[0]
        relative, absolute = metric_tolerance(metric_key)
        ranked = sorted(group, key=lambda item: _candidate_rank(item, source_map))
        selected = ranked[0]
        providers = {item.provider for item in ranked}
        disagreements = [
            item for item in ranked[1:]
            if not _matches(selected, item, relative, absolute)
        ]
        comparable = [
            item for item in ranked[1:]
            if item.provider != selected.provider
            and item.period_type == selected.period_type
            and item.period_end == selected.period_end
        ]
        source = source_map.get(selected.data_source_id)
        if disagreements:
            status = VerificationStatus.CONFLICTING
            for item in ranked:
                updated[item.metric_id] = item.model_copy(
                    update={"verification_status": VerificationStatus.CONFLICTING}
                )
            challenger = max(disagreements, key=lambda item: abs(item.value - selected.value))
            difference = abs(selected.value - challenger.value)
            scale = max(abs(selected.value), abs(challenger.value), 1e-12)
            official_primary = bool(source_map.get(selected.data_source_id) and source_map[selected.data_source_id].is_official)
            official_primary = official_primary or (
                selected.provider == "FinSight" and "sec.gov" in selected.source_document
            )
            conflicts.append(
                SourceConflict(
                    conflict_id=_stable_id(
                        "conflict", metric_key, selected.metric_id, challenger.metric_id
                    ),
                    metric_key=metric_key,
                    financial_period_id=selected.financial_period_id,
                    metric_ids=[item.metric_id for item in ranked],
                    providers=[item.provider for item in ranked],
                    values=[item.value for item in ranked],
                    relative_difference=difference / scale,
                    absolute_difference=difference,
                    relative_tolerance=relative,
                    absolute_tolerance=absolute,
                    resolution=(
                        "UNRESOLVED_OFFICIAL_PRIMARY"
                        if official_primary else "UNRESOLVED_NO_PRIMARY"
                    ),
                )
            )
            explanation = "Sources disagree beyond the configured tolerance; all values are preserved."
            if official_primary:
                explanation += " The official filing remains the primary display candidate."
        elif comparable:
            status = VerificationStatus.CROSS_VERIFIED
            updated[selected.metric_id] = selected.model_copy(
                update={"verification_status": status}
            )
            explanation = "Independent providers match within the configured tolerance."
        elif selected.verification_status == VerificationStatus.PERIOD_UNCLEAR:
            status = VerificationStatus.PERIOD_UNCLEAR
            explanation = "The provider did not identify an exact reporting period."
        elif selected.verification_status == VerificationStatus.CALCULATED:
            status = VerificationStatus.CALCULATED
            explanation = "FinSight calculated this value from validated input metrics."
        elif source and source.is_official:
            status = VerificationStatus.OFFICIAL
            updated[selected.metric_id] = selected.model_copy(
                update={"verification_status": status}
            )
            explanation = "Selected from an official SEC filing."
        else:
            status = VerificationStatus.SINGLE_SOURCE
            explanation = "Only one normalized provider supplied this period."
        results.append(
            VerificationResult(
                verification_result_id=_stable_id(
                    "verification", metric_key, selected.financial_period_id
                ),
                metric_key=metric_key,
                financial_period_id=selected.financial_period_id,
                selected_metric_id=selected.metric_id,
                candidate_metric_ids=[item.metric_id for item in ranked],
                verification_status=status,
                relative_tolerance=relative,
                absolute_tolerance=absolute,
                compared_provider_count=len(providers),
                explanation=explanation,
            )
        )

    latest_by_key: dict[str, VerificationResult] = {}
    for result in results:
        metric = updated.get(result.selected_metric_id or "")
        if metric is None:
            continue
        current = latest_by_key.get(result.metric_key)
        current_metric = updated.get(current.selected_metric_id or "") if current else None
        if current_metric is None or metric.period_end > current_metric.period_end:
            latest_by_key[result.metric_key] = result
    for result in latest_by_key.values():
        metric = updated.get(result.selected_metric_id or "")
        if (
            metric is not None
            and (now.date() - metric.period_end).days > settings.FINANCIAL_STALE_DAYS
            and result.verification_status
            not in {VerificationStatus.CONFLICTING, VerificationStatus.PERIOD_UNCLEAR}
        ):
            result.verification_status = VerificationStatus.STALE
            result.explanation = "The newest available value is older than the configured freshness window."
            updated[metric.metric_id] = metric.model_copy(
                update={"verification_status": VerificationStatus.STALE}
            )

    return list(updated.values()), results, conflicts


def build_financial_evidence(
    company: CompanyEntity,
    listings: list[Listing],
    periods: Iterable[FinancialPeriod],
    sources: Iterable[DataSource],
    metrics: Iterable[FinancialMetric],
    *,
    validation_failures: list[str] | None = None,
    now: datetime | None = None,
) -> FinancialEvidenceResponse:
    source_list = list(sources)
    period_list = list(periods)
    normalized_metrics, results, conflicts = reconcile_metrics(
        metrics, source_list, now=now
    )
    source_map = {source.data_source_id: source for source in source_list}
    for metric in normalized_metrics:
        if metric.data_source_id not in source_map:
            source_map[metric.data_source_id] = DataSource(
                data_source_id=metric.data_source_id,
                provider=metric.provider,
                source_type=DataSourceType.CALCULATION,
                source_document=metric.source_document,
                source_url=None,
                is_official=False,
                fetched_at=metric.fetched_at,
            )
    period_map = {period.period_id: period for period in period_list}
    for metric in normalized_metrics:
        period_map.setdefault(metric.financial_period_id, _period(metric))
    selected_keys = {
        result.metric_key for result in results if result.selected_metric_id is not None
    }
    return FinancialEvidenceResponse(
        company=company,
        listings=listings,
        periods=sorted(period_map.values(), key=lambda item: (item.period_end, item.period_type.value), reverse=True),
        sources=list(source_map.values()),
        metrics=normalized_metrics,
        verification_results=results,
        conflicts=conflicts,
        missing_metric_keys=sorted(EXPECTED_METRICS - selected_keys),
        validation_failures=validation_failures or [],
        generated_at=now or datetime.now(timezone.utc),
    )


def get_financial_evidence(ticker: str, overview: dict | None = None) -> FinancialEvidenceResponse:
    """Build verified financial evidence, degrading to normalized Yahoo data."""
    ticker = ticker.upper()
    cache_key = _overview_cache_key(ticker, overview)
    cached = _cache.get(cache_key)
    if cached and time.time() - cached[0] < settings.CACHE_TTL_SECONDS:
        return FinancialEvidenceResponse.model_validate(cached[1])

    now = datetime.now(timezone.utc)
    sec_normalized = None
    failures: list[str] = []
    try:
        submissions = sec_filings.get_submissions_metadata(ticker)
        company_facts = sec_filings.get_company_facts(ticker)
        sec_normalized = normalize_sec_payloads(company_facts, submissions, ticker)
    except sec_filings.SecError as error:
        failures.append(f"SEC EDGAR: {error}")

    if sec_normalized:
        company = sec_normalized["company"]
        listings = sec_normalized["listings"]
        aggregate = sec_normalized
    else:
        name = str((overview or {}).get("name") or ticker)
        entity_id = f"symbol:{ticker}"
        company = CompanyEntity(entity_id=entity_id, legal_name=name, cik=None, country=None)
        listings = [
            Listing(
                listing_id=f"listing:{ticker}",
                entity_id=entity_id,
                ticker=ticker,
                exchange=(overview or {}).get("exchange"),
                currency=str((overview or {}).get("currency") or "").upper() or None,
            )
        ]
        aggregate = {
            "periods": {}, "sources": {}, "metrics": [], "validation_failures": []
        }
    listing = listings[0]
    if overview:
        listing = listing.model_copy(
            update={
                "exchange": overview.get("exchange") or listing.exchange,
                "currency": str(overview.get("currency") or listing.currency or "").upper() or None,
            }
        )
        listings[0] = listing

    yahoo_statements = normalize_yahoo_statements(
        ticker,
        entity_id=company.entity_id,
        listing_id=listing.listing_id,
        currency=listing.currency,
        fetched_at=now,
    )
    _merge_normalized(aggregate, yahoo_statements)
    if overview:
        _merge_normalized(
            aggregate,
            normalize_overview_metrics(
                ticker, overview, entity_id=company.entity_id, listing_id=listing.listing_id
            ),
        )
    failures.extend(aggregate.get("validation_failures", []))
    response = build_financial_evidence(
        company,
        listings,
        aggregate["periods"].values(),
        aggregate["sources"].values(),
        aggregate["metrics"],
        validation_failures=failures,
        now=now,
    )
    _cache[cache_key] = (time.time(), response.model_dump(mode="python"))
    return response


AI_ALLOWED_STATUSES = {
    VerificationStatus.OFFICIAL,
    VerificationStatus.CROSS_VERIFIED,
    VerificationStatus.SINGLE_SOURCE,
    VerificationStatus.CALCULATED,
    VerificationStatus.STALE,
}


def normalized_ai_evidence(evidence: FinancialEvidenceResponse) -> list[dict]:
    """Return the only financial evidence shape authorized for AI prompts."""
    selected = latest_selected_metrics(evidence)
    result_by_metric_id = {
        result.selected_metric_id: result
        for result in evidence.verification_results
        if result.selected_metric_id
    }
    rows = []
    for metric in selected.values():
        result = result_by_metric_id.get(metric.metric_id)
        if result is None:
            continue
        if result.verification_status not in AI_ALLOWED_STATUSES:
            continue
        rows.append(
            {
                "metric_key": metric.metric_key,
                "value": metric.value,
                "unit": metric.unit.value,
                "currency": metric.currency,
                "period_type": metric.period_type.value,
                "period_start": metric.period_start.isoformat() if metric.period_start else None,
                "period_end": metric.period_end.isoformat(),
                "fiscal_year": metric.fiscal_year,
                "fiscal_quarter": metric.fiscal_quarter,
                "filing_date": metric.filing_date.isoformat() if metric.filing_date else None,
                "accounting_standard": metric.accounting_standard.value,
                "provider": metric.provider,
                "source_document": metric.source_document,
                "source_concept": metric.source_concept,
                "fetched_at": metric.fetched_at.isoformat(),
                "verification_status": result.verification_status.value,
                "calculation_formula": metric.calculation_formula,
            }
        )
    return rows


def latest_selected_metrics(evidence: FinancialEvidenceResponse) -> dict[str, FinancialMetric]:
    metric_map = {metric.metric_id: metric for metric in evidence.metrics}
    selected: dict[str, FinancialMetric] = {}
    for result in evidence.verification_results:
        if result.verification_status not in AI_ALLOWED_STATUSES:
            continue
        metric = metric_map.get(result.selected_metric_id or "")
        if metric is None:
            continue
        current = selected.get(metric.metric_key)
        if current is None or metric.period_end > current.period_end:
            selected[metric.metric_key] = metric
    return selected


def apply_verified_overview(
    overview: dict,
    evidence: FinancialEvidenceResponse,
) -> dict:
    """Overlay normalized selected metrics onto the legacy overview contract."""
    normalized = dict(overview)
    selected = latest_selected_metrics(evidence)
    reported_keys = {
        "total_revenue",
        "free_cash_flow",
        "profit_margin",
        "operating_margin",
        "debt_to_equity",
    }
    for key in reported_keys - selected.keys():
        # A conflicted or period-unclear provider value must not sneak around the
        # verification result through the older overview field.
        normalized[key] = None
    for key, metric in selected.items():
        if key not in OVERVIEW_SPECS:
            continue
        value = metric.value
        if metric.unit in {FinancialUnit.CURRENCY, FinancialUnit.CURRENCY_PER_SHARE}:
            unit = metric.currency
        elif metric.unit == FinancialUnit.MULTIPLE:
            unit = "multiple"
        else:
            unit = metric.unit.value
        if key == "debt_to_equity" and metric.unit == FinancialUnit.RATIO:
            value *= 100
            unit = "percent"
        normalized[key] = {
            "value": value,
            "unit": unit,
            "display_value": None,
            "provider": metric.provider,
            "source": metric.source_concept,
            "as_of_date": metric.period_end,
            "fetched_at": metric.fetched_at,
            "freshness_status": (
                "stale"
                if metric.verification_status == VerificationStatus.STALE
                else "historical"
                if metric.period_type != FinancialPeriodType.INSTANT
                else "fresh"
            ),
            "verification_status": metric.verification_status.value,
            "source_url": metric.source_document,
        }
    return normalized
