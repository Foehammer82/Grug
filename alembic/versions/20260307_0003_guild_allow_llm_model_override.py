"""guild_allow_llm_model_override

Adds an ``allow_llm_model_override`` boolean column to ``guild_configs``.
When False (the default) guild admins cannot change the per-campaign AI model;
a Grug super-admin must flip this flag before server admins gain that capability.

Revision ID: 20260307_0003_guild_allow_llm_model_override
Revises: 20260307_0002_campaign_llm_model
Create Date: 2026-03-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260307_0003_guild_allow_llm_model_override"
down_revision: Union[str, None] = "20260307_0002_campaign_llm_model"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "guild_configs",
        sa.Column(
            "allow_llm_model_override",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    op.drop_column("guild_configs", "allow_llm_model_override")
