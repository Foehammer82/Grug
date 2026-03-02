"""add_is_super_admin_to_grug_users

Revision ID: 20260302_is_super_admin
Revises: 49acc1b137a3
Create Date: 2026-03-02
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260302_is_super_admin"
down_revision: Union[str, None] = "49acc1b137a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "grug_users",
        sa.Column(
            "is_super_admin",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("grug_users", "is_super_admin")
