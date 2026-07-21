"""Add event conditions and append-only assumption history.

Revision ID: 20260721_0003
Revises: 20260720_0002
Create Date: 2026-07-21
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260721_0003"
down_revision: str | None = "20260720_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "thesis_assumptions",
        sa.Column("event_condition", sa.Text(), nullable=True),
    )
    op.create_table(
        "thesis_assumption_history",
        sa.Column("assumption_id", sa.Uuid(), nullable=False),
        sa.Column("change_type", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("previous_values", sa.JSON(), nullable=True),
        sa.Column("current_values", sa.JSON(), nullable=False),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["assumption_id"],
            ["thesis_assumptions.id"],
            name="fk_thesis_assumption_history_assumption_id_thesis_assumptions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_thesis_assumption_history"),
    )
    op.create_index(
        "ix_thesis_assumption_history_assumption_id",
        "thesis_assumption_history",
        ["assumption_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_thesis_assumption_history_assumption_id",
        table_name="thesis_assumption_history",
    )
    op.drop_table("thesis_assumption_history")
    op.drop_column("thesis_assumptions", "event_condition")
