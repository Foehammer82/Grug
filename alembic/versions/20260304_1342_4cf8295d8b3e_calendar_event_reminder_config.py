"""calendar_event_reminder_config

Revision ID: 4cf8295d8b3e
Revises: 20260304_0005_campaign_scheduling
Create Date: 2026-03-04 13:42:26.119216
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4cf8295d8b3e'
down_revision: Union[str, None] = '20260304_0005_campaign_scheduling'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('calendar_events', sa.Column('reminder_days', sa.JSON(), nullable=True))
    op.add_column('calendar_events', sa.Column('reminder_time', sa.String(length=8), nullable=True))
    op.add_column('calendar_events', sa.Column('poll_advance_days', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('calendar_events', 'poll_advance_days')
    op.drop_column('calendar_events', 'reminder_time')
    op.drop_column('calendar_events', 'reminder_days')
