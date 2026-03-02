"""drop_guild_config_prefix

Revision ID: ecce9ea827b6
Revises: 0003
Create Date: 2026-03-01 20:40:54.003362
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "ecce9ea827b6"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("guild_configs", "prefix")


def downgrade() -> None:
    op.add_column(
        "guild_configs",
        sa.Column("prefix", sa.String(10), server_default="!", nullable=False),
    )
