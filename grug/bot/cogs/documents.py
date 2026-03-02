"""Document management cog for Grug."""

import logging
import tempfile
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select

from grug.bot.cogs.base import GrugCogBase
from grug.db.models import Document
from grug.db.session import get_session_factory
from grug.rag.indexer import DocumentIndexer
from grug.utils import get_campaign_id_for_channel

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_MB = 10
ALLOWED_EXTENSIONS = {".txt", ".md", ".rst", ".pdf"}


class DocumentsCog(GrugCogBase, name="Documents"):
    """Manage documents for RAG retrieval."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._indexer = DocumentIndexer()

    @app_commands.command(
        name="upload_doc",
        description="Upload and index a text document for Grug to reference.",
    )
    @app_commands.describe(
        file="The document to upload (.txt, .md, or .rst).",
        description="Optional description of what this document contains.",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def upload_document(
        self,
        interaction: discord.Interaction,
        file: discord.Attachment,
        description: str = "",
    ) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "This command only works in a server.", ephemeral=True
            )
            return

        ext = Path(file.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            await interaction.response.send_message(
                f"Grug only understand text files ({', '.join(sorted(ALLOWED_EXTENSIONS))}). "
                f"No understand {ext}! 🦴",
                ephemeral=True,
            )
            return

        size_mb = file.size / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            await interaction.response.send_message(
                f"File too big! Max {MAX_FILE_SIZE_MB} MB. Grug brain small. 🧠",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir) / file.filename
            await file.save(tmp_path)

            campaign_id = await get_campaign_id_for_channel(interaction.channel_id)

            factory = get_session_factory()
            async with factory() as session:
                doc = Document(
                    guild_id=interaction.guild_id,
                    filename=file.filename,
                    description=description or None,
                    chroma_collection=f"guild_{interaction.guild_id}",
                    chunk_count=0,
                    uploaded_by=interaction.user.id,
                    campaign_id=campaign_id,
                )
                session.add(doc)
                await session.commit()
                await session.refresh(doc)
                doc_id = doc.id

            chunk_count = await self._indexer.index_file(
                guild_id=interaction.guild_id,
                file_path=tmp_path,
                document_id=doc_id,
                description=description or None,
            )

            async with factory() as session:
                result = await session.execute(
                    select(Document).where(Document.id == doc_id)
                )
                doc_row = result.scalar_one()
                doc_row.chunk_count = chunk_count
                await session.commit()

        await interaction.followup.send(
            f"✅ Grug indexed **{file.filename}** — {chunk_count} chunks ready for search!"
        )

    @app_commands.command(
        name="list_docs", description="List all indexed documents for this server."
    )
    async def list_documents(self, interaction: discord.Interaction) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "This command only works in a server.", ephemeral=True
            )
            return

        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(Document).where(Document.guild_id == interaction.guild_id)
            )
            docs = result.scalars().all()

        if not docs:
            await interaction.response.send_message(
                "No documents indexed yet. Use `/upload_doc` to add some!"
            )
            return

        embed = discord.Embed(
            title="📚 Indexed Documents",
            color=discord.Color.green(),
        )
        for doc in docs:
            value = f"ID: {doc.id} | Chunks: {doc.chunk_count}"
            if doc.description:
                value += f"\n{doc.description}"
            embed.add_field(name=doc.filename, value=value, inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="remove_doc", description="Remove an indexed document by its ID."
    )
    @app_commands.describe(doc_id="The document ID (from /list_docs).")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def remove_document(
        self, interaction: discord.Interaction, doc_id: int
    ) -> None:
        if interaction.guild_id is None:
            await interaction.response.send_message(
                "This command only works in a server.", ephemeral=True
            )
            return

        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(Document).where(
                    Document.id == doc_id, Document.guild_id == interaction.guild_id
                )
            )
            doc = result.scalar_one_or_none()
            if doc is None:
                await interaction.response.send_message(
                    f"Grug not find document #{doc_id}. Wrong ID? 🤷", ephemeral=True
                )
                return
            filename = doc.filename
            await self._indexer.delete_document(interaction.guild_id, doc_id)
            await session.delete(doc)
            await session.commit()

        await interaction.response.send_message(
            f"🗑️ Removed **{filename}** from Grug's memory."
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DocumentsCog(bot))
