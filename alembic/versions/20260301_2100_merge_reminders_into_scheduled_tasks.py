"""merge_reminders_into_scheduled_tasks

Combines the separate ``reminders`` and ``scheduled_tasks`` tables into a single
unified ``scheduled_tasks`` table.  A new ``type`` discriminator column
(``'once'`` | ``'recurring'``) identifies how the task is triggered:

* ``type='once'``      — fires once at ``fire_at``; ``enabled`` set False after firing.
* ``type='recurring'`` — fires on ``cron_expression``; updates ``last_run`` on each run.

All existing ``reminders`` rows are migrated forward as ``type='once'`` tasks.

Revision ID: merge_reminders_001
Revises: ecce9ea827b6
Create Date: 2026-03-01 21:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "merge_reminders_001"
down_revision: Union[str, None] = "ecce9ea827b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Add new columns to scheduled_tasks
    # ------------------------------------------------------------------
    op.add_column(
        "scheduled_tasks",
        sa.Column("type", sa.String(16), nullable=False, server_default="recurring"),
    )
    op.add_column(
        "scheduled_tasks",
        sa.Column("fire_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "scheduled_tasks",
        sa.Column("user_id", sa.BigInteger(), nullable=True),
    )

    # ------------------------------------------------------------------
    # 2. Make name and cron_expression nullable
    #    (ALTER COLUMN varies by dialect; use batch mode for SQLite compat)
    # ------------------------------------------------------------------
    with op.batch_alter_table("scheduled_tasks") as batch_op:
        batch_op.alter_column("name", nullable=True, existing_type=sa.String(256))
        batch_op.alter_column(
            "cron_expression", nullable=True, existing_type=sa.String(128)
        )

    # ------------------------------------------------------------------
    # 3. Remove the server_default now that existing rows have been set
    # ------------------------------------------------------------------
    with op.batch_alter_table("scheduled_tasks") as batch_op:
        batch_op.alter_column(
            "type",
            server_default=None,
            existing_type=sa.String(16),
            existing_nullable=False,
        )

    # ------------------------------------------------------------------
    # 4. Migrate reminders → scheduled_tasks (type='once')
    #    Derive a name from the first 80 chars of message.
    #    sent=True rows get enabled=False and last_run=remind_at.
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO scheduled_tasks
            (guild_id, channel_id, type, name, prompt, fire_at, user_id,
             enabled, last_run, created_by, created_at)
        SELECT
            guild_id,
            channel_id,
            'once'                          AS type,
            SUBSTR(message, 1, 80)          AS name,
            message                         AS prompt,
            remind_at                       AS fire_at,
            user_id,
            CASE WHEN sent THEN FALSE ELSE TRUE END AS enabled,
            CASE WHEN sent THEN remind_at ELSE NULL END AS last_run,
            user_id                         AS created_by,
            created_at
        FROM reminders
        """
    )

    # ------------------------------------------------------------------
    # 5. Drop the reminders table
    # ------------------------------------------------------------------
    op.drop_table("reminders")


def downgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Recreate reminders table
    # ------------------------------------------------------------------
    op.create_table(
        "reminders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("remind_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["guild_id"],
            ["guild_configs.guild_id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_reminders_guild_id"), "reminders", ["guild_id"], unique=False
    )
    op.create_index(
        op.f("ix_reminders_user_id"), "reminders", ["user_id"], unique=False
    )

    # ------------------------------------------------------------------
    # 2. Move type='once' tasks back to reminders
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO reminders
            (guild_id, channel_id, user_id, message, remind_at, sent, created_at)
        SELECT
            guild_id,
            channel_id,
            COALESCE(user_id, created_by)   AS user_id,
            prompt                          AS message,
            fire_at                         AS remind_at,
            CASE WHEN last_run IS NOT NULL THEN 1 ELSE 0 END AS sent,
            created_at
        FROM scheduled_tasks
        WHERE type = 'once'
        """
    )

    # ------------------------------------------------------------------
    # 3. Delete migrated rows from scheduled_tasks
    # ------------------------------------------------------------------
    op.execute("DELETE FROM scheduled_tasks WHERE type = 'once'")

    # ------------------------------------------------------------------
    # 4. Restore name and cron_expression as NOT NULL
    #    (at this point only recurring tasks remain; they all have values)
    # ------------------------------------------------------------------
    with op.batch_alter_table("scheduled_tasks") as batch_op:
        batch_op.alter_column(
            "name",
            nullable=False,
            existing_type=sa.String(256),
            existing_server_default=None,
        )
        batch_op.alter_column(
            "cron_expression",
            nullable=False,
            existing_type=sa.String(128),
            existing_server_default=None,
        )

    # ------------------------------------------------------------------
    # 5. Drop the new columns
    # ------------------------------------------------------------------
    with op.batch_alter_table("scheduled_tasks") as batch_op:
        batch_op.drop_column("user_id")
        batch_op.drop_column("fire_at")
        batch_op.drop_column("type")
