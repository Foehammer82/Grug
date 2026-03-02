"""Stub for is_super_admin revision applied outside version control.

Revision ID: 20260302_is_super_admin
Revises: 0003
Create Date: 2026-03-02

This stub exists solely to satisfy Alembic's revision history tracking.
The revision was generated and applied to the database in a previous session
but the file was never committed.  No schema changes are performed here.
"""

from typing import Sequence, Union

revision: str = "20260302_is_super_admin"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
