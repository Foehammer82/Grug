"""Fix timestamp columns to TIMESTAMP WITH TIME ZONE.

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-01

Migration 0002 created campaigns, characters, user_profiles, glossary_terms,
and glossary_term_history with TIMESTAMP WITHOUT TIME ZONE columns.  The ORM
models store timezone-aware UTC datetimes, causing asyncpg to reject the
insert.  This migration converts all affected columns to TIMESTAMPTZ.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (table, column) pairs to convert from TIMESTAMP -> TIMESTAMPTZ
_COLUMNS: list[tuple[str, str]] = [
    ("campaigns", "created_at"),
    ("characters", "created_at"),
    ("characters", "updated_at"),
    ("glossary_term_history", "changed_at"),
    ("glossary_terms", "created_at"),
    ("glossary_terms", "updated_at"),
    ("user_profiles", "created_at"),
]


def upgrade() -> None:
    for table, column in _COLUMNS:
        op.execute(
            sa.text(
                f"ALTER TABLE {table} ALTER COLUMN {column} "
                f"TYPE TIMESTAMP WITH TIME ZONE "
                f"USING {column} AT TIME ZONE 'UTC'"
            )
        )


def downgrade() -> None:
    for table, column in reversed(_COLUMNS):
        op.execute(
            sa.text(
                f"ALTER TABLE {table} ALTER COLUMN {column} "
                f"TYPE TIMESTAMP WITHOUT TIME ZONE "
                f"USING {column} AT TIME ZONE 'UTC'"
            )
        )
