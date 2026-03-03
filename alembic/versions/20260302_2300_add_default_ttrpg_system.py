"""add_default_ttrpg_system

Adds the default_ttrpg_system column to guild_configs so guild admins can
set a server-wide default game system for rule lookups.

Revision ID: 20260302_default_ttrpg_system
Revises: 20260302_rule_sources
Create Date: 2026-03-02 23:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260302_default_ttrpg_system"
down_revision: Union[str, None] = "20260302_rule_sources"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "guild_configs",
        sa.Column("default_ttrpg_system", sa.String(128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("guild_configs", "default_ttrpg_system")
