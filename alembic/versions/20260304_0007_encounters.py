"""Add encounters and combatants tables for initiative tracking.

Revision ID: 20260304_0007_encounters
Revises: 20260304_0006_dice_rolls
Create Date: 2026-03-04
"""

from alembic import op
import sqlalchemy as sa

revision: str = "20260304_0007_encounters"
down_revision: str | None = "20260304_0006_dice_rolls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "encounters",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "campaign_id",
            sa.Integer(),
            sa.ForeignKey("campaigns.id"),
            nullable=False,
        ),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="preparing",
        ),
        sa.Column(
            "current_turn_index",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "round_number",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column("channel_id", sa.BigInteger(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_encounters_campaign_id", "encounters", ["campaign_id"])
    op.create_index("ix_encounters_guild_id", "encounters", ["guild_id"])

    op.create_table(
        "combatants",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "encounter_id",
            sa.Integer(),
            sa.ForeignKey("encounters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "character_id",
            sa.Integer(),
            sa.ForeignKey("characters.id"),
            nullable=True,
        ),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("initiative_roll", sa.Integer(), nullable=True),
        sa.Column(
            "initiative_modifier",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "is_enemy",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_combatants_encounter_id", "combatants", ["encounter_id"])
    op.create_index("ix_combatants_character_id", "combatants", ["character_id"])


def downgrade() -> None:
    op.drop_index("ix_combatants_character_id", table_name="combatants")
    op.drop_index("ix_combatants_encounter_id", table_name="combatants")
    op.drop_table("combatants")
    op.drop_index("ix_encounters_guild_id", table_name="encounters")
    op.drop_index("ix_encounters_campaign_id", table_name="encounters")
    op.drop_table("encounters")
