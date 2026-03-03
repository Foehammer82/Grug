"""add_guild_tool_configs

Revision ID: 90d192104884
Revises: 20260302_is_super_admin
Create Date: 2026-03-02 19:41:06.907184
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "90d192104884"
down_revision: Union[str, None] = "20260302_is_super_admin"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "guild_tool_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("tool_id", sa.String(length=128), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["guild_id"], ["guild_configs.guild_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("guild_id", "tool_id", name="uq_guild_tool"),
    )
    op.create_index(
        op.f("ix_guild_tool_configs_guild_id"),
        "guild_tool_configs",
        ["guild_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_guild_tool_configs_guild_id"), table_name="guild_tool_configs"
    )
    op.drop_table("guild_tool_configs")
