"""Add scheduled_task_runs table for execution history.

Revision ID: 20260307_0005_scheduled_task_runs
Revises: 20260307_0004_document_visibility_and_file_path
Create Date: 2026-03-07
"""

from alembic import op
import sqlalchemy as sa

revision: str = "20260307_0005_scheduled_task_runs"
down_revision: str | None = "20260307_0004_document_visibility_and_file_path"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scheduled_task_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "ran_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "triggered_by",
            sa.String(length=16),
            nullable=False,
            server_default="scheduled",
        ),
        sa.Column("response", sa.Text(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default="true"),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["scheduled_tasks.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_scheduled_task_runs_task_id"),
        "scheduled_task_runs",
        ["task_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scheduled_task_runs_guild_id"),
        "scheduled_task_runs",
        ["guild_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_scheduled_task_runs_guild_id"), table_name="scheduled_task_runs"
    )
    op.drop_index(
        op.f("ix_scheduled_task_runs_task_id"), table_name="scheduled_task_runs"
    )
    op.drop_table("scheduled_task_runs")
