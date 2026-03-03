"""Add calendar_token to guild_configs for iCal feed authentication.

Revision ID: 20260303_calendar_token
Revises: 20260303_events_features
Create Date: 2026-03-03
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260303_calendar_token"
down_revision: Union[str, None] = "20260303_events_features"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "guild_configs",
        sa.Column("calendar_token", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("guild_configs", "calendar_token")
