"""Deterministic, opt-in investment-policy presets.

Presets are editable research starting points, not recommendations. Selecting a
preset creates only a review proposal; it cannot create or activate a policy.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from ..db.models import InvestmentPolicyProposal, User
from ..models.schemas import (
    InvestmentPolicyProposalPayload,
    PolicyExtractionResponse,
    PolicyPresetSummary,
    PolicyVersionCreate,
    PolicyVersionStatus,
)
from . import investment_policies


LONG_TERM_TECH_VALUE_ID = "long-term-tech-value"
LONG_TERM_TECH_VALUE_DISCLAIMER = (
    "This editable research starting point is inspired by general long-term "
    "business-owner and value-investing principles. It does not reproduce, "
    "predict, or represent the decisions of any real investor."
)
LONG_TERM_TECH_VALUE_THEMES = [
    "software",
    "semiconductors",
    "internet",
    "AI",
    "cloud computing",
    "new energy",
    "smart vehicles",
]
LONG_TERM_TECH_VALUE_MARKETS = [
    "United States",
    "Japan",
    "Hong Kong",
]


def _rule(
    rule_type: str,
    operator: str,
    value,
    rationale: str,
    *,
    importance: int = 4,
    strength: str = "soft",
    effect: str = "preference_fit_scoring",
) -> dict:
    return {
        "rule_type": rule_type,
        "operator": operator,
        "value": value,
        "importance": importance,
        "hard_or_soft": strength,
        "rationale": rationale,
        "enabled": True,
        "application_effect": effect,
    }


def _principle(rule_type: str, rationale: str, *, importance: int = 5) -> dict:
    return _rule(
        rule_type,
        "equals",
        True,
        rationale,
        importance=importance,
        effect="report_emphasis",
    )


LONG_TERM_TECH_VALUE_POLICY = InvestmentPolicyProposalPayload(
    name="Long-Term Tech Value",
    description=LONG_TERM_TECH_VALUE_DISCLAIMER,
    initial_version=PolicyVersionCreate(
        status=PolicyVersionStatus.DRAFT,
        change_summary=(
            "Long-Term Tech Value preset selected for user review and editing"
        ),
        principles=[
            _principle(
                "business_quality",
                "Emphasize durable economics, customer value, and understandable "
                "business models.",
            ),
            _principle(
                "economic_moat",
                "Research evidence of durable competitive advantages and how they "
                "could weaken.",
            ),
            _principle(
                "management_and_capital_allocation",
                "Assess management incentives, candor, reinvestment discipline, "
                "acquisitions, buybacks, and balance-sheet choices.",
            ),
            _principle(
                "long_term_free_cash_flow",
                "Center valuation on conservatively estimated long-term free cash "
                "flow rather than short-term price movement.",
            ),
            _principle(
                "structural_growth",
                "Prefer businesses with evidence-backed, durable demand drivers.",
                importance=4,
            ),
            _principle(
                "margin_of_safety",
                "Require an explicit gap between price and a conservative estimate "
                "of value.",
            ),
            _principle(
                "inversion_and_permanent_loss_risks",
                "Ask what could permanently impair capital before considering "
                "upside.",
            ),
            _principle(
                "concentrated_quality_research",
                "Favor deep research on a limited set of high-quality candidates "
                "without treating concentration as a guarantee of returns.",
                importance=4,
            ),
        ],
        market_scopes=[
            _rule(
                "preferred_markets",
                "includes_any",
                LONG_TERM_TECH_VALUE_MARKETS,
                "Start research in the United States, Japan, and Hong Kong while "
                "keeping the market list editable.",
            )
        ],
        theme_preferences=[
            _rule(
                "preferred_themes",
                "includes_any",
                LONG_TERM_TECH_VALUE_THEMES,
                "Use the preset's technology and structural-growth themes as an "
                "editable research universe.",
                effect="ranking",
            )
        ],
        metric_rules=[
            _rule(
                "minimum_return_on_invested_capital",
                "greater_than_or_equal",
                0.15,
                "Editable starting threshold for sustained business quality.",
            ),
            _rule(
                "minimum_free_cash_flow_margin",
                "greater_than_or_equal",
                0.10,
                "Editable starting threshold for cash-generating economics.",
            ),
            _rule(
                "minimum_five_year_revenue_cagr",
                "greater_than_or_equal",
                0.08,
                "Editable starting threshold for demonstrated long-term growth.",
            ),
            _rule(
                "maximum_net_debt_to_ebitda",
                "less_than_or_equal",
                2.0,
                "Editable balance-sheet risk threshold intended to reduce "
                "permanent-loss exposure.",
            ),
        ],
        constraints=[
            _rule(
                "permanent_loss_risk_review_required",
                "equals",
                True,
                "Require an explicit review of leverage, disruption, governance, "
                "dilution, cyclicality, and other permanent-loss paths.",
                importance=5,
                strength="hard",
                effect="filtering",
            ),
            _rule(
                "inversion_checklist_required",
                "includes_all",
                [
                    "balance-sheet fragility",
                    "moat erosion",
                    "management misallocation",
                    "technology displacement",
                    "valuation compression",
                ],
                "Research how the thesis can fail before relying on the upside case.",
                importance=5,
                strength="hard",
                effect="filtering",
            ),
        ],
        valuation_rules=[
            _rule(
                "minimum_margin_of_safety",
                "greater_than_or_equal",
                0.25,
                "Editable discount to a conservative intrinsic-value estimate; "
                "the estimate and its assumptions still require review.",
                importance=5,
            )
        ],
        portfolio_rules=[
            _rule(
                "target_position_count",
                "greater_than_or_equal",
                8,
                "Editable lower bound for a focused but diversified research list.",
            ),
            _rule(
                "target_position_count",
                "less_than_or_equal",
                15,
                "Editable upper bound for concentrated quality research.",
            ),
            _rule(
                "maximum_position_weight",
                "less_than_or_equal",
                0.15,
                "Editable single-position limit to constrain permanent-loss impact.",
                importance=5,
            ),
            _rule(
                "maximum_theme_weight",
                "less_than_or_equal",
                0.40,
                "Editable limit for correlated exposure to any one theme.",
            ),
        ],
        alert_rules=[
            _rule(
                "thesis_break_review",
                "equals",
                True,
                "Alert when evidence suggests moat erosion, capital-allocation "
                "deterioration, balance-sheet stress, or a broken cash-flow thesis.",
                importance=5,
                effect="alerts",
            )
        ],
    ),
)

PRESETS = {
    LONG_TERM_TECH_VALUE_ID: (
        PolicyPresetSummary(
            preset_id=LONG_TERM_TECH_VALUE_ID,
            name=LONG_TERM_TECH_VALUE_POLICY.name,
            description=(
                "An editable, quality-focused technology research starting point."
            ),
            disclaimer=LONG_TERM_TECH_VALUE_DISCLAIMER,
            default_themes=LONG_TERM_TECH_VALUE_THEMES,
            default_markets=LONG_TERM_TECH_VALUE_MARKETS,
        ),
        LONG_TERM_TECH_VALUE_POLICY,
    )
}


def list_presets() -> list[PolicyPresetSummary]:
    """Return metadata only; listing a preset never selects or applies it."""
    return [entry[0].model_copy(deep=True) for entry in PRESETS.values()]


def is_preset_source(source_text: str) -> bool:
    """Identify only proposals created from a registered deterministic preset."""
    return source_text in {
        f"preset:{preset_id}"
        for preset_id in PRESETS
    }


def create_proposal(
    session: Session,
    customer_id: UUID,
    preset_id: str,
) -> PolicyExtractionResponse:
    """Create an inactive, editable proposal after an explicit preset choice."""
    if session.get(User, customer_id) is None:
        raise investment_policies.InvestmentPolicyNotFoundError(
            "Customer profile not found"
        )
    preset = PRESETS.get(preset_id)
    if preset is None:
        raise investment_policies.InvestmentPolicyNotFoundError(
            "Investment policy preset not found"
        )

    proposal = preset[1].model_copy(deep=True)
    record = InvestmentPolicyProposal(
        user_id=customer_id,
        source_text=f"preset:{preset_id}",
        language_hint=None,
        detected_languages=[],
        proposed_policy=proposal.model_dump(mode="json"),
        issues=[],
        status="pending_review",
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return PolicyExtractionResponse(
        proposal_id=record.id,
        detected_languages=[],
        proposed_policy=proposal,
        issues=[],
        ai_provider="Deterministic FinSight preset",
        created_at=record.created_at,
    )
