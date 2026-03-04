"""Add dice_rolls table for persistent dice roll history.

Revision ID: 20260304_0006_dice_rolls
Revises: 4cf8295d8b3e
Create Date: 2026-03-04
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260304_0006_dice_rolls"
down_revision: str | None = "4cf8295d8b3e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dice_rolls",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "campaign_id", sa.Integer(), sa.ForeignKey("campaigns.id"), nullable=True
        ),
        sa.Column("roller_discord_user_id", sa.BigInteger(), nullable=False),
        sa.Column("roller_display_name", sa.String(256), nullable=False),
        sa.Column("character_name", sa.String(256), nullable=True),
        sa.Column("expression", sa.String(256), nullable=False),
        sa.Column("individual_rolls", sa.JSON(), nullable=False),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column(
            "roll_type",
            sa.String(32),
            nullable=False,
            server_default="general",
        ),
        sa.Column(
            "is_private",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column("context_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dice_rolls_guild_id", "dice_rolls", ["guild_id"])
    op.create_index("ix_dice_rolls_campaign_id", "dice_rolls", ["campaign_id"])
    op.create_index(
        "ix_dice_rolls_roller_discord_user_id",
        "dice_rolls",
        ["roller_discord_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_dice_rolls_roller_discord_user_id", table_name="dice_rolls")
    op.drop_index("ix_dice_rolls_campaign_id", table_name="dice_rolls")
    op.drop_index("ix_dice_rolls_guild_id", table_name="dice_rolls")
    op.drop_table("dice_rolls")
