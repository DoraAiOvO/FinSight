"""Add advanced, versioned investment policies.

Revision ID: 20260722_0004
Revises: 20260721_0003
Create Date: 2026-07-22
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260722_0004"
down_revision: str | None = "20260721_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


RULE_TABLES = (
    "policy_principles",
    "policy_market_scopes",
    "policy_sector_preferences",
    "policy_theme_preferences",
    "policy_metric_rules",
    "policy_constraints",
    "policy_valuation_rules",
    "policy_portfolio_rules",
    "policy_alert_rules",
)


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


def create_rule_table(table_name: str) -> None:
    op.create_table(
        table_name,
        sa.Column("policy_version_id", sa.Uuid(), nullable=False),
        sa.Column("rule_type", sa.String(length=120), nullable=False),
        sa.Column("operator", sa.String(length=32), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("importance", sa.Integer(), nullable=False),
        sa.Column("hard_or_soft", sa.String(length=16), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("application_effect", sa.String(length=32), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "importance >= 1 AND importance <= 5",
            name=op.f(f"ck_{table_name}_importance_range"),
        ),
        sa.CheckConstraint(
            "hard_or_soft IN ('hard', 'soft')",
            name=op.f(f"ck_{table_name}_hard_or_soft_values"),
        ),
        sa.CheckConstraint(
            "application_effect IN "
            "('filtering', 'ranking', 'report_emphasis', 'alerts', "
            "'preference_fit_scoring')",
            name=op.f(f"ck_{table_name}_safe_application_effects"),
        ),
        sa.ForeignKeyConstraint(
            ["policy_version_id"],
            ["policy_versions.id"],
            name=f"fk_{table_name}_policy_version_id_policy_versions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=f"pk_{table_name}"),
    )
    op.create_index(
        f"ix_{table_name}_policy_version_id",
        table_name,
        ["policy_version_id"],
    )


def upgrade() -> None:
    op.create_table(
        "investment_policies",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_investment_policies_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_investment_policies"),
        sa.UniqueConstraint(
            "user_id", "name", name="uq_investment_policies_user_name"
        ),
    )
    op.create_index(
        "ix_investment_policies_user_id", "investment_policies", ["user_id"]
    )
    op.create_table(
        "policy_versions",
        sa.Column("investment_policy_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("change_summary", sa.Text(), nullable=True),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "version_number > 0",
            name=op.f("ck_policy_versions_positive_version_number"),
        ),
        sa.ForeignKeyConstraint(
            ["investment_policy_id"],
            ["investment_policies.id"],
            name="fk_policy_versions_investment_policy_id_investment_policies",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_policy_versions"),
        sa.UniqueConstraint(
            "investment_policy_id",
            "version_number",
            name="uq_policy_versions_policy_number",
        ),
    )
    op.create_index(
        "ix_policy_versions_investment_policy_id",
        "policy_versions",
        ["investment_policy_id"],
    )
    for table_name in RULE_TABLES:
        create_rule_table(table_name)


def downgrade() -> None:
    for table_name in reversed(RULE_TABLES):
        op.drop_index(
            f"ix_{table_name}_policy_version_id", table_name=table_name
        )
        op.drop_table(table_name)
    op.drop_index(
        "ix_policy_versions_investment_policy_id", table_name="policy_versions"
    )
    op.drop_table("policy_versions")
    op.drop_index(
        "ix_investment_policies_user_id", table_name="investment_policies"
    )
    op.drop_table("investment_policies")
