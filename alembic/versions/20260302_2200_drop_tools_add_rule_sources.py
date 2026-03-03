"""drop_tools_add_rule_sources

Drops the guild_tool_configs table (tool registry concept removed) and
creates rule_sources + guild_builtin_overrides for the TTRPG rules lookup
feature.

Revision ID: 20260302_rule_sources
Revises: 90d192104884
Create Date: 2026-03-02 22:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260302_rule_sources"
down_revision: Union[str, None] = "90d192104884"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Drop guild_tool_configs ──────────────────────────────────────────
    op.drop_index(
        op.f("ix_guild_tool_configs_guild_id"), table_name="guild_tool_configs"
    )
    op.drop_table("guild_tool_configs")

    # ── Create rule_sources ──────────────────────────────────────────────
    op.create_table(
        "rule_sources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("system", sa.String(length=128), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["guild_id"],
            ["guild_configs.guild_id"],
            name="fk_rule_sources_guild_id",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rule_sources_guild_id", "rule_sources", ["guild_id"])

    # ── Create guild_builtin_overrides ───────────────────────────────────
    op.create_table(
        "guild_builtin_overrides",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("source_id", sa.String(length=128), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["guild_id"],
            ["guild_configs.guild_id"],
            name="fk_guild_builtin_overrides_guild_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("guild_id", "source_id", name="uq_guild_builtin_source"),
    )
    op.create_index(
        "ix_guild_builtin_overrides_guild_id",
        "guild_builtin_overrides",
        ["guild_id"],
    )


def downgrade() -> None:
    # ── Drop rule sources tables ─────────────────────────────────────────
    op.drop_index(
        "ix_guild_builtin_overrides_guild_id", table_name="guild_builtin_overrides"
    )
    op.drop_table("guild_builtin_overrides")
    op.drop_index("ix_rule_sources_guild_id", table_name="rule_sources")
    op.drop_table("rule_sources")

    # ── Restore guild_tool_configs ───────────────────────────────────────
    op.create_table(
        "guild_tool_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("tool_id", sa.String(length=128), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["guild_id"],
            ["guild_configs.guild_id"],
            name="fk_guild_tool_configs_guild_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("guild_id", "tool_id", name="uq_guild_tool"),
    )
    op.create_index(
        op.f("ix_guild_tool_configs_guild_id"),
        "guild_tool_configs",
        ["guild_id"],
    )
