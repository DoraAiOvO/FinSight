"""Create the persistent research workspace schema.

Revision ID: 20260720_0001
Revises:
Create Date: 2026-07-20
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260720_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_table(
        "customer_profiles",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("experience_level", sa.String(length=32), nullable=True),
        sa.Column("research_horizon", sa.String(length=32), nullable=True),
        sa.Column("priorities", sa.JSON(), nullable=False),
        sa.Column("risk_comfort", sa.String(length=32), nullable=True),
        sa.Column("preferred_report_depth", sa.String(length=32), nullable=True),
        sa.Column("preferred_language", sa.String(length=12), nullable=False),
        sa.Column("industries_of_interest", sa.JSON(), nullable=False),
        sa.Column("excluded_investment_types", sa.JSON(), nullable=False),
        sa.Column("presentation_preferences", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_customer_profiles_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_customer_profiles"),
        sa.UniqueConstraint("user_id", name="uq_customer_profiles_user_id"),
    )
    op.create_table(
        "watchlists",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_watchlists_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_watchlists"),
        sa.UniqueConstraint("user_id", "name", name="uq_watchlists_user_name"),
    )
    op.create_index("ix_watchlists_user_id", "watchlists", ["user_id"])
    op.create_table(
        "research_sessions",
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("language", sa.String(length=12), nullable=False),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column("result_payload", sa.JSON(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_research_sessions_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_research_sessions"),
    )
    op.create_index("ix_research_sessions_ticker", "research_sessions", ["ticker"])
    op.create_index(
        "ix_research_sessions_user_ticker", "research_sessions", ["user_id", "ticker"]
    )
    op.create_table(
        "watchlist_items",
        sa.Column("watchlist_id", sa.Uuid(), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["watchlist_id"],
            ["watchlists.id"],
            name="fk_watchlist_items_watchlist_id_watchlists",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_watchlist_items"),
        sa.UniqueConstraint(
            "watchlist_id", "ticker", name="uq_watchlist_items_watchlist_ticker"
        ),
    )
    op.create_index("ix_watchlist_items_ticker", "watchlist_items", ["ticker"])
    op.create_index(
        "ix_watchlist_items_watchlist_id", "watchlist_items", ["watchlist_id"]
    )
    op.create_table(
        "saved_reports",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("research_session_id", sa.Uuid(), nullable=True),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("report_type", sa.String(length=32), nullable=False),
        sa.Column("language", sa.String(length=12), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["research_session_id"],
            ["research_sessions.id"],
            name="fk_saved_reports_research_session_id_research_sessions",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_saved_reports_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_saved_reports"),
    )
    op.create_index("ix_saved_reports_ticker", "saved_reports", ["ticker"])
    op.create_index(
        "ix_saved_reports_user_ticker", "saved_reports", ["user_id", "ticker"]
    )
    op.create_table(
        "theses",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("research_session_id", sa.Uuid(), nullable=True),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name=op.f("ck_theses_confidence_range"),
        ),
        sa.ForeignKeyConstraint(
            ["research_session_id"],
            ["research_sessions.id"],
            name="fk_theses_research_session_id_research_sessions",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_theses_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_theses"),
    )
    op.create_index("ix_theses_ticker", "theses", ["ticker"])
    op.create_index("ix_theses_user_ticker", "theses", ["user_id", "ticker"])
    op.create_table(
        "thesis_assumptions",
        sa.Column("thesis_id", sa.Uuid(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("condition_type", sa.String(length=32), nullable=True),
        sa.Column("metric_key", sa.String(length=120), nullable=True),
        sa.Column("operator", sa.String(length=24), nullable=True),
        sa.Column("target_value", sa.String(length=120), nullable=True),
        sa.Column("current_status", sa.String(length=32), nullable=False),
        sa.Column("supporting_evidence", sa.JSON(), nullable=False),
        sa.Column("contradicting_evidence", sa.JSON(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("last_evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["thesis_id"], ["theses.id"], name="fk_thesis_assumptions_thesis_id_theses", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_thesis_assumptions"),
    )
    op.create_index(
        "ix_thesis_assumptions_thesis_id", "thesis_assumptions", ["thesis_id"]
    )
    op.create_table(
        "feedback",
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("research_session_id", sa.Uuid(), nullable=True),
        sa.Column("saved_report_id", sa.Uuid(), nullable=True),
        sa.Column("section_key", sa.String(length=120), nullable=True),
        sa.Column("feedback_type", sa.String(length=32), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "rating IS NULL OR (rating >= 1 AND rating <= 5)",
            name=op.f("ck_feedback_rating_range"),
        ),
        sa.ForeignKeyConstraint(
            ["research_session_id"],
            ["research_sessions.id"],
            name="fk_feedback_research_session_id_research_sessions",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["saved_report_id"],
            ["saved_reports.id"],
            name="fk_feedback_saved_report_id_saved_reports",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_feedback_user_id_users", ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_feedback"),
    )
    op.create_index("ix_feedback_user_id", "feedback", ["user_id"])
    op.create_table(
        "alert_preferences",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=True),
        sa.Column("alert_type", sa.String(length=64), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("frequency", sa.String(length=32), nullable=False),
        sa.Column("conditions", sa.JSON(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_alert_preferences_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_alert_preferences"),
        sa.UniqueConstraint(
            "user_id", "ticker", "alert_type", "channel", name="uq_alert_preferences_scope"
        ),
    )
    op.create_index("ix_alert_preferences_ticker", "alert_preferences", ["ticker"])
    op.create_index("ix_alert_preferences_user_id", "alert_preferences", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_alert_preferences_user_id", table_name="alert_preferences")
    op.drop_index("ix_alert_preferences_ticker", table_name="alert_preferences")
    op.drop_table("alert_preferences")
    op.drop_index("ix_feedback_user_id", table_name="feedback")
    op.drop_table("feedback")
    op.drop_index("ix_thesis_assumptions_thesis_id", table_name="thesis_assumptions")
    op.drop_table("thesis_assumptions")
    op.drop_index("ix_theses_user_ticker", table_name="theses")
    op.drop_index("ix_theses_ticker", table_name="theses")
    op.drop_table("theses")
    op.drop_index("ix_saved_reports_user_ticker", table_name="saved_reports")
    op.drop_index("ix_saved_reports_ticker", table_name="saved_reports")
    op.drop_table("saved_reports")
    op.drop_index("ix_watchlist_items_watchlist_id", table_name="watchlist_items")
    op.drop_index("ix_watchlist_items_ticker", table_name="watchlist_items")
    op.drop_table("watchlist_items")
    op.drop_index("ix_research_sessions_user_ticker", table_name="research_sessions")
    op.drop_index("ix_research_sessions_ticker", table_name="research_sessions")
    op.drop_table("research_sessions")
    op.drop_index("ix_watchlists_user_id", table_name="watchlists")
    op.drop_table("watchlists")
    op.drop_table("customer_profiles")
    op.drop_table("users")
