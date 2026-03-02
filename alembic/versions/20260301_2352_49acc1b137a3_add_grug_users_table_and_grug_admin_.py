"""add_grug_users_table_and_grug_admin_role_id

Revision ID: 49acc1b137a3
Revises: 20260301_channel_ctx
Create Date: 2026-03-01 23:52:17.359090
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "49acc1b137a3"
down_revision: Union[str, None] = "20260301_channel_ctx"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. New grug_users table — tracks per-user privileges (can_invite, etc.)
    op.create_table(
        "grug_users",
        sa.Column(
            "discord_user_id", sa.BigInteger(), autoincrement=False, nullable=False
        ),
        sa.Column("can_invite", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("discord_user_id"),
    )

    # 2. Store the auto-created grug-admin Discord role ID per guild.
    op.add_column(
        "guild_configs",
        sa.Column("grug_admin_role_id", sa.BigInteger(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("guild_configs", "grug_admin_role_id")
    op.drop_table("grug_users")
