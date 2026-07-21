"""Persistent watchlists, saved research snapshots, and deterministic change tracking."""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from numbers import Real
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db.models import (
    ResearchSession,
    Thesis,
    ThesisAssumption,
    User,
    Watchlist,
    WatchlistItem,
)
from ..models.schemas import (
    ChangeSummary,
    FilingChange,
    MetricChange,
    NewsChange,
    ResearchSessionCreate,
    ResearchSessionResponse,
    ResearchSessionSummary,
    ResearchSnapshot,
    SignalChange,
    ThesisAssumptionChange,
    ThesisAssumptionSnapshot,
    WatchlistCreate,
    WatchlistItemCreate,
    WatchlistItemResponse,
    WatchlistResponse,
    WhatChangedResponse,
)
from . import evidence_auditor
from .tickers import normalize_ticker


class WorkspaceError(Exception):
    """Base error for customer workspace operations."""


class WorkspaceNotFoundError(WorkspaceError):
    pass


class WorkspaceConflictError(WorkspaceError):
    pass


class WorkspaceValidationError(WorkspaceError):
    pass


METRIC_LABELS = {
    "price": "Share price",
    "market_cap": "Market capitalization",
    "trailing_pe": "Trailing P/E",
    "forward_pe": "Forward P/E",
    "price_to_sales": "Price / Sales",
    "profit_margin": "Net margin",
    "operating_margin": "Operating margin",
    "revenue_growth": "Revenue growth",
    "earnings_growth": "Earnings growth",
    "debt_to_equity": "Debt / Equity",
    "current_ratio": "Current ratio",
    "free_cash_flow": "Free cash flow",
    "total_revenue": "Total revenue",
    "free_cash_flow_margin": "Free cash flow margin",
    "beta": "Beta",
    "dividend_yield": "Dividend yield",
    "fifty_two_week_low": "52-week low",
    "fifty_two_week_high": "52-week high",
    "analyst_target_mean": "Analyst target mean",
}

# Only metrics with a broadly defensible direction are called improved or
# worsened. Price, market cap, valuation multiples, beta, dividend yield, and
# analyst targets are reported as changed without implying investment merit.
METRIC_BENEFIT_DIRECTION = {
    "profit_margin": 1,
    "operating_margin": 1,
    "revenue_growth": 1,
    "earnings_growth": 1,
    "debt_to_equity": -1,
    "current_ratio": 1,
    "free_cash_flow": 1,
    "total_revenue": 1,
    "free_cash_flow_margin": 1,
}

SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3}
ASSUMPTION_STATUS_RANK = {
    "invalidated": 0,
    "failed": 0,
    "challenged": 0,
    "unreviewed": 1,
    "unknown": 1,
    "monitoring": 2,
    "supported": 3,
    "met": 3,
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_user(session: Session, customer_id: UUID) -> User:
    user = session.get(User, customer_id)
    if user is None:
        raise WorkspaceNotFoundError("Customer profile not found")
    return user


def _load_watchlist(
    session: Session, customer_id: UUID, watchlist_id: UUID
) -> Watchlist:
    watchlist = session.scalar(
        select(Watchlist)
        .options(selectinload(Watchlist.items))
        .where(
            Watchlist.id == watchlist_id,
            Watchlist.user_id == customer_id,
        )
    )
    if watchlist is None:
        raise WorkspaceNotFoundError("Watchlist not found")
    return watchlist


def serialize_watchlist(watchlist: Watchlist) -> WatchlistResponse:
    items = sorted(watchlist.items, key=lambda item: item.added_at)
    return WatchlistResponse(
        id=watchlist.id,
        name=watchlist.name,
        description=watchlist.description,
        is_default=watchlist.is_default,
        items=[
            WatchlistItemResponse(
                id=item.id,
                ticker=item.ticker,
                notes=item.notes,
                added_at=item.added_at,
            )
            for item in items
        ],
        created_at=watchlist.created_at,
        updated_at=watchlist.updated_at,
    )


def list_watchlists(session: Session, customer_id: UUID) -> list[WatchlistResponse]:
    _require_user(session, customer_id)
    watchlists = session.scalars(
        select(Watchlist)
        .options(selectinload(Watchlist.items))
        .where(Watchlist.user_id == customer_id)
        .order_by(Watchlist.is_default.desc(), Watchlist.created_at, Watchlist.name)
    ).all()
    return [serialize_watchlist(watchlist) for watchlist in watchlists]


def create_watchlist(
    session: Session, customer_id: UUID, request: WatchlistCreate
) -> WatchlistResponse:
    _require_user(session, customer_id)
    existing = session.scalars(
        select(Watchlist).where(Watchlist.user_id == customer_id)
    ).all()
    if any(item.name.casefold() == request.name.casefold() for item in existing):
        raise WorkspaceConflictError("A watchlist with this name already exists")

    make_default = request.is_default or not existing
    if make_default:
        for watchlist in existing:
            watchlist.is_default = False
    watchlist = Watchlist(
        user_id=customer_id,
        name=request.name,
        description=request.description,
        is_default=make_default,
    )
    session.add(watchlist)
    session.commit()
    return serialize_watchlist(_load_watchlist(session, customer_id, watchlist.id))


def delete_watchlist(session: Session, customer_id: UUID, watchlist_id: UUID) -> None:
    watchlist = _load_watchlist(session, customer_id, watchlist_id)
    was_default = watchlist.is_default
    session.delete(watchlist)
    session.flush()
    if was_default:
        replacement = session.scalar(
            select(Watchlist)
            .where(Watchlist.user_id == customer_id)
            .order_by(Watchlist.created_at)
        )
        if replacement is not None:
            replacement.is_default = True
    session.commit()


def add_watchlist_item(
    session: Session,
    customer_id: UUID,
    watchlist_id: UUID,
    request: WatchlistItemCreate,
) -> WatchlistResponse:
    watchlist = _load_watchlist(session, customer_id, watchlist_id)
    try:
        ticker = normalize_ticker(request.ticker).upper()
    except ValueError as error:
        raise WorkspaceValidationError(str(error)) from error
    if any(item.ticker == ticker for item in watchlist.items):
        raise WorkspaceConflictError(f"{ticker} is already in this watchlist")
    watchlist.items.append(WatchlistItem(ticker=ticker, notes=request.notes))
    session.commit()
    return serialize_watchlist(_load_watchlist(session, customer_id, watchlist_id))


def remove_watchlist_item(
    session: Session, customer_id: UUID, watchlist_id: UUID, ticker: str
) -> WatchlistResponse:
    watchlist = _load_watchlist(session, customer_id, watchlist_id)
    try:
        normalized = normalize_ticker(ticker).upper()
    except ValueError as error:
        raise WorkspaceValidationError(str(error)) from error
    item = next((item for item in watchlist.items if item.ticker == normalized), None)
    if item is None:
        raise WorkspaceNotFoundError(f"{normalized} is not in this watchlist")
    watchlist.items.remove(item)
    session.commit()
    return serialize_watchlist(_load_watchlist(session, customer_id, watchlist_id))


def _session_summary(research: ResearchSession) -> ResearchSessionSummary:
    return ResearchSessionSummary(
        id=research.id,
        ticker=research.ticker,
        title=research.title,
        status=research.status,
        language=research.language,
        created_at=research.created_at,
        completed_at=research.completed_at,
    )


def _snapshot_from_session(research: ResearchSession) -> ResearchSnapshot:
    if not research.result_payload:
        raise WorkspaceValidationError("Saved research session has no snapshot")
    try:
        return ResearchSnapshot.model_validate(research.result_payload)
    except ValueError as error:
        raise WorkspaceValidationError("Saved research snapshot is invalid") from error


def serialize_research_session(research: ResearchSession) -> ResearchSessionResponse:
    return ResearchSessionResponse(
        **_session_summary(research).model_dump(),
        snapshot=_snapshot_from_session(research),
    )


def _current_assumptions(
    session: Session, customer_id: UUID, ticker: str
) -> list[ThesisAssumptionSnapshot]:
    assumptions = session.scalars(
        select(ThesisAssumption)
        .join(Thesis, Thesis.id == ThesisAssumption.thesis_id)
        .where(
            Thesis.user_id == customer_id,
            Thesis.ticker == ticker,
            Thesis.status == "active",
        )
        .order_by(Thesis.updated_at.desc(), ThesisAssumption.position)
    ).all()
    return [
        ThesisAssumptionSnapshot(
            assumption_id=assumption.id,
            description=assumption.description,
            current_status=assumption.current_status,
            condition_type=assumption.condition_type,
            metric_key=assumption.metric_key,
            operator=assumption.operator,
            target_value=assumption.target_value,
            event_condition=assumption.event_condition,
        )
        for assumption in assumptions
    ]


def _validated_snapshot(
    session: Session, customer_id: UUID, snapshot: ResearchSnapshot
) -> ResearchSnapshot:
    ticker = normalize_ticker(snapshot.overview.ticker).upper()
    for section_name in ("analysis", "news", "filings"):
        section = getattr(snapshot, section_name)
        if section is not None and normalize_ticker(section.ticker).upper() != ticker:
            raise WorkspaceValidationError(
                f"Snapshot {section_name} ticker does not match overview ticker"
            )
    assumptions = _current_assumptions(session, customer_id, ticker)
    if not assumptions:
        assumptions = snapshot.thesis_assumptions
    validated = snapshot.model_copy(
        update={
            "overview": snapshot.overview.model_copy(update={"ticker": ticker}),
            "thesis_assumptions": assumptions,
        }
    )
    # Browser payloads are untrusted. Re-run the same deterministic audit before
    # either saving a report or using it as a change-tracking baseline.
    return evidence_auditor.audit_snapshot(validated)


def create_research_session(
    session: Session, customer_id: UUID, request: ResearchSessionCreate
) -> ResearchSessionResponse:
    _require_user(session, customer_id)
    try:
        snapshot = _validated_snapshot(session, customer_id, request.snapshot)
    except ValueError as error:
        raise WorkspaceValidationError(str(error)) from error
    ticker = snapshot.overview.ticker
    completed_at = _utc_now()
    research = ResearchSession(
        user_id=customer_id,
        ticker=ticker,
        title=request.title or f"{ticker} research",
        status="completed",
        language=request.language.value,
        request_payload={
            "source": "saved_research",
            "captured_at": snapshot.captured_at.isoformat(),
        },
        result_payload=snapshot.model_dump(mode="json"),
        completed_at=completed_at,
    )
    session.add(research)
    session.commit()
    session.refresh(research)
    return serialize_research_session(research)


def list_research_sessions(
    session: Session,
    customer_id: UUID,
    ticker: str | None = None,
    limit: int = 20,
) -> list[ResearchSessionSummary]:
    _require_user(session, customer_id)
    query = select(ResearchSession).where(
        ResearchSession.user_id == customer_id,
        ResearchSession.status == "completed",
    )
    if ticker:
        try:
            query = query.where(
                ResearchSession.ticker == normalize_ticker(ticker).upper()
            )
        except ValueError as error:
            raise WorkspaceValidationError(str(error)) from error
    research_sessions = session.scalars(
        query.order_by(ResearchSession.completed_at.desc(), ResearchSession.created_at.desc()).limit(
            limit
        )
    ).all()
    return [_session_summary(research) for research in research_sessions]


def get_research_session(
    session: Session, customer_id: UUID, research_session_id: UUID
) -> ResearchSession:
    research = session.scalar(
        select(ResearchSession).where(
            ResearchSession.id == research_session_id,
            ResearchSession.user_id == customer_id,
        )
    )
    if research is None:
        raise WorkspaceNotFoundError("Research session not found")
    return research


def delete_research_session(
    session: Session, customer_id: UUID, research_session_id: UUID
) -> None:
    research = get_research_session(session, customer_id, research_session_id)
    session.delete(research)
    session.commit()


def _number(point) -> float | None:
    if point is None or isinstance(point.value, bool) or not isinstance(point.value, Real):
        return None
    value = float(point.value)
    return value if math.isfinite(value) else None


def _metric_changes(
    previous: ResearchSnapshot, current: ResearchSnapshot
) -> list[MetricChange]:
    changes = []
    for metric_key, label in METRIC_LABELS.items():
        old_point = getattr(previous.overview, metric_key)
        new_point = getattr(current.overview, metric_key)
        old_value = _number(old_point)
        new_value = _number(new_point)
        relative_change = None
        if old_point is None and new_point is None:
            continue
        if old_point is None:
            direction = "new"
        elif new_point is None:
            direction = "removed"
        elif old_value is not None and new_value is not None:
            if math.isclose(old_value, new_value, rel_tol=0.01, abs_tol=1e-12):
                direction = "unchanged"
            else:
                delta = new_value - old_value
                if old_value != 0:
                    relative_change = delta / abs(old_value)
                benefit = METRIC_BENEFIT_DIRECTION.get(metric_key)
                direction = (
                    "improved"
                    if benefit is not None and delta * benefit > 0
                    else "worsened"
                    if benefit is not None
                    else "changed"
                )
        else:
            direction = (
                "unchanged" if old_point.value == new_point.value else "changed"
            )
        changes.append(
            MetricChange(
                metric_key=metric_key,
                label=label,
                direction=direction,
                previous=old_point,
                current=new_point,
                relative_change=relative_change,
            )
        )
    return changes


def _normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().casefold())


def _news_key(item) -> str:
    if item.link:
        return f"url:{item.link.strip().casefold()}"
    return f"title:{_normalized_text(item.title.claim)}"


def _news_changes(previous: ResearchSnapshot, current: ResearchSnapshot) -> list[NewsChange]:
    previous_items = {
        _news_key(item): item for item in (previous.news.items if previous.news else [])
    }
    current_items = {
        _news_key(item): item for item in (current.news.items if current.news else [])
    }
    return [
        NewsChange(change_key=key, direction="new", item=item)
        for key, item in current_items.items()
        if key not in previous_items
    ]


def _filing_changes(
    previous: ResearchSnapshot, current: ResearchSnapshot
) -> list[FilingChange]:
    previous_ids = {
        filing.accession_number
        for filing in (previous.filings.filings if previous.filings else [])
    }
    return [
        FilingChange(accession_number=filing.accession_number, filing=filing)
        for filing in (current.filings.filings if current.filings else [])
        if filing.accession_number not in previous_ids
    ]


def _signal_changes(
    previous: ResearchSnapshot, current: ResearchSnapshot, kind: str
) -> list[SignalChange]:
    # A partial current report cannot prove that an earlier signal resolved.
    # Suppress this category until analysis evidence is available again.
    if current.analysis is None:
        return []
    previous_items = {
        item.code: item
        for item in (previous.analysis.insights if previous.analysis else [])
        if item.kind == kind
    }
    current_items = {
        item.code: item
        for item in (current.analysis.insights if current.analysis else [])
        if item.kind == kind
    }
    changes = []
    for code in sorted(previous_items.keys() | current_items.keys()):
        old_item = previous_items.get(code)
        new_item = current_items.get(code)
        if old_item is None:
            direction = "new"
        elif new_item is None:
            direction = "resolved" if kind == "risk" else "worsened"
        elif old_item.severity == new_item.severity:
            direction = "unchanged"
        else:
            old_rank = SEVERITY_RANK.get(old_item.severity, 0)
            new_rank = SEVERITY_RANK.get(new_item.severity, 0)
            if old_rank == new_rank:
                direction = "changed"
            elif kind == "risk":
                direction = "worsened" if new_rank > old_rank else "improved"
            else:
                direction = "improved" if new_rank > old_rank else "worsened"
        changes.append(
            SignalChange(
                code=code,
                kind=kind,
                direction=direction,
                title=(new_item or old_item).title,
                previous_severity=old_item.severity if old_item else None,
                current_severity=new_item.severity if new_item else None,
            )
        )
    return changes


def _assumption_key(assumption: ThesisAssumptionSnapshot) -> str:
    if assumption.assumption_id:
        return f"id:{assumption.assumption_id}"
    return f"description:{_normalized_text(assumption.description)}"


def _assumption_changes(
    previous: ResearchSnapshot, current: ResearchSnapshot
) -> list[ThesisAssumptionChange]:
    previous_items = {
        _assumption_key(assumption): assumption
        for assumption in previous.thesis_assumptions
    }
    current_items = {
        _assumption_key(assumption): assumption
        for assumption in current.thesis_assumptions
    }
    changes = []
    for key in sorted(previous_items.keys() | current_items.keys()):
        old_item = previous_items.get(key)
        new_item = current_items.get(key)
        if old_item is None:
            direction = "new"
        elif new_item is None:
            direction = "removed"
        elif old_item.current_status == new_item.current_status:
            old_values = old_item.model_dump(exclude={"assumption_id"})
            new_values = new_item.model_dump(exclude={"assumption_id"})
            direction = "unchanged" if old_values == new_values else "changed"
        else:
            old_rank = ASSUMPTION_STATUS_RANK.get(old_item.current_status)
            new_rank = ASSUMPTION_STATUS_RANK.get(new_item.current_status)
            if old_rank is None or new_rank is None or old_rank == new_rank:
                direction = "changed"
            else:
                direction = "improved" if new_rank > old_rank else "worsened"
        changes.append(
            ThesisAssumptionChange(
                change_key=key,
                description=(new_item or old_item).description,
                direction=direction,
                previous_status=old_item.current_status if old_item else None,
                current_status=new_item.current_status if new_item else None,
            )
        )
    return changes


def _summary(*groups) -> ChangeSummary:
    counts = {
        "new": 0,
        "improved": 0,
        "worsened": 0,
        "changed": 0,
        "resolved": 0,
        "unchanged": 0,
    }
    for group in groups:
        for item in group:
            direction = item.direction
            if direction == "removed":
                counts["changed"] += 1
            elif direction in counts:
                counts[direction] += 1
    return ChangeSummary(**counts)


def what_changed(
    session: Session,
    customer_id: UUID,
    ticker: str,
    current_snapshot: ResearchSnapshot,
    baseline_session_id: UUID | None = None,
) -> WhatChangedResponse:
    _require_user(session, customer_id)
    try:
        normalized_ticker = normalize_ticker(ticker).upper()
        current = _validated_snapshot(session, customer_id, current_snapshot)
    except ValueError as error:
        raise WorkspaceValidationError(str(error)) from error
    if current.overview.ticker != normalized_ticker:
        raise WorkspaceValidationError("Snapshot ticker does not match request ticker")

    if baseline_session_id:
        baseline = get_research_session(session, customer_id, baseline_session_id)
        if baseline.ticker != normalized_ticker:
            raise WorkspaceValidationError("Baseline session ticker does not match")
    else:
        baseline = session.scalar(
            select(ResearchSession)
            .where(
                ResearchSession.user_id == customer_id,
                ResearchSession.ticker == normalized_ticker,
                ResearchSession.status == "completed",
            )
            .order_by(
                ResearchSession.completed_at.desc(), ResearchSession.created_at.desc()
            )
        )

    if baseline is None:
        return WhatChangedResponse(
            ticker=normalized_ticker,
            compared_at=_utc_now(),
            has_baseline=False,
        )

    previous = _snapshot_from_session(baseline)
    financial_metrics = _metric_changes(previous, current)
    news = _news_changes(previous, current)
    filings = _filing_changes(previous, current)
    risk_signals = _signal_changes(previous, current, "risk")
    opportunity_signals = _signal_changes(previous, current, "opportunity")
    thesis_assumptions = _assumption_changes(previous, current)
    return WhatChangedResponse(
        ticker=normalized_ticker,
        compared_at=_utc_now(),
        has_baseline=True,
        baseline_session=_session_summary(baseline),
        summary=_summary(
            financial_metrics,
            news,
            filings,
            risk_signals,
            opportunity_signals,
            thesis_assumptions,
        ),
        financial_metrics=financial_metrics,
        news=news,
        filings=filings,
        risk_signals=risk_signals,
        opportunity_signals=opportunity_signals,
        thesis_assumptions=thesis_assumptions,
    )
