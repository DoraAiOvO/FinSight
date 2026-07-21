"""Persistent, user-authored research theses and measurable assumptions."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db.models import (
    ResearchSession,
    Thesis,
    ThesisAssumption,
    ThesisAssumptionHistory,
    User,
)
from ..models.schemas import (
    AssumptionConditionType,
    ThesisAssumptionCreate,
    ThesisAssumptionHistoryResponse,
    ThesisAssumptionResponse,
    ThesisAssumptionUpdate,
    ThesisCreate,
    ThesisResponse,
    ThesisStatus,
    ThesisUpdate,
)
from .tickers import normalize_ticker


class ThesisLedgerError(Exception):
    """Base error for thesis-ledger operations."""


class ThesisLedgerNotFoundError(ThesisLedgerError):
    pass


class ThesisLedgerValidationError(ThesisLedgerError):
    pass


ASSUMPTION_FIELDS = (
    "description",
    "condition_type",
    "metric_key",
    "operator",
    "target_value",
    "event_condition",
    "current_status",
    "supporting_evidence",
    "contradicting_evidence",
    "position",
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _require_user(session: Session, customer_id: UUID) -> None:
    if session.get(User, customer_id) is None:
        raise ThesisLedgerNotFoundError("Customer profile not found")


def _thesis_query(customer_id: UUID):
    return (
        select(Thesis)
        .options(
            selectinload(Thesis.assumptions).selectinload(
                ThesisAssumption.history
            )
        )
        .where(Thesis.user_id == customer_id)
    )


def _load_thesis(session: Session, customer_id: UUID, thesis_id: UUID) -> Thesis:
    thesis = session.scalar(_thesis_query(customer_id).where(Thesis.id == thesis_id))
    if thesis is None:
        raise ThesisLedgerNotFoundError("Thesis not found")
    return thesis


def _load_assumption(
    session: Session,
    customer_id: UUID,
    thesis_id: UUID,
    assumption_id: UUID,
) -> tuple[Thesis, ThesisAssumption]:
    thesis = _load_thesis(session, customer_id, thesis_id)
    assumption = next(
        (item for item in thesis.assumptions if item.id == assumption_id), None
    )
    if assumption is None:
        raise ThesisLedgerNotFoundError("Thesis assumption not found")
    return thesis, assumption


def _condition_type(assumption: ThesisAssumption) -> str:
    if assumption.condition_type:
        return assumption.condition_type
    return (
        AssumptionConditionType.METRIC.value
        if assumption.metric_key
        else AssumptionConditionType.EVENT.value
    )


def _assumption_values(assumption: ThesisAssumption) -> dict:
    return {
        "description": assumption.description,
        "condition_type": _condition_type(assumption),
        "metric_key": assumption.metric_key,
        "operator": assumption.operator,
        "target_value": assumption.target_value,
        "event_condition": assumption.event_condition,
        "current_status": assumption.current_status,
        "supporting_evidence": deepcopy(assumption.supporting_evidence or []),
        "contradicting_evidence": deepcopy(
            assumption.contradicting_evidence or []
        ),
        "position": assumption.position,
    }


def _serialize_history(
    history: ThesisAssumptionHistory,
) -> ThesisAssumptionHistoryResponse:
    return ThesisAssumptionHistoryResponse(
        id=history.id,
        change_type=history.change_type,
        reason=history.reason,
        previous_values=deepcopy(history.previous_values),
        current_values=deepcopy(history.current_values),
        changed_at=_as_utc(history.changed_at),
    )


def serialize_assumption(
    assumption: ThesisAssumption,
) -> ThesisAssumptionResponse:
    def history_timestamp(item: ThesisAssumptionHistory) -> float:
        changed_at = _as_utc(item.changed_at)
        return changed_at.timestamp() if changed_at is not None else 0

    history = sorted(
        assumption.history,
        key=history_timestamp,
        reverse=True,
    )
    return ThesisAssumptionResponse(
        id=assumption.id,
        **_assumption_values(assumption),
        last_evaluated_at=_as_utc(assumption.last_evaluated_at),
        history=[_serialize_history(item) for item in history],
        created_at=_as_utc(assumption.created_at),
        updated_at=_as_utc(assumption.updated_at),
    )


def serialize_thesis(thesis: Thesis) -> ThesisResponse:
    assumptions = sorted(thesis.assumptions, key=lambda item: (item.position, item.created_at))
    return ThesisResponse(
        id=thesis.id,
        ticker=thesis.ticker,
        title=thesis.title,
        statement=thesis.statement,
        status=thesis.status,
        confidence=thesis.confidence,
        research_session_id=thesis.research_session_id,
        assumptions=[serialize_assumption(item) for item in assumptions],
        created_at=_as_utc(thesis.created_at),
        updated_at=_as_utc(thesis.updated_at),
    )


def _new_assumption(
    request: ThesisAssumptionCreate, position: int
) -> ThesisAssumption:
    data = request.model_dump(mode="json")
    data["position"] = position
    return ThesisAssumption(**data)


def _record_history(
    assumption: ThesisAssumption,
    *,
    change_type: str,
    previous_values: dict | None,
    current_values: dict,
    reason: str | None = None,
) -> None:
    assumption.history.append(
        ThesisAssumptionHistory(
            change_type=change_type,
            reason=reason,
            previous_values=deepcopy(previous_values),
            current_values=deepcopy(current_values),
        )
    )


def create_thesis(
    session: Session, customer_id: UUID, request: ThesisCreate
) -> ThesisResponse:
    _require_user(session, customer_id)
    try:
        ticker = normalize_ticker(request.ticker).upper()
    except ValueError as error:
        raise ThesisLedgerValidationError(str(error)) from error
    if request.research_session_id is not None:
        research = session.scalar(
            select(ResearchSession).where(
                ResearchSession.id == request.research_session_id,
                ResearchSession.user_id == customer_id,
                ResearchSession.ticker == ticker,
            )
        )
        if research is None:
            raise ThesisLedgerValidationError(
                "Research session must belong to this customer and ticker"
            )

    thesis = Thesis(
        user_id=customer_id,
        research_session_id=request.research_session_id,
        ticker=ticker,
        title=request.title,
        statement=request.statement,
        status=request.status.value,
        confidence=request.confidence,
    )
    for index, item in enumerate(request.assumptions):
        position = item.position if "position" in item.model_fields_set else index
        assumption = _new_assumption(item, position)
        thesis.assumptions.append(assumption)
        _record_history(
            assumption,
            change_type="created",
            previous_values=None,
            current_values=_assumption_values(assumption),
        )
    session.add(thesis)
    session.commit()
    return serialize_thesis(_load_thesis(session, customer_id, thesis.id))


def list_theses(
    session: Session,
    customer_id: UUID,
    *,
    ticker: str | None = None,
    status: ThesisStatus | None = None,
) -> list[ThesisResponse]:
    _require_user(session, customer_id)
    query = _thesis_query(customer_id)
    if ticker:
        try:
            query = query.where(Thesis.ticker == normalize_ticker(ticker).upper())
        except ValueError as error:
            raise ThesisLedgerValidationError(str(error)) from error
    if status is not None:
        query = query.where(Thesis.status == status.value)
    theses = session.scalars(
        query.order_by(Thesis.updated_at.desc(), Thesis.created_at.desc())
    ).all()
    return [serialize_thesis(thesis) for thesis in theses]


def get_thesis(
    session: Session, customer_id: UUID, thesis_id: UUID
) -> ThesisResponse:
    return serialize_thesis(_load_thesis(session, customer_id, thesis_id))


def update_thesis(
    session: Session,
    customer_id: UUID,
    thesis_id: UUID,
    request: ThesisUpdate,
) -> ThesisResponse:
    thesis = _load_thesis(session, customer_id, thesis_id)
    for field_name in request.model_fields_set:
        value = getattr(request, field_name)
        if field_name == "status" and value is not None:
            value = value.value
        setattr(thesis, field_name, value)
    session.commit()
    return serialize_thesis(_load_thesis(session, customer_id, thesis_id))


def delete_thesis(session: Session, customer_id: UUID, thesis_id: UUID) -> None:
    thesis = _load_thesis(session, customer_id, thesis_id)
    session.delete(thesis)
    session.commit()


def create_assumption(
    session: Session,
    customer_id: UUID,
    thesis_id: UUID,
    request: ThesisAssumptionCreate,
) -> ThesisAssumptionResponse:
    thesis = _load_thesis(session, customer_id, thesis_id)
    position = request.position
    if "position" not in request.model_fields_set:
        position = max((item.position for item in thesis.assumptions), default=-1) + 1
    assumption = _new_assumption(request, position)
    thesis.assumptions.append(assumption)
    _record_history(
        assumption,
        change_type="created",
        previous_values=None,
        current_values=_assumption_values(assumption),
    )
    session.commit()
    _, stored = _load_assumption(
        session, customer_id, thesis_id, assumption.id
    )
    return serialize_assumption(stored)


def update_assumption(
    session: Session,
    customer_id: UUID,
    thesis_id: UUID,
    assumption_id: UUID,
    request: ThesisAssumptionUpdate,
) -> ThesisAssumptionResponse:
    _, assumption = _load_assumption(
        session, customer_id, thesis_id, assumption_id
    )
    previous = _assumption_values(assumption)
    merged = deepcopy(previous)
    update_fields = request.model_fields_set - {"change_reason"}
    for field_name in update_fields:
        value = getattr(request, field_name)
        if hasattr(value, "value"):
            value = value.value
        elif isinstance(value, list):
            value = [
                item.model_dump(mode="json") if hasattr(item, "model_dump") else item
                for item in value
            ]
        merged[field_name] = value

    try:
        validated = ThesisAssumptionCreate.model_validate(merged)
    except ValueError as error:
        raise ThesisLedgerValidationError(str(error)) from error
    current = validated.model_dump(mode="json")
    changed_fields = {
        field_name
        for field_name in ASSUMPTION_FIELDS
        if previous.get(field_name) != current.get(field_name)
    }
    if not changed_fields:
        return serialize_assumption(assumption)

    for field_name in ASSUMPTION_FIELDS:
        setattr(assumption, field_name, deepcopy(current[field_name]))
    if changed_fields & {
        "current_status",
        "supporting_evidence",
        "contradicting_evidence",
    }:
        assumption.last_evaluated_at = _utc_now()
    change_type = (
        "status_changed" if changed_fields == {"current_status"} else "updated"
    )
    _record_history(
        assumption,
        change_type=change_type,
        previous_values=previous,
        current_values=current,
        reason=request.change_reason,
    )
    session.commit()
    _, stored = _load_assumption(
        session, customer_id, thesis_id, assumption_id
    )
    return serialize_assumption(stored)


def delete_assumption(
    session: Session,
    customer_id: UUID,
    thesis_id: UUID,
    assumption_id: UUID,
) -> None:
    thesis, assumption = _load_assumption(
        session, customer_id, thesis_id, assumption_id
    )
    thesis.assumptions.remove(assumption)
    session.commit()
