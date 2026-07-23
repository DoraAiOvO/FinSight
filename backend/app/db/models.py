"""Persistent domain models for users and their investment research workspace."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, UUIDPrimaryKeyMixin


JSON_DICT = MutableDict.as_mutable(JSON)
JSON_LIST = MutableList.as_mutable(JSON)


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    # Email remains optional until authentication is introduced. The customer
    # onboarding flow creates a browser-scoped anonymous user and can attach an
    # email to that same user in a later authentication phase.
    email: Mapped[str | None] = mapped_column(String(320), nullable=True, unique=True)
    display_name: Mapped[str | None] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    customer_profile: Mapped[CustomerProfile | None] = relationship(
        back_populates="user", cascade="all, delete-orphan", single_parent=True
    )
    watchlists: Mapped[list[Watchlist]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    research_sessions: Mapped[list[ResearchSession]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    saved_reports: Mapped[list[SavedReport]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    theses: Mapped[list[Thesis]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    feedback: Mapped[list[Feedback]] = relationship(back_populates="user")
    alert_preferences: Mapped[list[AlertPreference]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    investment_policies: Mapped[list[InvestmentPolicy]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    investment_policy_proposals: Mapped[list[InvestmentPolicyProposal]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class CustomerProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "customer_profiles"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    experience_level: Mapped[str | None] = mapped_column(String(32))
    research_horizon: Mapped[str | None] = mapped_column(String(32))
    priorities: Mapped[list[str]] = mapped_column(
        JSON_LIST, nullable=False, default=list
    )
    risk_comfort: Mapped[str | None] = mapped_column(String(32))
    preferred_report_depth: Mapped[str | None] = mapped_column(String(32))
    preferred_language: Mapped[str] = mapped_column(
        String(12), nullable=False, default="en"
    )
    industries_of_interest: Mapped[list[str]] = mapped_column(
        JSON_LIST, nullable=False, default=list
    )
    excluded_investment_types: Mapped[list[str]] = mapped_column(
        JSON_LIST, nullable=False, default=list
    )
    presentation_preferences: Mapped[dict[str, Any]] = mapped_column(
        JSON_DICT, nullable=False, default=dict
    )

    user: Mapped[User] = relationship(back_populates="customer_profile")


class Watchlist(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "watchlists"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_watchlists_user_name"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    user: Mapped[User] = relationship(back_populates="watchlists")
    items: Mapped[list[WatchlistItem]] = relationship(
        back_populates="watchlist", cascade="all, delete-orphan"
    )


class WatchlistItem(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (
        UniqueConstraint(
            "watchlist_id", "ticker", name="uq_watchlist_items_watchlist_ticker"
        ),
        Index("ix_watchlist_items_ticker", "ticker"),
    )

    watchlist_id: Mapped[UUID] = mapped_column(
        ForeignKey("watchlists.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ticker: Mapped[str] = mapped_column(String(32), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    watchlist: Mapped[Watchlist] = relationship(back_populates="items")


class ResearchSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "research_sessions"
    __table_args__ = (Index("ix_research_sessions_user_ticker", "user_id", "ticker"),)

    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    ticker: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="started")
    language: Mapped[str] = mapped_column(String(12), nullable=False, default="en")
    request_payload: Mapped[dict[str, Any]] = mapped_column(
        JSON_DICT, nullable=False, default=dict
    )
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON_DICT)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User | None] = relationship(back_populates="research_sessions")
    saved_reports: Mapped[list[SavedReport]] = relationship(
        back_populates="research_session"
    )
    theses: Mapped[list[Thesis]] = relationship(back_populates="research_session")
    feedback: Mapped[list[Feedback]] = relationship(back_populates="research_session")


class SavedReport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "saved_reports"
    __table_args__ = (Index("ix_saved_reports_user_ticker", "user_id", "ticker"),)

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    research_session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("research_sessions.id", ondelete="SET NULL"), nullable=True
    )
    ticker: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    report_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="standard"
    )
    language: Mapped[str] = mapped_column(String(12), nullable=False, default="en")
    content: Mapped[dict[str, Any]] = mapped_column(JSON_DICT, nullable=False)

    user: Mapped[User] = relationship(back_populates="saved_reports")
    research_session: Mapped[ResearchSession | None] = relationship(
        back_populates="saved_reports"
    )
    feedback: Mapped[list[Feedback]] = relationship(back_populates="saved_report")


class Thesis(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "theses"
    __table_args__ = (
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name="confidence_range",
        ),
        Index("ix_theses_user_ticker", "user_id", "ticker"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    research_session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("research_sessions.id", ondelete="SET NULL"), nullable=True
    )
    ticker: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    confidence: Mapped[float | None] = mapped_column(Float)

    user: Mapped[User] = relationship(back_populates="theses")
    research_session: Mapped[ResearchSession | None] = relationship(
        back_populates="theses"
    )
    assumptions: Mapped[list[ThesisAssumption]] = relationship(
        back_populates="thesis",
        cascade="all, delete-orphan",
        order_by="ThesisAssumption.position",
    )


class ThesisAssumption(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "thesis_assumptions"

    thesis_id: Mapped[UUID] = mapped_column(
        ForeignKey("theses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    condition_type: Mapped[str | None] = mapped_column(String(32))
    metric_key: Mapped[str | None] = mapped_column(String(120))
    operator: Mapped[str | None] = mapped_column(String(24))
    target_value: Mapped[str | None] = mapped_column(String(120))
    event_condition: Mapped[str | None] = mapped_column(Text)
    current_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unreviewed"
    )
    supporting_evidence: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON_LIST, nullable=False, default=list
    )
    contradicting_evidence: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON_LIST, nullable=False, default=list
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    thesis: Mapped[Thesis] = relationship(back_populates="assumptions")
    history: Mapped[list[ThesisAssumptionHistory]] = relationship(
        back_populates="assumption",
        cascade="all, delete-orphan",
        order_by="ThesisAssumptionHistory.changed_at.desc()",
    )


class ThesisAssumptionHistory(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "thesis_assumption_history"

    assumption_id: Mapped[UUID] = mapped_column(
        ForeignKey("thesis_assumptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    change_type: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    previous_values: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    current_values: Mapped[dict[str, Any]] = mapped_column(
        JSON_DICT, nullable=False, default=dict
    )
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    assumption: Mapped[ThesisAssumption] = relationship(back_populates="history")


class Feedback(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "feedback"
    __table_args__ = (
        CheckConstraint(
            "rating IS NULL OR (rating >= 1 AND rating <= 5)", name="rating_range"
        ),
    )

    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    research_session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("research_sessions.id", ondelete="SET NULL"), nullable=True
    )
    saved_report_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("saved_reports.id", ondelete="SET NULL"), nullable=True
    )
    section_key: Mapped[str | None] = mapped_column(String(120))
    feedback_type: Mapped[str] = mapped_column(String(32), nullable=False)
    rating: Mapped[int | None] = mapped_column(Integer)
    message: Mapped[str | None] = mapped_column(Text)
    context: Mapped[dict[str, Any]] = mapped_column(
        JSON_DICT, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User | None] = relationship(back_populates="feedback")
    research_session: Mapped[ResearchSession | None] = relationship(
        back_populates="feedback"
    )
    saved_report: Mapped[SavedReport | None] = relationship(back_populates="feedback")


class AlertPreference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "alert_preferences"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "ticker",
            "alert_type",
            "channel",
            name="uq_alert_preferences_scope",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ticker: Mapped[str | None] = mapped_column(String(32), index=True)
    alert_type: Mapped[str] = mapped_column(String(64), nullable=False)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="in_app")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    frequency: Mapped[str] = mapped_column(String(32), nullable=False, default="immediate")
    conditions: Mapped[dict[str, Any]] = mapped_column(
        JSON_DICT, nullable=False, default=dict
    )

    user: Mapped[User] = relationship(back_populates="alert_preferences")


class InvestmentPolicy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A user-owned policy container with an immutable version history."""

    __tablename__ = "investment_policies"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "name", name="uq_investment_policies_user_name"
        ),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    user: Mapped[User] = relationship(back_populates="investment_policies")
    versions: Mapped[list[PolicyVersion]] = relationship(
        back_populates="investment_policy",
        cascade="all, delete-orphan",
        order_by="PolicyVersion.version_number",
    )


class InvestmentPolicyProposal(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A review-only AI extraction that has no policy application effect."""

    __tablename__ = "investment_policy_proposals"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    language_hint: Mapped[str | None] = mapped_column(String(35))
    detected_languages: Mapped[list[str]] = mapped_column(
        JSON_LIST, nullable=False, default=list
    )
    proposed_policy: Mapped[dict[str, Any]] = mapped_column(
        JSON_DICT, nullable=False, default=dict
    )
    issues: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON_LIST, nullable=False, default=list
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending_review"
    )
    confirmed_policy_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("investment_policies.id", ondelete="SET NULL"), nullable=True
    )
    confirmed_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("policy_versions.id", ondelete="SET NULL"), nullable=True
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="investment_policy_proposals")


class PolicyVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A complete point-in-time snapshot of one investment policy."""

    __tablename__ = "policy_versions"
    __table_args__ = (
        UniqueConstraint(
            "investment_policy_id",
            "version_number",
            name="uq_policy_versions_policy_number",
        ),
        CheckConstraint(
            "version_number > 0", name="positive_version_number"
        ),
    )

    investment_policy_id: Mapped[UUID] = mapped_column(
        ForeignKey("investment_policies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    change_summary: Mapped[str | None] = mapped_column(Text)
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    investment_policy: Mapped[InvestmentPolicy] = relationship(
        back_populates="versions"
    )
    principles: Mapped[list[PolicyPrinciple]] = relationship(
        back_populates="policy_version", cascade="all, delete-orphan"
    )
    market_scopes: Mapped[list[PolicyMarketScope]] = relationship(
        back_populates="policy_version", cascade="all, delete-orphan"
    )
    sector_preferences: Mapped[list[PolicySectorPreference]] = relationship(
        back_populates="policy_version", cascade="all, delete-orphan"
    )
    theme_preferences: Mapped[list[PolicyThemePreference]] = relationship(
        back_populates="policy_version", cascade="all, delete-orphan"
    )
    metric_rules: Mapped[list[PolicyMetricRule]] = relationship(
        back_populates="policy_version", cascade="all, delete-orphan"
    )
    constraints: Mapped[list[PolicyConstraint]] = relationship(
        back_populates="policy_version", cascade="all, delete-orphan"
    )
    valuation_rules: Mapped[list[PolicyValuationRule]] = relationship(
        back_populates="policy_version", cascade="all, delete-orphan"
    )
    portfolio_rules: Mapped[list[PolicyPortfolioRule]] = relationship(
        back_populates="policy_version", cascade="all, delete-orphan"
    )
    alert_rules: Mapped[list[PolicyAlertRule]] = relationship(
        back_populates="policy_version", cascade="all, delete-orphan"
    )


def _policy_rule_constraints() -> tuple[CheckConstraint, ...]:
    """Return fresh constraints for each concrete rule table."""

    return (
        CheckConstraint(
            "importance >= 1 AND importance <= 5", name="importance_range"
        ),
        CheckConstraint(
            "hard_or_soft IN ('hard', 'soft')", name="hard_or_soft_values"
        ),
        CheckConstraint(
            "application_effect IN "
            "('filtering', 'ranking', 'report_emphasis', 'alerts', "
            "'preference_fit_scoring')",
            name="safe_application_effects",
        ),
    )


class PolicyRuleMixin:
    """Shared contract for every versioned policy rule.

    ``application_effect`` is deliberately restricted to presentation and
    preference-fit concerns. No policy rule can be classified as changing,
    hiding, or recalculating objective evidence or benchmarks.
    """

    policy_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("policy_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_type: Mapped[str] = mapped_column(String(120), nullable=False)
    operator: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[Any] = mapped_column(JSON, nullable=False)
    importance: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    hard_or_soft: Mapped[str] = mapped_column(
        String(16), nullable=False, default="soft"
    )
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    application_effect: Mapped[str] = mapped_column(
        String(32), nullable=False, default="preference_fit_scoring"
    )


class PolicyPrinciple(
    UUIDPrimaryKeyMixin, TimestampMixin, PolicyRuleMixin, Base
):
    __tablename__ = "policy_principles"
    __table_args__ = _policy_rule_constraints()

    policy_version: Mapped[PolicyVersion] = relationship(
        back_populates="principles"
    )


class PolicyMarketScope(
    UUIDPrimaryKeyMixin, TimestampMixin, PolicyRuleMixin, Base
):
    __tablename__ = "policy_market_scopes"
    __table_args__ = _policy_rule_constraints()

    policy_version: Mapped[PolicyVersion] = relationship(
        back_populates="market_scopes"
    )


class PolicySectorPreference(
    UUIDPrimaryKeyMixin, TimestampMixin, PolicyRuleMixin, Base
):
    __tablename__ = "policy_sector_preferences"
    __table_args__ = _policy_rule_constraints()

    policy_version: Mapped[PolicyVersion] = relationship(
        back_populates="sector_preferences"
    )


class PolicyThemePreference(
    UUIDPrimaryKeyMixin, TimestampMixin, PolicyRuleMixin, Base
):
    __tablename__ = "policy_theme_preferences"
    __table_args__ = _policy_rule_constraints()

    policy_version: Mapped[PolicyVersion] = relationship(
        back_populates="theme_preferences"
    )


class PolicyMetricRule(
    UUIDPrimaryKeyMixin, TimestampMixin, PolicyRuleMixin, Base
):
    __tablename__ = "policy_metric_rules"
    __table_args__ = _policy_rule_constraints()

    policy_version: Mapped[PolicyVersion] = relationship(
        back_populates="metric_rules"
    )


class PolicyConstraint(
    UUIDPrimaryKeyMixin, TimestampMixin, PolicyRuleMixin, Base
):
    __tablename__ = "policy_constraints"
    __table_args__ = _policy_rule_constraints()

    policy_version: Mapped[PolicyVersion] = relationship(
        back_populates="constraints"
    )


class PolicyValuationRule(
    UUIDPrimaryKeyMixin, TimestampMixin, PolicyRuleMixin, Base
):
    __tablename__ = "policy_valuation_rules"
    __table_args__ = _policy_rule_constraints()

    policy_version: Mapped[PolicyVersion] = relationship(
        back_populates="valuation_rules"
    )


class PolicyPortfolioRule(
    UUIDPrimaryKeyMixin, TimestampMixin, PolicyRuleMixin, Base
):
    __tablename__ = "policy_portfolio_rules"
    __table_args__ = _policy_rule_constraints()

    policy_version: Mapped[PolicyVersion] = relationship(
        back_populates="portfolio_rules"
    )


class PolicyAlertRule(
    UUIDPrimaryKeyMixin, TimestampMixin, PolicyRuleMixin, Base
):
    __tablename__ = "policy_alert_rules"
    __table_args__ = _policy_rule_constraints()

    policy_version: Mapped[PolicyVersion] = relationship(
        back_populates="alert_rules"
    )
