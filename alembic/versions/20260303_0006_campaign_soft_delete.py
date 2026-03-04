"""Add deleted_at column to campaigns for soft-delete support.

Revision ID: 20260303_0006_campaign_soft_delete
Revises: 20260303_0005_llm_usage_records
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260303_0006_campaign_soft_delete"
down_revision: str | None = "20260303_0005_llm_usage_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "campaigns",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("campaigns", "deleted_at")
