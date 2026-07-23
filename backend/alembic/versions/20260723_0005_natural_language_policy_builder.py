"""Add review-only natural-language investment policy proposals.

Revision ID: 20260723_0005
Revises: 20260722_0004
Create Date: 2026-07-23
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260723_0005"
down_revision: str | None = "20260722_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "investment_policy_proposals",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("language_hint", sa.String(length=35), nullable=True),
        sa.Column("detected_languages", sa.JSON(), nullable=False),
        sa.Column("proposed_policy", sa.JSON(), nullable=False),
        sa.Column("issues", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("confirmed_policy_id", sa.Uuid(), nullable=True),
        sa.Column("confirmed_version_id", sa.Uuid(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["confirmed_policy_id"],
            ["investment_policies.id"],
            name="fk_policy_proposals_confirmed_policy_id_policies",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_version_id"],
            ["policy_versions.id"],
            name="fk_policy_proposals_confirmed_version_id_versions",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_investment_policy_proposals_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_investment_policy_proposals"),
    )
    op.create_index(
        "ix_investment_policy_proposals_user_id",
        "investment_policy_proposals",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_investment_policy_proposals_user_id",
        table_name="investment_policy_proposals",
    )
    op.drop_table("investment_policy_proposals")
