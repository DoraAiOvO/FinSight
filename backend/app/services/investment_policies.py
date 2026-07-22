"""Versioned, user-owned investment policies with evidence-safe effects.

Policy data is intentionally isolated from objective market data, benchmark,
provenance, and evidence models. Consumers may use it only for the constrained
``application_effect`` values represented by the API schema.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db.models import (
    InvestmentPolicy,
    PolicyAlertRule,
    PolicyConstraint,
    PolicyMarketScope,
    PolicyMetricRule,
    PolicyPortfolioRule,
    PolicyPrinciple,
    PolicySectorPreference,
    PolicyThemePreference,
    PolicyValuationRule,
    PolicyVersion,
    User,
)
from ..models.schemas import (
    InvestmentPolicyCreate,
    InvestmentPolicyResponse,
    InvestmentPolicySummary,
    InvestmentPolicyUpdate,
    PolicyVersionCreate,
    PolicyVersionResponse,
    PolicyVersionStatus,
)


class InvestmentPolicyError(Exception):
    """Base error for investment-policy operations."""


class InvestmentPolicyNotFoundError(InvestmentPolicyError):
    pass


class InvestmentPolicyConflictError(InvestmentPolicyError):
    pass


class InvestmentPolicyValidationError(InvestmentPolicyError):
    pass


RULE_MODELS = {
    "principles": PolicyPrinciple,
    "market_scopes": PolicyMarketScope,
    "sector_preferences": PolicySectorPreference,
    "theme_preferences": PolicyThemePreference,
    "metric_rules": PolicyMetricRule,
    "constraints": PolicyConstraint,
    "valuation_rules": PolicyValuationRule,
    "portfolio_rules": PolicyPortfolioRule,
    "alert_rules": PolicyAlertRule,
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _require_user(session: Session, customer_id: UUID) -> User:
    user = session.get(User, customer_id)
    if user is None:
        raise InvestmentPolicyNotFoundError("Customer profile not found")
    return user


def _policy_query(customer_id: UUID):
    options = [
        selectinload(InvestmentPolicy.versions).selectinload(
            getattr(PolicyVersion, relationship_name)
        )
        for relationship_name in RULE_MODELS
    ]
    return (
        select(InvestmentPolicy)
        .options(*options)
        .where(InvestmentPolicy.user_id == customer_id)
    )


def _load_policy(
    session: Session, customer_id: UUID, policy_id: UUID
) -> InvestmentPolicy:
    policy = session.scalar(
        _policy_query(customer_id).where(InvestmentPolicy.id == policy_id)
    )
    if policy is None:
        # A cross-owner ID is indistinguishable from a missing ID.
        raise InvestmentPolicyNotFoundError("Investment policy not found")
    return policy


def _serialize_rule(rule) -> dict:
    return {
        "id": rule.id,
        "rule_type": rule.rule_type,
        "operator": rule.operator,
        "value": deepcopy(rule.value),
        "importance": rule.importance,
        "hard_or_soft": rule.hard_or_soft,
        "rationale": rule.rationale,
        "enabled": rule.enabled,
        "application_effect": rule.application_effect,
        "created_at": _as_utc(rule.created_at),
        "updated_at": _as_utc(rule.updated_at),
    }


def serialize_version(version: PolicyVersion) -> PolicyVersionResponse:
    payload = {
        "id": version.id,
        "investment_policy_id": version.investment_policy_id,
        "version_number": version.version_number,
        "status": version.status,
        "change_summary": version.change_summary,
        "effective_at": _as_utc(version.effective_at),
        "created_at": _as_utc(version.created_at),
        "updated_at": _as_utc(version.updated_at),
    }
    for relationship_name in RULE_MODELS:
        rules = sorted(
            getattr(version, relationship_name),
            key=lambda rule: (rule.created_at, str(rule.id)),
        )
        payload[relationship_name] = [_serialize_rule(rule) for rule in rules]
    return PolicyVersionResponse(**payload)


def _published_version_number(policy: InvestmentPolicy) -> int | None:
    published = [
        version.version_number
        for version in policy.versions
        if version.status == PolicyVersionStatus.PUBLISHED.value
    ]
    return max(published, default=None)


def serialize_policy_summary(policy: InvestmentPolicy) -> InvestmentPolicySummary:
    return InvestmentPolicySummary(
        id=policy.id,
        customer_id=policy.user_id,
        name=policy.name,
        description=policy.description,
        status=policy.status,
        is_default=policy.is_default,
        latest_version_number=max(
            (version.version_number for version in policy.versions), default=0
        ),
        published_version_number=_published_version_number(policy),
        created_at=_as_utc(policy.created_at),
        updated_at=_as_utc(policy.updated_at),
    )


def serialize_policy(policy: InvestmentPolicy) -> InvestmentPolicyResponse:
    summary = serialize_policy_summary(policy)
    versions = sorted(policy.versions, key=lambda item: item.version_number)
    return InvestmentPolicyResponse(
        **summary.model_dump(),
        versions=[serialize_version(version) for version in versions],
    )


def _retire_published_versions(policy: InvestmentPolicy) -> None:
    for version in policy.versions:
        if version.status == PolicyVersionStatus.PUBLISHED.value:
            version.status = PolicyVersionStatus.RETIRED.value


def _append_version(
    policy: InvestmentPolicy,
    request: PolicyVersionCreate,
    version_number: int,
) -> PolicyVersion:
    if request.status == PolicyVersionStatus.RETIRED:
        raise InvestmentPolicyValidationError(
            "A new policy version cannot start in retired status"
        )
    if request.status == PolicyVersionStatus.PUBLISHED:
        _retire_published_versions(policy)

    version = PolicyVersion(
        version_number=version_number,
        status=request.status.value,
        change_summary=request.change_summary,
        effective_at=(
            request.effective_at
            if request.effective_at is not None
            else (
                _utc_now()
                if request.status == PolicyVersionStatus.PUBLISHED
                else None
            )
        ),
    )
    for relationship_name, model in RULE_MODELS.items():
        rules = [
            model(**rule.model_dump(mode="json"))
            for rule in getattr(request, relationship_name)
        ]
        setattr(version, relationship_name, rules)
    policy.versions.append(version)
    return version


def list_policies(
    session: Session, customer_id: UUID
) -> list[InvestmentPolicySummary]:
    _require_user(session, customer_id)
    policies = session.scalars(
        _policy_query(customer_id).order_by(
            InvestmentPolicy.is_default.desc(),
            InvestmentPolicy.created_at,
            InvestmentPolicy.name,
        )
    ).all()
    return [serialize_policy_summary(policy) for policy in policies]


def create_policy(
    session: Session, customer_id: UUID, request: InvestmentPolicyCreate
) -> InvestmentPolicyResponse:
    _require_user(session, customer_id)
    existing = session.scalars(
        select(InvestmentPolicy).where(InvestmentPolicy.user_id == customer_id)
    ).all()
    if any(policy.name.casefold() == request.name.casefold() for policy in existing):
        raise InvestmentPolicyConflictError(
            "An investment policy with this name already exists"
        )
    if request.status.value == "archived" and request.is_default:
        raise InvestmentPolicyValidationError(
            "An archived investment policy cannot be the default"
        )

    make_default = (
        request.status.value == "active"
        and (request.is_default or not existing)
    )
    if make_default:
        for policy in existing:
            policy.is_default = False
    policy = InvestmentPolicy(
        user_id=customer_id,
        name=request.name,
        description=request.description,
        status=request.status.value,
        is_default=make_default,
    )
    _append_version(policy, request.initial_version, 1)
    session.add(policy)
    session.commit()
    return serialize_policy(_load_policy(session, customer_id, policy.id))


def get_policy(
    session: Session, customer_id: UUID, policy_id: UUID
) -> InvestmentPolicyResponse:
    return serialize_policy(_load_policy(session, customer_id, policy_id))


def update_policy(
    session: Session,
    customer_id: UUID,
    policy_id: UUID,
    request: InvestmentPolicyUpdate,
) -> InvestmentPolicyResponse:
    policy = _load_policy(session, customer_id, policy_id)
    changes = request.model_dump(exclude_unset=True)

    if "name" in changes:
        if changes["name"] is None:
            raise InvestmentPolicyValidationError("Policy name cannot be null")
        siblings = session.scalars(
            select(InvestmentPolicy).where(
                InvestmentPolicy.user_id == customer_id,
                InvestmentPolicy.id != policy_id,
            )
        ).all()
        if any(
            item.name.casefold() == changes["name"].casefold()
            for item in siblings
        ):
            raise InvestmentPolicyConflictError(
                "An investment policy with this name already exists"
            )
        policy.name = changes["name"]
    if "description" in changes:
        policy.description = changes["description"]
    if "status" in changes:
        status = changes["status"]
        status_value = status.value if hasattr(status, "value") else status
        policy.status = status_value
        if status_value == "archived":
            policy.is_default = False
    if changes.get("is_default") is True:
        if policy.status == "archived":
            raise InvestmentPolicyValidationError(
                "An archived investment policy cannot be the default"
            )
        siblings = session.scalars(
            select(InvestmentPolicy).where(
                InvestmentPolicy.user_id == customer_id,
                InvestmentPolicy.id != policy_id,
            )
        ).all()
        for item in siblings:
            item.is_default = False
        policy.is_default = True
    elif changes.get("is_default") is False:
        policy.is_default = False

    session.commit()
    return serialize_policy(_load_policy(session, customer_id, policy_id))


def delete_policy(session: Session, customer_id: UUID, policy_id: UUID) -> None:
    policy = _load_policy(session, customer_id, policy_id)
    was_default = policy.is_default
    session.delete(policy)
    session.flush()
    if was_default:
        replacement = session.scalar(
            select(InvestmentPolicy)
            .where(
                InvestmentPolicy.user_id == customer_id,
                InvestmentPolicy.status == "active",
            )
            .order_by(InvestmentPolicy.created_at)
        )
        if replacement is not None:
            replacement.is_default = True
    session.commit()


def list_policy_versions(
    session: Session, customer_id: UUID, policy_id: UUID
) -> list[PolicyVersionResponse]:
    policy = _load_policy(session, customer_id, policy_id)
    return [
        serialize_version(version)
        for version in sorted(policy.versions, key=lambda item: item.version_number)
    ]


def create_policy_version(
    session: Session,
    customer_id: UUID,
    policy_id: UUID,
    request: PolicyVersionCreate,
) -> PolicyVersionResponse:
    policy = _load_policy(session, customer_id, policy_id)
    if policy.status == "archived":
        raise InvestmentPolicyValidationError(
            "Cannot add a version to an archived investment policy"
        )
    next_number = max(
        (version.version_number for version in policy.versions), default=0
    ) + 1
    version = _append_version(policy, request, next_number)
    session.commit()
    policy = _load_policy(session, customer_id, policy_id)
    stored = next(item for item in policy.versions if item.id == version.id)
    return serialize_version(stored)


def get_policy_version(
    session: Session,
    customer_id: UUID,
    policy_id: UUID,
    version_id: UUID,
) -> PolicyVersionResponse:
    policy = _load_policy(session, customer_id, policy_id)
    version = next(
        (item for item in policy.versions if item.id == version_id), None
    )
    if version is None:
        raise InvestmentPolicyNotFoundError("Policy version not found")
    return serialize_version(version)
