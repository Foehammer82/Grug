"""Add combat tracker depth to campaigns, HP/conditions/death saves to combatants, combat_log_entries table.

Revision ID: 20260304_0008_combat_depth
Revises: 20260304_0007_encounters
Create Date: 2026-03-04
"""

from alembic import op
import sqlalchemy as sa

revision: str = "20260304_0008_combat_depth"
down_revision: str | None = "20260304_0007_encounters"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- Campaign: combat_tracker_depth ---------------------------------
    op.add_column(
        "campaigns",
        sa.Column(
            "combat_tracker_depth",
            sa.String(16),
            nullable=False,
            server_default="standard",
        ),
    )

    # -- Combatant: HP, AC, conditions, saves, death saves, concentration --
    op.add_column("combatants", sa.Column("max_hp", sa.Integer(), nullable=True))
    op.add_column("combatants", sa.Column("current_hp", sa.Integer(), nullable=True))
    op.add_column(
        "combatants",
        sa.Column("temp_hp", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("combatants", sa.Column("armor_class", sa.Integer(), nullable=True))
    op.add_column("combatants", sa.Column("conditions", sa.JSON(), nullable=True))
    op.add_column("combatants", sa.Column("save_modifiers", sa.JSON(), nullable=True))
    op.add_column(
        "combatants",
        sa.Column(
            "death_save_successes", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    op.add_column(
        "combatants",
        sa.Column(
            "death_save_failures", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    op.add_column(
        "combatants",
        sa.Column("concentration_spell", sa.String(256), nullable=True),
    )

    # -- CombatLogEntry table -------------------------------------------
    op.create_table(
        "combat_log_entries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "encounter_id",
            sa.Integer(),
            sa.ForeignKey("encounters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "combatant_id",
            sa.Integer(),
            sa.ForeignKey("combatants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_combat_log_entries_encounter_id",
        "combat_log_entries",
        ["encounter_id"],
    )
    op.create_index(
        "ix_combat_log_entries_combatant_id",
        "combat_log_entries",
        ["combatant_id"],
    )


def downgrade() -> None:
    op.drop_table("combat_log_entries")

    op.drop_column("combatants", "concentration_spell")
    op.drop_column("combatants", "death_save_failures")
    op.drop_column("combatants", "death_save_successes")
    op.drop_column("combatants", "save_modifiers")
    op.drop_column("combatants", "conditions")
    op.drop_column("combatants", "armor_class")
    op.drop_column("combatants", "temp_hp")
    op.drop_column("combatants", "current_hp")
    op.drop_column("combatants", "max_hp")

    op.drop_column("campaigns", "combat_tracker_depth")
