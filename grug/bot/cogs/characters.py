"""Character sheet cog — lets players upload, view, and manage their characters.

Works in both guild channels and DMs.
"""

import io
import logging
from pathlib import Path

import aiofiles
import discord
from discord.ext import commands
from sqlalchemy import select

from grug.character.indexer import CharacterIndexer
from grug.character.parser import CharacterSheetParser
from grug.config.settings import get_settings
from grug.db.models import Campaign, Character, UserProfile
from grug.db.session import get_session_factory

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {
    ".txt",
    ".md",
    ".rst",
    ".pdf",
    ".docx",
    ".doc",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
}
MAX_FILE_SIZE_MB = 20

_SYSTEM_LABELS = {
    "dnd5e": "D&D 5e",
    "pf2e": "Pathfinder 2e",
    "unknown": "Unknown / Homebrew",
}


class CharactersCog(commands.Cog, name="Characters"):
    """Manage player character sheets."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        settings = get_settings()
        self._parser = CharacterSheetParser(
            anthropic_api_key=settings.anthropic_api_key,
            anthropic_model=settings.anthropic_model,
        )
        self._indexer = CharacterIndexer()
        self._file_data_dir = Path(settings.file_data_dir)

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    @commands.group(name="character", aliases=["char"], invoke_without_command=True)
    async def character_group(self, ctx: commands.Context) -> None:
        """Character sheet commands. Use !character <subcommand>."""
        await ctx.send_help(ctx.command)

    @character_group.command(name="upload")
    async def upload_character(self, ctx: commands.Context) -> None:
        """Upload a character sheet file.

        Attach your sheet to this command. Supported: PDF, DOCX, PNG, JPG, WEBP, TXT, MD.

        Grug will read the sheet, detect the game system, and store it so you can
        ask questions about it in DMs or during sessions.

        Usage: !character upload
        """
        if not ctx.message.attachments:
            await ctx.send(
                "Grug need file! Attach your character sheet to the command. 📄"
            )
            return

        attachment = ctx.message.attachments[0]
        ext = Path(attachment.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            await ctx.send(
                f"Grug no understand {ext} files. "
                f"Try: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )
            return

        size_mb = attachment.size / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            await ctx.send(
                f"File too big! Max {MAX_FILE_SIZE_MB} MB. Grug brain small. 🧠"
            )
            return

        async with ctx.typing():
            file_bytes = await attachment.read()
            thinking_msg = await ctx.send(
                "Grug reading scroll... 📜 (this take a moment)"
            )

            try:
                raw_text, structured_data, detected_system = await self._parser.parse(
                    file_bytes, attachment.filename
                )
            except Exception as exc:
                logger.exception("Character sheet parsing failed: %s", exc)
                await thinking_msg.edit(
                    content="Grug brain hurt — parsing failed. Try again?"
                )
                return

            char_name = (structured_data.get("name") or "").strip() or Path(
                attachment.filename
            ).stem
            user_id = ctx.author.id

            factory = get_session_factory()
            async with factory() as session:
                existing = await session.execute(
                    select(Character).where(
                        Character.owner_discord_user_id == user_id,
                        Character.name == char_name,
                    )
                )
                character = existing.scalar_one_or_none()
                if character is None:
                    character = Character(
                        owner_discord_user_id=user_id,
                        name=char_name,
                        system=detected_system,
                        raw_sheet_text=raw_text,
                        structured_data=structured_data,
                    )
                    session.add(character)
                else:
                    character.system = detected_system
                    character.raw_sheet_text = raw_text
                    character.structured_data = structured_data
                await session.commit()
                await session.refresh(character)
                character_id = character.id

            # Save raw file to the persistent volume.
            file_path = await self._save_file(
                file_bytes, user_id, character_id, attachment.filename
            )
            async with factory() as session:
                row = (
                    await session.execute(
                        select(Character).where(Character.id == character_id)
                    )
                ).scalar_one()
                row.file_path = file_path
                await session.commit()

            # Index the sheet for semantic search.
            await self._indexer.index_character(character_id, raw_text)

            # Ensure profile exists; make this the active character if none is set.
            await _ensure_user_profile(user_id, default_character_id=character_id)

        system_label = _SYSTEM_LABELS.get(detected_system, detected_system)
        char_level = structured_data.get("level")
        char_class = structured_data.get("class_and_subclass") or "?"
        embed = discord.Embed(
            title=f"📜 {char_name}",
            description=f"Sheet uploaded and indexed! (ID: {character_id})",
            color=discord.Color.green(),
        )
        embed.add_field(name="System", value=system_label, inline=True)
        embed.add_field(name="Class", value=char_class, inline=True)
        if char_level:
            embed.add_field(name="Level", value=str(char_level), inline=True)
        embed.set_footer(
            text="Use !character show to view your sheet, or DM Grug to chat about it!"
        )
        await thinking_msg.edit(content=None, embed=embed)

    @character_group.command(name="show")
    async def show_character(self, ctx: commands.Context, *, name: str = "") -> None:
        """Show a character sheet.

        Usage: !character show [name]
        """
        character = await _resolve_character(ctx.author.id, name or None)
        if character is None:
            await ctx.send(
                "No character found. Upload one with `!character upload` or specify a name."
            )
            return
        embed, md_text = _build_character_embed_and_md(character)
        file = discord.File(
            fp=io.BytesIO(md_text.encode()),
            filename=f"{character.name.replace(' ', '_')}.md",
        )
        await ctx.send(embed=embed, file=file)

    @character_group.command(name="list")
    async def list_characters(self, ctx: commands.Context) -> None:
        """List all your characters."""
        factory = get_session_factory()
        async with factory() as session:
            characters = (
                (
                    await session.execute(
                        select(Character).where(
                            Character.owner_discord_user_id == ctx.author.id
                        )
                    )
                )
                .scalars()
                .all()
            )
        if not characters:
            await ctx.send(
                "You have no characters. Upload one with `!character upload`!"
            )
            return
        profile = await _get_user_profile(ctx.author.id)
        active_id = profile.active_character_id if profile else None
        embed = discord.Embed(title="📜 Your Characters", color=discord.Color.blue())
        for c in characters:
            system_label = _SYSTEM_LABELS.get(c.system, c.system)
            active_tag = " ★ active" if c.id == active_id else ""
            value = f"System: {system_label}"
            if c.structured_data:
                lvl = c.structured_data.get("level")
                cls = c.structured_data.get("class_and_subclass")
                if lvl:
                    value += f" | Lv {lvl}"
                if cls:
                    value += f" | {cls}"
            if c.campaign_id:
                value += f" | Campaign ID: {c.campaign_id}"
            embed.add_field(name=f"{c.name}{active_tag}", value=value, inline=False)
        await ctx.send(embed=embed)

    @character_group.command(name="setactive")
    async def set_active(self, ctx: commands.Context, *, name: str) -> None:
        """Set your active character (used in DM sessions).

        Usage: !character setactive <name>
        """
        character = await _resolve_character(ctx.author.id, name)
        if character is None:
            await ctx.send(f"Grug no find character named **{name}**. Check spelling?")
            return
        await _ensure_user_profile(ctx.author.id, default_character_id=character.id)
        factory = get_session_factory()
        async with factory() as session:
            profile = (
                await session.execute(
                    select(UserProfile).where(
                        UserProfile.discord_user_id == ctx.author.id
                    )
                )
            ).scalar_one()
            profile.active_character_id = character.id
            await session.commit()
        await ctx.send(
            f"⚔️ **{character.name}** is now your active character. Grug remember!"
        )

    @character_group.command(name="link")
    async def link_campaign(self, ctx: commands.Context) -> None:
        """Link your active character to this channel's campaign.

        Usage: !character link
        """
        if ctx.guild is None:
            await ctx.send("This command only works in a server channel, not DMs.")
            return
        character = await _resolve_character(ctx.author.id, None)
        if character is None:
            await ctx.send(
                "No active character. Upload one with `!character upload` first."
            )
            return
        factory = get_session_factory()
        async with factory() as session:
            campaign = (
                await session.execute(
                    select(Campaign).where(Campaign.channel_id == ctx.channel.id)
                )
            ).scalar_one_or_none()
        if campaign is None:
            await ctx.send(
                "No campaign is linked to this channel. "
                "An admin can create one with `!campaign create <name>`."
            )
            return
        async with factory() as session:
            row = (
                await session.execute(
                    select(Character).where(Character.id == character.id)
                )
            ).scalar_one()
            row.campaign_id = campaign.id
            await session.commit()
        await ctx.send(
            f"⚔️ **{character.name}** linked to campaign **{campaign.name}**! "
            "Grug know where your adventures happen now."
        )

    @character_group.command(name="export")
    async def export_character(self, ctx: commands.Context, *, name: str = "") -> None:
        """Export your character sheet as a Markdown file.

        Usage: !character export [name]
        """
        character = await _resolve_character(ctx.author.id, name or None)
        if character is None:
            await ctx.send("No character found. Upload one with `!character upload`.")
            return
        _, md_text = _build_character_embed_and_md(character)
        file = discord.File(
            fp=io.BytesIO(md_text.encode()),
            filename=f"{character.name.replace(' ', '_')}.md",
        )
        await ctx.send(
            f"📎 Here is **{character.name}**'s sheet, adventurer!", file=file
        )

    async def _save_file(
        self, file_bytes: bytes, user_id: int, character_id: int, filename: str
    ) -> str:
        """Persist the raw file and return a path relative to file_data_dir."""
        char_dir = self._file_data_dir / "characters" / str(user_id)
        char_dir.mkdir(parents=True, exist_ok=True)
        safe_filename = f"{character_id}_{Path(filename).name}"
        dest = char_dir / safe_filename
        async with aiofiles.open(dest, "wb") as f:
            await f.write(file_bytes)
        return str(dest.relative_to(self._file_data_dir))


# ------------------------------------------------------------------
# Helpers shared with agent tools
# ------------------------------------------------------------------


async def _get_user_profile(discord_user_id: int) -> UserProfile | None:
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(UserProfile).where(UserProfile.discord_user_id == discord_user_id)
        )
        return result.scalar_one_or_none()


async def _ensure_user_profile(
    discord_user_id: int,
    default_character_id: int | None = None,
) -> UserProfile:
    """Return the UserProfile, creating it if absent."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(UserProfile).where(UserProfile.discord_user_id == discord_user_id)
        )
        profile = result.scalar_one_or_none()
        if profile is None:
            profile = UserProfile(
                discord_user_id=discord_user_id,
                active_character_id=default_character_id,
            )
            session.add(profile)
        elif profile.active_character_id is None and default_character_id is not None:
            profile.active_character_id = default_character_id
        await session.commit()
        await session.refresh(profile)
        return profile


async def _resolve_character(
    discord_user_id: int, name: str | None
) -> Character | None:
    """Return a character by name, or the user's active character if name is None."""
    factory = get_session_factory()
    async with factory() as session:
        if name:
            result = await session.execute(
                select(Character).where(
                    Character.owner_discord_user_id == discord_user_id,
                    Character.name == name,
                )
            )
            return result.scalar_one_or_none()

        profile_result = await session.execute(
            select(UserProfile).where(UserProfile.discord_user_id == discord_user_id)
        )
        profile = profile_result.scalar_one_or_none()
        if profile is None or profile.active_character_id is None:
            result = await session.execute(
                select(Character)
                .where(Character.owner_discord_user_id == discord_user_id)
                .order_by(Character.created_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()
        result = await session.execute(
            select(Character).where(Character.id == profile.active_character_id)
        )
        return result.scalar_one_or_none()


def _build_character_embed_and_md(character: Character) -> tuple[discord.Embed, str]:
    """Build a Discord embed and Markdown text for a character sheet."""
    sd = character.structured_data or {}
    system_label = _SYSTEM_LABELS.get(character.system, character.system)

    embed = discord.Embed(title=f"📜 {character.name}", color=discord.Color.blue())
    embed.add_field(name="System", value=system_label, inline=True)
    if sd.get("level"):
        embed.add_field(name="Level", value=str(sd["level"]), inline=True)
    if sd.get("class_and_subclass"):
        embed.add_field(name="Class", value=sd["class_and_subclass"], inline=True)
    if sd.get("race_or_ancestry"):
        embed.add_field(name="Race/Ancestry", value=sd["race_or_ancestry"], inline=True)
    if sd.get("background"):
        embed.add_field(name="Background", value=sd["background"], inline=True)
    if sd.get("alignment"):
        embed.add_field(name="Alignment", value=sd["alignment"], inline=True)
    hp = sd.get("hp") or {}
    if hp.get("max"):
        hp_str = f"{hp.get('current', '?')}/{hp['max']}"
        if hp.get("temp"):
            hp_str += f" (+{hp['temp']} temp)"
        embed.add_field(name="HP", value=hp_str, inline=True)
    if sd.get("armor_class"):
        embed.add_field(name="AC", value=str(sd["armor_class"]), inline=True)
    if sd.get("speed"):
        embed.add_field(name="Speed", value=str(sd["speed"]), inline=True)
    scores = sd.get("ability_scores") or {}
    if any(scores.values()):
        score_str = "  ".join(
            f"**{k}** {v}" for k, v in scores.items() if v is not None
        )
        embed.add_field(name="Ability Scores", value=score_str, inline=False)

    lines = [f"# {character.name}", f"**System:** {system_label}", ""]
    if sd.get("player_name"):
        lines.append(f"**Player:** {sd['player_name']}")
    if sd.get("level"):
        lines.append(f"**Level:** {sd['level']}")
    if sd.get("class_and_subclass"):
        lines.append(f"**Class:** {sd['class_and_subclass']}")
    if sd.get("race_or_ancestry"):
        lines.append(f"**Race/Ancestry:** {sd['race_or_ancestry']}")
    if sd.get("background"):
        lines.append(f"**Background:** {sd['background']}")
    if sd.get("alignment"):
        lines.append(f"**Alignment:** {sd['alignment']}")
    lines.append("")
    if scores and any(scores.values()):
        lines.append("## Ability Scores")
        lines.append(
            " | ".join(f"{k}: {v}" for k, v in scores.items() if v is not None)
        )
        lines.append("")
    if hp.get("max"):
        lines.append(f"**HP:** {hp.get('current', '?')}/{hp['max']}")
    if sd.get("armor_class"):
        lines.append(f"**AC:** {sd['armor_class']}")
    if sd.get("speed"):
        lines.append(f"**Speed:** {sd['speed']}")
    lines.append("")
    if sd.get("features_and_traits"):
        lines.append("## Features & Traits")
        for feat in sd["features_and_traits"]:
            lines.append(f"- {feat}")
        lines.append("")
    if sd.get("inventory"):
        lines.append("## Inventory")
        for item in sd["inventory"]:
            lines.append(f"- {item}")
        lines.append("")
    if sd.get("notes"):
        lines.append("## Notes")
        lines.append(sd["notes"])
        lines.append("")
    if not sd and character.raw_sheet_text:
        lines.append("## Raw Sheet")
        lines.append(character.raw_sheet_text)

    return embed, "\n".join(lines)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CharactersCog(bot))
