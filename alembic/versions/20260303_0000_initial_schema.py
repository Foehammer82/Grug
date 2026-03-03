"""Initial schema — full baseline after squashing all prior migrations.

Revision ID: 20260303_0000_initial_schema
Revises:
Create Date: 2026-03-03 00:00:00

NOTE: Vector columns (embedding) are added via raw ALTER TABLE after each
vector table is created, because SQLAlchemy's Alembic autogenerate does not
support the pgvector Vector() type natively.

IVFFlat indexes are intentionally omitted from this baseline — they require
the table to have data first (for list quantisation to be meaningful).  Add
them via a separate migration once the embedding tables are populated.
"""

import sqlalchemy as sa
from alembic import op

revision = "20260303_0000_initial_schema"
down_revision = None
branch_labels = None
depends_on = None

EMBEDDING_DIM = 384  # all-MiniLM-L6-v2


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # pgvector extension                                                   #
    # ------------------------------------------------------------------ #
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ------------------------------------------------------------------ #
    # guild_configs                                                        #
    # ------------------------------------------------------------------ #
    op.create_table(
        "guild_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("announce_channel_id", sa.BigInteger(), nullable=True),
        sa.Column("grug_admin_role_id", sa.BigInteger(), nullable=True),
        sa.Column("context_cutoff", sa.DateTime(timezone=True), nullable=True),
        sa.Column("calendar_token", sa.String(64), nullable=True),
        sa.Column("default_ttrpg_system", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_guild_configs_guild_id", "guild_configs", ["guild_id"], unique=True
    )

    # ------------------------------------------------------------------ #
    # campaigns                                                            #
    # ------------------------------------------------------------------ #
    op.create_table(
        "campaigns",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("system", sa.String(128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_campaigns_guild_id", "campaigns", ["guild_id"])
    op.create_index("ix_campaigns_channel_id", "campaigns", ["channel_id"], unique=True)

    # ------------------------------------------------------------------ #
    # characters                                                           #
    # ------------------------------------------------------------------ #
    op.create_table(
        "characters",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_discord_user_id", sa.BigInteger(), nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("system", sa.String(128), nullable=False),
        sa.Column("raw_sheet_text", sa.Text(), nullable=True),
        sa.Column("structured_data", sa.JSON(), nullable=True),
        sa.Column("file_path", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_characters_owner_discord_user_id", "characters", ["owner_discord_user_id"]
    )
    op.create_index("ix_characters_campaign_id", "characters", ["campaign_id"])

    # ------------------------------------------------------------------ #
    # user_profiles                                                        #
    # ------------------------------------------------------------------ #
    op.create_table(
        "user_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("discord_user_id", sa.BigInteger(), nullable=False),
        sa.Column("active_character_id", sa.Integer(), nullable=True),
        sa.Column("dm_context_cutoff", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["active_character_id"],
            ["characters.id"],
            name="fk_user_active_character",
            use_alter=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_user_profiles_discord_user_id",
        "user_profiles",
        ["discord_user_id"],
        unique=True,
    )

    # ------------------------------------------------------------------ #
    # documents                                                            #
    # ------------------------------------------------------------------ #
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("chroma_collection", sa.String(256), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("uploaded_by", sa.BigInteger(), nullable=False),
        sa.Column("campaign_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documents_guild_id", "documents", ["guild_id"])
    op.create_index("ix_documents_campaign_id", "documents", ["campaign_id"])

    # ------------------------------------------------------------------ #
    # channel_configs                                                      #
    # ------------------------------------------------------------------ #
    op.create_table(
        "channel_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "always_respond", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column("context_cutoff", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["guild_id"], ["guild_configs.guild_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_channel_configs_guild_id", "channel_configs", ["guild_id"])
    op.create_index(
        "ix_channel_configs_channel_id", "channel_configs", ["channel_id"], unique=True
    )

    # ------------------------------------------------------------------ #
    # calendar_events                                                      #
    # ------------------------------------------------------------------ #
    op.create_table(
        "calendar_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rrule", sa.String(512), nullable=True),
        sa.Column("location", sa.String(256), nullable=True),
        sa.Column("channel_id", sa.BigInteger(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["guild_id"], ["guild_configs.guild_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_calendar_events_guild_id", "calendar_events", ["guild_id"])

    # ------------------------------------------------------------------ #
    # event_rsvps                                                          #
    # ------------------------------------------------------------------ #
    op.create_table(
        "event_rsvps",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("discord_user_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id"], ["calendar_events.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id", "discord_user_id", name="uq_event_rsvp"),
    )
    op.create_index("ix_event_rsvps_event_id", "event_rsvps", ["event_id"])

    # ------------------------------------------------------------------ #
    # event_notes                                                          #
    # ------------------------------------------------------------------ #
    op.create_table(
        "event_notes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("done", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id"], ["calendar_events.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_event_notes_event_id", "event_notes", ["event_id"])

    # ------------------------------------------------------------------ #
    # event_occurrence_overrides                                           #
    # ------------------------------------------------------------------ #
    op.create_table(
        "event_occurrence_overrides",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("original_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("new_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("new_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id"], ["calendar_events.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "event_id", "original_start", name="uq_event_occurrence_override"
        ),
    )
    op.create_index(
        "ix_event_occurrence_overrides_event_id",
        "event_occurrence_overrides",
        ["event_id"],
    )

    # ------------------------------------------------------------------ #
    # availability_polls                                                   #
    # ------------------------------------------------------------------ #
    op.create_table(
        "availability_polls",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("closes_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("winner_option_id", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["guild_id"], ["guild_configs.guild_id"]),
        sa.ForeignKeyConstraint(
            ["event_id"], ["calendar_events.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_availability_polls_guild_id", "availability_polls", ["guild_id"]
    )
    op.create_index(
        "ix_availability_polls_event_id", "availability_polls", ["event_id"]
    )

    # ------------------------------------------------------------------ #
    # poll_votes                                                           #
    # ------------------------------------------------------------------ #
    op.create_table(
        "poll_votes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("poll_id", sa.Integer(), nullable=False),
        sa.Column("discord_user_id", sa.BigInteger(), nullable=False),
        sa.Column("option_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["poll_id"], ["availability_polls.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("poll_id", "discord_user_id", name="uq_poll_vote"),
    )
    op.create_index("ix_poll_votes_poll_id", "poll_votes", ["poll_id"])

    # ------------------------------------------------------------------ #
    # scheduled_tasks                                                      #
    # ------------------------------------------------------------------ #
    op.create_table(
        "scheduled_tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("name", sa.String(256), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("fire_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cron_expression", sa.String(128), nullable=True),
        sa.Column("source", sa.String(16), nullable=False, server_default="discord"),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("last_run", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["guild_id"], ["guild_configs.guild_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scheduled_tasks_guild_id", "scheduled_tasks", ["guild_id"])

    # ------------------------------------------------------------------ #
    # conversation_messages                                                #
    # ------------------------------------------------------------------ #
    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("author_id", sa.BigInteger(), nullable=True),
        sa.Column("author_name", sa.String(256), nullable=True),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_passive", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_conversation_messages_guild_id", "conversation_messages", ["guild_id"]
    )
    op.create_index(
        "ix_conversation_messages_channel_id", "conversation_messages", ["channel_id"]
    )

    # ------------------------------------------------------------------ #
    # grug_users                                                           #
    # ------------------------------------------------------------------ #
    op.create_table(
        "grug_users",
        sa.Column(
            "discord_user_id", sa.BigInteger(), autoincrement=False, nullable=False
        ),
        sa.Column("can_invite", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "is_super_admin", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("discord_user_id"),
    )

    # ------------------------------------------------------------------ #
    # glossary_terms                                                       #
    # ------------------------------------------------------------------ #
    op.create_table(
        "glossary_terms",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=True),
        sa.Column("term", sa.String(256), nullable=False),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column("ai_generated", sa.Boolean(), nullable=False),
        sa.Column("originally_ai_generated", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["guild_id"], ["guild_configs.guild_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_glossary_terms_guild_id", "glossary_terms", ["guild_id"])
    op.create_index("ix_glossary_terms_channel_id", "glossary_terms", ["channel_id"])

    # ------------------------------------------------------------------ #
    # glossary_term_history                                                #
    # ------------------------------------------------------------------ #
    op.create_table(
        "glossary_term_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("term_id", sa.Integer(), nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("old_term", sa.String(256), nullable=False),
        sa.Column("old_definition", sa.Text(), nullable=False),
        sa.Column("old_ai_generated", sa.Boolean(), nullable=False),
        sa.Column("changed_by", sa.BigInteger(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["term_id"], ["glossary_terms.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_glossary_term_history_term_id", "glossary_term_history", ["term_id"]
    )
    op.create_index(
        "ix_glossary_term_history_guild_id", "glossary_term_history", ["guild_id"]
    )

    # ------------------------------------------------------------------ #
    # rule_sources                                                         #
    # ------------------------------------------------------------------ #
    op.create_table(
        "rule_sources",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("system", sa.String(128), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["guild_id"], ["guild_configs.guild_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rule_sources_guild_id", "rule_sources", ["guild_id"])

    # ------------------------------------------------------------------ #
    # guild_builtin_overrides                                              #
    # ------------------------------------------------------------------ #
    op.create_table(
        "guild_builtin_overrides",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("source_id", sa.String(128), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["guild_id"], ["guild_configs.guild_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("guild_id", "source_id", name="uq_guild_builtin_source"),
    )
    op.create_index(
        "ix_guild_builtin_overrides_guild_id", "guild_builtin_overrides", ["guild_id"]
    )

    # ------------------------------------------------------------------ #
    # document_chunk_embeddings (pgvector)                                 #
    # ------------------------------------------------------------------ #
    op.create_table(
        "document_chunk_embeddings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("chunk_id", sa.String(36), nullable=False),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("total_chunks", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chunk_id"),
    )
    op.execute(
        f"ALTER TABLE document_chunk_embeddings ADD COLUMN embedding vector({EMBEDDING_DIM}) NOT NULL"
    )
    op.create_index(
        "ix_document_chunk_embeddings_guild_id",
        "document_chunk_embeddings",
        ["guild_id"],
    )
    op.create_index(
        "ix_document_chunk_embeddings_document_id",
        "document_chunk_embeddings",
        ["document_id"],
    )

    # ------------------------------------------------------------------ #
    # conversation_history_embeddings (pgvector)                           #
    # ------------------------------------------------------------------ #
    op.create_table(
        "conversation_history_embeddings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("summary_id", sa.String(36), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.String(64), nullable=False),
        sa.Column("end_time", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("summary_id"),
    )
    op.execute(
        f"ALTER TABLE conversation_history_embeddings ADD COLUMN embedding vector({EMBEDDING_DIM}) NOT NULL"
    )
    op.create_index(
        "ix_conversation_history_embeddings_guild_id",
        "conversation_history_embeddings",
        ["guild_id"],
    )
    op.create_index(
        "ix_conversation_history_embeddings_channel_id",
        "conversation_history_embeddings",
        ["channel_id"],
    )


def downgrade() -> None:
    op.drop_table("conversation_history_embeddings")
    op.drop_table("document_chunk_embeddings")
    op.drop_table("guild_builtin_overrides")
    op.drop_table("rule_sources")
    op.drop_table("glossary_term_history")
    op.drop_table("glossary_terms")
    op.drop_table("grug_users")
    op.drop_table("conversation_messages")
    op.drop_table("scheduled_tasks")
    op.drop_table("poll_votes")
    op.drop_table("availability_polls")
    op.drop_table("event_occurrence_overrides")
    op.drop_table("event_notes")
    op.drop_table("event_rsvps")
    op.drop_table("calendar_events")
    op.drop_table("channel_configs")
    op.drop_table("documents")
    op.drop_table("user_profiles")
    op.drop_table("characters")
    op.drop_table("campaigns")
    op.drop_table("guild_configs")
