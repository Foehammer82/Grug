"""campaign_llm_model

Adds a per-campaign ``llm_model`` column so GMs can opt-in to a smarter
(but more expensive) Anthropic model for their campaign channel.
NULL = use the server default (typically claude-haiku-4-5).

Revision ID: 20260307_0002_campaign_llm_model
Revises: 20260307_0001_scheduled_task_timezone
Create Date: 2026-03-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260307_0002_campaign_llm_model"
down_revision: Union[str, None] = "20260307_0001_scheduled_task_timezone"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "campaigns",
        sa.Column(
            "llm_model",
            sa.String(length=128),
            nullable=True,
            server_default=None,
        ),
    )


def downgrade() -> None:
    op.drop_column("campaigns", "llm_model")
