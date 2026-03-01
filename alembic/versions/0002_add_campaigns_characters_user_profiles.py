"""Add campaigns, characters, user_profiles, glossary_terms, glossary_term_history.

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-01

Five tables present in grug/db/models.py were omitted from the initial
migration, causing UndefinedTableError at runtime.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "campaigns",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("system", sa.String(128), nullable=False, server_default="unknown"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel_id"),
    )
    op.create_index("ix_campaigns_guild_id", "campaigns", ["guild_id"])
    op.create_index("ix_campaigns_channel_id", "campaigns", ["channel_id"])

    op.create_table(
        "characters",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_discord_user_id", sa.BigInteger(), nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("system", sa.String(128), nullable=False, server_default="unknown"),
        sa.Column("raw_sheet_text", sa.Text(), nullable=True),
        sa.Column("structured_data", sa.JSON(), nullable=True),
        sa.Column("file_path", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_characters_owner_discord_user_id", "characters", ["owner_discord_user_id"]
    )
    op.create_index("ix_characters_campaign_id", "characters", ["campaign_id"])

    op.create_table(
        "user_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("discord_user_id", sa.BigInteger(), nullable=False),
        sa.Column("active_character_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["active_character_id"],
            ["characters.id"],
            name="fk_user_active_character",
            use_alter=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("discord_user_id"),
    )
    op.create_index(
        "ix_user_profiles_discord_user_id", "user_profiles", ["discord_user_id"]
    )

    # Add campaign_id to documents (was added via SQLite incremental DDL but
    # was never in the Postgres migration).
    op.add_column(
        "documents",
        sa.Column("campaign_id", sa.Integer(), nullable=True),
    )

    op.create_table(
        "glossary_terms",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=True),
        sa.Column("term", sa.String(256), nullable=False),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column(
            "ai_generated", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "originally_ai_generated",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["guild_id"], ["guild_configs.guild_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_glossary_terms_guild_id", "glossary_terms", ["guild_id"])
    op.create_index("ix_glossary_terms_channel_id", "glossary_terms", ["channel_id"])

    op.create_table(
        "glossary_term_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("term_id", sa.Integer(), nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("old_term", sa.String(256), nullable=False),
        sa.Column("old_definition", sa.Text(), nullable=False),
        sa.Column("old_ai_generated", sa.Boolean(), nullable=False),
        sa.Column("changed_by", sa.BigInteger(), nullable=False),
        sa.Column("changed_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["term_id"], ["glossary_terms.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_glossary_term_history_term_id", "glossary_term_history", ["term_id"]
    )
    op.create_index(
        "ix_glossary_term_history_guild_id", "glossary_term_history", ["guild_id"]
    )


def downgrade() -> None:
    op.drop_table("glossary_term_history")
    op.drop_table("glossary_terms")
    op.drop_column("documents", "campaign_id")
    op.drop_table("user_profiles")
    op.drop_table("characters")
    op.drop_table("campaigns")
