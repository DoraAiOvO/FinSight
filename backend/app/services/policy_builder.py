"""Guarded natural-language extraction for investment policy proposals."""

from __future__ import annotations

import re
from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import InvestmentPolicyProposal, User
from ..models.schemas import (
    InvestmentPolicyCreate,
    InvestmentPolicyProposalPayload,
    InvestmentPolicyResponse,
    PolicyExtractionIssue,
    PolicyExtractionRequest,
    PolicyExtractionResponse,
    PolicyProposalConfirmRequest,
    PolicyVersionCreate,
    PolicyVersionStatus,
)
from . import ai, investment_policies, policy_presets


RULE_FAMILIES = tuple(investment_policies.RULE_MODELS)

DEFAULT_EFFECTS = {
    "principles": "report_emphasis",
    "market_scopes": "preference_fit_scoring",
    "sector_preferences": "ranking",
    "theme_preferences": "ranking",
    "metric_rules": "preference_fit_scoring",
    "constraints": "filtering",
    "valuation_rules": "preference_fit_scoring",
    "portfolio_rules": "preference_fit_scoring",
    "alert_rules": "alerts",
}

SECTOR_NAMES = {
    "technology": "Technology",
    "tecnología": "Technology",
    "technologie": "Technology",
    "科技": "Technology",
    "healthcare": "Healthcare",
    "salud": "Healthcare",
    "santé": "Healthcare",
    "医疗保健": "Healthcare",
    "financials": "Financials",
    "finanzas": "Financials",
    "finance": "Financials",
    "金融": "Financials",
    "energy": "Energy",
    "energía": "Energy",
    "énergie": "Energy",
    "能源": "Energy",
}

RULE_TYPE_ALIASES = {
    "p_e": "price_to_earnings",
    "pe": "price_to_earnings",
    "p_e_ratio": "price_to_earnings",
    "ev_ebitda": "ev_to_ebitda",
    "free_cash_flow": "fcf",
    "return_on_invested_capital": "roic",
    "earnings_per_share": "eps",
}

AMBIGUITY_PATTERN = re.compile(
    r"\b(maybe|perhaps|possibly|not sure|either\b.+\bor|roughly|approximately)"
    r"\b|quiz[aá]s|tal vez|peut[- ]être|不确定|也许|或者",
    re.IGNORECASE | re.DOTALL,
)


class PolicyBuilderError(Exception):
    pass


class PolicyBuilderUnavailableError(PolicyBuilderError):
    pass


class PolicyBuilderExtractionError(PolicyBuilderError):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_user(session: Session, customer_id: UUID) -> None:
    if session.get(User, customer_id) is None:
        raise investment_policies.InvestmentPolicyNotFoundError(
            "Customer profile not found"
        )


def _snake_case(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip()).strip("_").lower()
    return RULE_TYPE_ALIASES.get(normalized, normalized)


def _canonicalize_ticker_value(value: Any) -> Any:
    def ticker(candidate):
        if not isinstance(candidate, str):
            return candidate
        stripped = candidate.strip()
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9.-]{0,14}", stripped):
            return stripped.upper()
        return stripped

    if isinstance(value, list):
        return [ticker(item) for item in value]
    return ticker(value)


def _canonicalize_sector_value(value: Any) -> Any:
    def sector(candidate):
        if not isinstance(candidate, str):
            return candidate
        stripped = candidate.strip()
        return SECTOR_NAMES.get(stripped.casefold(), stripped)

    if isinstance(value, list):
        return [sector(item) for item in value]
    return sector(value)


def _normalize_rule(family: str, raw_rule: Any) -> dict:
    if not isinstance(raw_rule, dict):
        raise PolicyBuilderExtractionError(
            f"AI extraction returned an invalid {family} rule"
        )
    rule = deepcopy(raw_rule)
    rule_type = _snake_case(str(rule.get("rule_type", "")))
    if not rule_type:
        raise PolicyBuilderExtractionError(
            f"AI extraction omitted rule_type for {family}"
        )
    rule["rule_type"] = rule_type
    rule.setdefault("application_effect", DEFAULT_EFFECTS[family])
    rule.setdefault("importance", 3)
    rule.setdefault("hard_or_soft", "soft")
    rule.setdefault("enabled", True)
    if family == "constraints" and rule["hard_or_soft"] == "hard":
        rule["application_effect"] = "filtering"
    if family == "alert_rules":
        rule["application_effect"] = "alerts"
    if "ticker" in rule_type or "symbol" in rule_type:
        rule["value"] = _canonicalize_ticker_value(rule.get("value"))
    if family == "sector_preferences" or "sector" in rule_type:
        rule["value"] = _canonicalize_sector_value(rule.get("value"))
    allowed = {
        "rule_type",
        "operator",
        "value",
        "importance",
        "hard_or_soft",
        "rationale",
        "enabled",
        "application_effect",
    }
    return {key: value for key, value in rule.items() if key in allowed}


def _issue(
    code: str,
    message: str,
    *,
    severity: str = "warning",
    source_text: str | None = None,
    rule_families: list[str] | None = None,
) -> PolicyExtractionIssue:
    return PolicyExtractionIssue(
        issue_id=str(uuid4()),
        code=code,
        severity=severity,
        message=message,
        source_text=source_text,
        rule_families=rule_families or [],
    )


def _normalize_issues(raw_issues: Any) -> list[PolicyExtractionIssue]:
    if raw_issues is None:
        return []
    if not isinstance(raw_issues, list):
        raise PolicyBuilderExtractionError("AI extraction returned invalid issues")
    issues = []
    for raw in raw_issues:
        if not isinstance(raw, dict):
            raise PolicyBuilderExtractionError(
                "AI extraction returned an invalid issue"
            )
        try:
            issues.append(
                PolicyExtractionIssue(
                    issue_id=str(uuid4()),
                    code=raw.get("code", "low_confidence"),
                    severity=raw.get("severity", "warning"),
                    message=raw.get(
                        "message", "The model reported low extraction confidence."
                    ),
                    source_text=raw.get("source_text"),
                    rule_families=[
                        family
                        for family in raw.get("rule_families", [])
                        if family in RULE_FAMILIES
                    ],
                )
            )
        except ValidationError as error:
            raise PolicyBuilderExtractionError(
                "AI extraction returned an invalid issue"
            ) from error
    return issues


def _comparable_values(value: Any) -> set[str]:
    values = value if isinstance(value, list) else [value]
    return {
        str(item).strip().casefold()
        for item in values
        if item is not None and str(item).strip()
    }


def _detect_conflicts(
    rules_by_family: dict[str, list[dict]],
) -> list[PolicyExtractionIssue]:
    issues: list[PolicyExtractionIssue] = []
    for family, rules in rules_by_family.items():
        grouped: dict[str, list[dict]] = defaultdict(list)
        for rule in rules:
            if rule.get("enabled", True):
                grouped[rule["rule_type"]].append(rule)
        for rule_type, related in grouped.items():
            equals = [
                rule for rule in related if rule.get("operator") in {"equals", "equal"}
            ]
            equal_values = {
                repr(rule.get("value")) for rule in equals
            }
            if len(equal_values) > 1:
                issues.append(
                    _issue(
                        "conflicting_instructions",
                        (
                            f"Multiple different values were given for "
                            f"{rule_type.replace('_', ' ')}."
                        ),
                        severity="blocking",
                        rule_families=[family],
                    )
                )
            lower_bounds = [
                float(rule["value"])
                for rule in related
                if rule.get("operator")
                in {"greater_than", "greater_than_or_equal", "minimum"}
                and isinstance(rule.get("value"), (int, float))
            ]
            upper_bounds = [
                float(rule["value"])
                for rule in related
                if rule.get("operator")
                in {"less_than", "less_than_or_equal", "maximum"}
                and isinstance(rule.get("value"), (int, float))
            ]
            if lower_bounds and upper_bounds and max(lower_bounds) > min(upper_bounds):
                issues.append(
                    _issue(
                        "conflicting_instructions",
                        (
                            f"The minimum for {rule_type.replace('_', ' ')} "
                            "is above its maximum."
                        ),
                        severity="blocking",
                        rule_families=[family],
                    )
                )

    preferred: dict[str, set[str]] = defaultdict(set)
    excluded: dict[str, set[str]] = defaultdict(set)
    for family, rules in rules_by_family.items():
        for rule in rules:
            rule_type = rule["rule_type"]
            values = _comparable_values(rule.get("value"))
            subject = next(
                (
                    token
                    for token in ("ticker", "sector", "theme", "market", "country")
                    if token in rule_type
                ),
                None,
            )
            if not subject:
                continue
            if any(token in rule_type for token in ("exclude", "avoid", "prohibit")):
                excluded[subject].update(values)
            if any(token in rule_type for token in ("prefer", "include", "allow")):
                preferred[subject].update(values)
    for subject in preferred.keys() | excluded.keys():
        overlap = sorted(preferred[subject] & excluded[subject])
        if overlap:
            issues.append(
                _issue(
                    "conflicting_instructions",
                    (
                        f"{', '.join(overlap)} is both preferred and excluded "
                        f"as a {subject}."
                    ),
                    severity="blocking",
                    rule_families=list(RULE_FAMILIES),
                )
            )
    return issues


def _detect_languages(raw: Any, hint: str | None, source: str) -> list[str]:
    languages = []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str):
                normalized = item.strip().replace("_", "-")
                if normalized and normalized not in languages:
                    languages.append(normalized)
    if not languages and hint:
        languages.append(hint)
    if not languages:
        if re.search(r"[\u4e00-\u9fff]", source):
            languages.append("zh")
        if re.search(r"[A-Za-z]", source):
            languages.append("en")
    return languages or ["und"]


def _normalize_extraction(
    raw: dict,
    request: PolicyExtractionRequest,
) -> tuple[InvestmentPolicyProposalPayload, list[str], list[PolicyExtractionIssue]]:
    if not isinstance(raw, dict):
        raise PolicyBuilderExtractionError("AI extraction did not return an object")
    raw_rules = raw.get("rules")
    if not isinstance(raw_rules, dict):
        raise PolicyBuilderExtractionError("AI extraction omitted structured rules")
    rules_by_family = {
        family: [
            _normalize_rule(family, rule)
            for rule in raw_rules.get(family, [])
        ]
        for family in RULE_FAMILIES
    }
    try:
        version = PolicyVersionCreate(
            status=PolicyVersionStatus.DRAFT,
            change_summary="AI-extracted proposal awaiting user confirmation",
            **rules_by_family,
        )
        proposal = InvestmentPolicyProposalPayload(
            name=raw.get("name", "My investment policy"),
            description=raw.get("description"),
            initial_version=version,
        )
    except ValidationError as error:
        raise PolicyBuilderExtractionError(
            "AI extraction did not match the investment policy schema"
        ) from error

    issues = _normalize_issues(raw.get("issues"))
    if AMBIGUITY_PATTERN.search(request.preferences) and not any(
        issue.code == "ambiguous_instruction" for issue in issues
    ):
        issues.append(
            _issue(
                "ambiguous_instruction",
                "Some preference wording may have more than one interpretation.",
                source_text=request.preferences,
            )
        )
    issues.extend(_detect_conflicts(rules_by_family))
    if not any(rules_by_family.values()):
        issues.append(
            _issue(
                "unsupported_instruction",
                "No actionable investment policy rules were extracted.",
                severity="blocking",
                source_text=request.preferences,
            )
        )
    languages = _detect_languages(
        raw.get("detected_languages"),
        request.language_hint,
        request.preferences,
    )
    return proposal, languages, issues


def extract_proposal(
    session: Session,
    customer_id: UUID,
    request: PolicyExtractionRequest,
) -> PolicyExtractionResponse:
    _require_user(session, customer_id)
    raw = ai.extract_investment_policy(
        request.preferences,
        language_hint=request.language_hint,
    )
    if raw is None:
        raise PolicyBuilderUnavailableError(
            "Policy extraction is temporarily unavailable; no policy was saved."
        )
    proposal, languages, issues = _normalize_extraction(raw, request)
    record = InvestmentPolicyProposal(
        user_id=customer_id,
        source_text=request.preferences,
        language_hint=request.language_hint,
        detected_languages=languages,
        proposed_policy=proposal.model_dump(mode="json"),
        issues=[issue.model_dump(mode="json") for issue in issues],
        status="pending_review",
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return PolicyExtractionResponse(
        proposal_id=record.id,
        detected_languages=languages,
        proposed_policy=proposal,
        issues=issues,
        ai_provider="Anthropic",
        created_at=record.created_at,
    )


def confirm_proposal(
    session: Session,
    customer_id: UUID,
    proposal_id: UUID,
    request: PolicyProposalConfirmRequest,
) -> InvestmentPolicyResponse:
    record = session.scalar(
        select(InvestmentPolicyProposal).where(
            InvestmentPolicyProposal.id == proposal_id,
            InvestmentPolicyProposal.user_id == customer_id,
        )
    )
    if record is None:
        raise investment_policies.InvestmentPolicyNotFoundError(
            "Investment policy proposal not found"
        )
    if record.status != "pending_review":
        raise investment_policies.InvestmentPolicyConflictError(
            "This investment policy proposal has already been confirmed"
        )

    issue_ids = {issue["issue_id"] for issue in record.issues}
    missing_acknowledgements = issue_ids - set(request.acknowledged_issue_ids)
    if missing_acknowledgements:
        raise investment_policies.InvestmentPolicyValidationError(
            "Review and acknowledge every extraction issue before confirming"
        )

    rules_by_family = {
        family: [
            rule.model_dump(mode="json")
            for rule in getattr(request.policy.initial_version, family)
        ]
        for family in RULE_FAMILIES
    }
    if _detect_conflicts(rules_by_family):
        raise investment_policies.InvestmentPolicyValidationError(
            "Resolve conflicting policy rules before confirming"
        )

    published_version = request.policy.initial_version.model_copy(
        update={
            "status": PolicyVersionStatus.PUBLISHED,
            "change_summary": (
                request.policy.initial_version.change_summary
                or "Confirmed from natural-language policy proposal"
            ),
            "effective_at": None,
        }
    )
    create_request = InvestmentPolicyCreate(
        name=request.policy.name,
        description=request.policy.description,
        is_default=request.make_default,
        initial_version=published_version,
    )
    is_preset_proposal = policy_presets.is_preset_source(record.source_text)
    created = investment_policies.create_policy(
        session,
        customer_id,
        create_request,
        commit=False,
        default_if_first=not is_preset_proposal,
    )
    confirmed_version = created.versions[-1]
    record.status = "confirmed"
    record.confirmed_policy_id = created.id
    record.confirmed_version_id = confirmed_version.id
    record.confirmed_at = _utc_now()
    session.commit()
    return investment_policies.get_policy(session, customer_id, created.id)
