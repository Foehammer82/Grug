"""Document management cog for Grug."""

import logging
import tempfile
from pathlib import Path

import discord
from discord.ext import commands
from sqlalchemy import select

from grug.db.models import Document
from grug.db.session import get_session_factory
from grug.rag.indexer import DocumentIndexer

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_MB = 10
ALLOWED_EXTENSIONS = {".txt", ".md", ".rst"}


class DocumentsCog(commands.Cog, name="Documents"):
    """Manage documents for RAG retrieval."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._indexer = DocumentIndexer()

    @commands.command(name="upload_doc", aliases=["add_doc"])
    @commands.has_permissions(manage_guild=True)
    async def upload_document(
        self, ctx: commands.Context, *, description: str = ""
    ) -> None:
        """Upload and index a text document. Attach the file to this command.

        Usage: !upload_doc [description]
        Supported formats: .txt, .md, .rst
        """
        if not ctx.message.attachments:
            await ctx.send("Grug needs file! Attach a document to the command. 📄")
            return

        attachment = ctx.message.attachments[0]
        ext = Path(attachment.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            await ctx.send(
                f"Grug only understand text files ({', '.join(sorted(ALLOWED_EXTENSIONS))}). "
                f"No understand {ext}!"
            )
            return

        size_mb = attachment.size / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            await ctx.send(
                f"File too big! Max {MAX_FILE_SIZE_MB} MB. Grug brain small. 🧠"
            )
            return

        async with ctx.typing():
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_path = Path(tmp_dir) / attachment.filename
                await attachment.save(tmp_path)

                factory = get_session_factory()
                async with factory() as session:
                    doc = Document(
                        guild_id=ctx.guild.id,
                        filename=attachment.filename,
                        description=description or None,
                        chroma_collection=f"guild_{ctx.guild.id}",
                        chunk_count=0,
                        uploaded_by=ctx.author.id,
                    )
                    session.add(doc)
                    await session.commit()
                    await session.refresh(doc)
                    doc_id = doc.id

                chunk_count = await self._indexer.index_file(
                    guild_id=ctx.guild.id,
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

        await ctx.send(
            f"✅ Grug indexed **{attachment.filename}** — {chunk_count} chunks ready for search!"
        )

    @commands.command(name="list_docs")
    async def list_documents(self, ctx: commands.Context) -> None:
        """List all indexed documents for this server."""
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(Document).where(Document.guild_id == ctx.guild.id)
            )
            docs = result.scalars().all()

        if not docs:
            await ctx.send("No documents indexed yet. Use `!upload_doc` to add some!")
            return

        embed = discord.Embed(
            title="📚 Indexed Documents",
            color=discord.Color.green(),
        )
        for doc in docs:
            value = f"Chunks: {doc.chunk_count}"
            if doc.description:
                value += f"\n{doc.description}"
            embed.add_field(name=doc.filename, value=value, inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="remove_doc", aliases=["delete_doc"])
    @commands.has_permissions(manage_guild=True)
    async def remove_document(self, ctx: commands.Context, doc_id: int) -> None:
        """Remove an indexed document by its ID.

        Usage: !remove_doc <doc_id>
        """
        factory = get_session_factory()
        async with factory() as session:
            result = await session.execute(
                select(Document).where(
                    Document.id == doc_id, Document.guild_id == ctx.guild.id
                )
            )
            doc = result.scalar_one_or_none()
            if doc is None:
                await ctx.send(f"Grug not find document #{doc_id}. Wrong ID? 🤷")
                return
            filename = doc.filename
            await self._indexer.delete_document(ctx.guild.id, doc_id)
            await session.delete(doc)
            await session.commit()

        await ctx.send(f"🗑️ Removed **{filename}** from Grug's memory.")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DocumentsCog(bot))
