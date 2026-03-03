"""Character sheet cog — lets players upload, view, and manage their characters.

Works in both guild channels and DMs.
"""

import io
import logging
from pathlib import Path

import aiofiles
import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select

from grug.character.indexer import CharacterIndexer
from grug.character.parser import CharacterSheetParser
from grug.character.pathbuilder import PathbuilderError, fetch_pathbuilder_character
from grug.config.settings import get_settings
from grug.db.models import Campaign, Character, UserProfile
from grug.db.session import get_session_factory
from grug.utils import GAME_SYSTEM_LABELS

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


class CharactersCog(commands.Cog, name="Characters"):
    """Manage player character sheets."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        settings = get_settings()
        self._parser = CharacterSheetParser(
            anthropic_api_key=settings.anthropic_api_key,
            anthropic_model=settings.anthropic_big_brain_model,
        )
        self._indexer = CharacterIndexer()
        self._file_data_dir = Path(settings.file_data_dir)

    # ------------------------------------------------------------------
    # Slash command group
    # ------------------------------------------------------------------

    character = app_commands.Group(
        name="character",
        description="Manage your player character sheets.",
    )

    @character.command(
        name="upload",
        description="Upload a character sheet file for Grug to read and index.",
    )
    @app_commands.describe(
        file="Your character sheet (PDF, DOCX, PNG, JPG, WEBP, TXT, or MD)."
    )
    async def upload_character(
        self, interaction: discord.Interaction, file: discord.Attachment
    ) -> None:
        ext = Path(file.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            await interaction.response.send_message(
                f"Grug no understand {ext} files. "
                f"Try: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
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

        file_bytes = await file.read()
        thinking_msg = await interaction.followup.send(
            "Grug reading scroll... 📜 (this take a moment)"
        )

        try:
            raw_text, structured_data, detected_system = await self._parser.parse(
                file_bytes, file.filename
            )
        except Exception as exc:
            logger.exception("Character sheet parsing failed: %s", exc)
            await thinking_msg.edit(
                content="Grug brain hurt — parsing failed. Try again?"
            )
            return

        char_name = (structured_data.get("name") or "").strip() or Path(
            file.filename
        ).stem
        user_id = interaction.user.id

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

        file_path = await self._save_file(
            file_bytes, user_id, character_id, file.filename
        )
        async with factory() as session:
            row = (
                await session.execute(
                    select(Character).where(Character.id == character_id)
                )
            ).scalar_one()
            row.file_path = file_path
            await session.commit()

        await self._indexer.index_character(character_id, raw_text)
        await _ensure_user_profile(user_id, default_character_id=character_id)

        system_label = GAME_SYSTEM_LABELS.get(detected_system, detected_system)
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
            text="Use /character show to view your sheet, or DM Grug to chat about it!"
        )
        await thinking_msg.edit(content=None, embed=embed)

    @character.command(name="show", description="Show one of your character sheets.")
    @app_commands.describe(
        name="Character name (leave blank for your active character)."
    )
    async def show_character(
        self, interaction: discord.Interaction, name: str | None = None
    ) -> None:
        character = await _resolve_character(interaction.user.id, name)
        if character is None:
            await interaction.response.send_message(
                "No character found. Upload one with `/character upload` or specify a name.",
                ephemeral=True,
            )
            return
        embed, md_text = _build_character_embed_and_md(character)
        file = discord.File(
            fp=io.BytesIO(md_text.encode()),
            filename=f"{character.name.replace(' ', '_')}.md",
        )
        await interaction.response.send_message(embed=embed, file=file)

    @character.command(name="list", description="List all your characters.")
    async def list_characters(self, interaction: discord.Interaction) -> None:
        factory = get_session_factory()
        async with factory() as session:
            characters = (
                (
                    await session.execute(
                        select(Character).where(
                            Character.owner_discord_user_id == interaction.user.id
                        )
                    )
                )
                .scalars()
                .all()
            )
        if not characters:
            await interaction.response.send_message(
                "You have no characters. Upload one with `/character upload`!",
                ephemeral=True,
            )
            return
        profile = await _get_user_profile(interaction.user.id)
        active_id = profile.active_character_id if profile else None
        embed = discord.Embed(title="📜 Your Characters", color=discord.Color.blue())
        for c in characters:
            system_label = GAME_SYSTEM_LABELS.get(c.system, c.system)
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
        await interaction.response.send_message(embed=embed)

    @character.command(
        name="setactive", description="Set your active character (used in DM sessions)."
    )
    @app_commands.describe(name="The name of the character to set as active.")
    async def set_active(self, interaction: discord.Interaction, name: str) -> None:
        character = await _resolve_character(interaction.user.id, name)
        if character is None:
            await interaction.response.send_message(
                f"Grug no find character named **{name}**. Check spelling?",
                ephemeral=True,
            )
            return
        await _ensure_user_profile(
            interaction.user.id, default_character_id=character.id
        )
        factory = get_session_factory()
        async with factory() as session:
            profile = (
                await session.execute(
                    select(UserProfile).where(
                        UserProfile.discord_user_id == interaction.user.id
                    )
                )
            ).scalar_one()
            profile.active_character_id = character.id
            await session.commit()
        await interaction.response.send_message(
            f"⚔️ **{character.name}** is now your active character. Grug remember!"
        )

    @character.command(
        name="link",
        description="Link your active character to this channel's campaign.",
    )
    async def link_campaign(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command only works in a server channel, not DMs.", ephemeral=True
            )
            return
        character = await _resolve_character(interaction.user.id, None)
        if character is None:
            await interaction.response.send_message(
                "No active character. Upload one with `/character upload` first.",
                ephemeral=True,
            )
            return
        factory = get_session_factory()
        async with factory() as session:
            campaign = (
                await session.execute(
                    select(Campaign).where(
                        Campaign.channel_id == interaction.channel_id
                    )
                )
            ).scalar_one_or_none()
        if campaign is None:
            await interaction.response.send_message(
                "No campaign is linked to this channel. "
                "An admin can create one with `/campaign create`.",
                ephemeral=True,
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
        await interaction.response.send_message(
            f"⚔️ **{character.name}** linked to campaign **{campaign.name}**! "
            "Grug know where your adventures happen now."
        )

    @character.command(
        name="export", description="Export your character sheet as a Markdown file."
    )
    @app_commands.describe(
        name="Character name (leave blank for your active character)."
    )
    async def export_character(
        self, interaction: discord.Interaction, name: str | None = None
    ) -> None:
        character = await _resolve_character(interaction.user.id, name)
        if character is None:
            await interaction.response.send_message(
                "No character found. Upload one with `/character upload`.",
                ephemeral=True,
            )
            return
        _, md_text = _build_character_embed_and_md(character)
        file = discord.File(
            fp=io.BytesIO(md_text.encode()),
            filename=f"{character.name.replace(' ', '_')}.md",
        )
        await interaction.response.send_message(
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
    # Pathbuilder integration
    # ------------------------------------------------------------------

    @character.command(
        name="pathbuilder",
        description="Link a character from Pathbuilder 2e by ID.",
    )
    @app_commands.describe(
        pathbuilder_id="Your Pathbuilder character ID (the number in the share URL).",
    )
    async def link_pathbuilder(
        self, interaction: discord.Interaction, pathbuilder_id: int
    ) -> None:
        await interaction.response.defer()
        thinking_msg = await interaction.followup.send(
            "Grug fetching scroll from Pathbuilder... 📜"
        )

        try:
            structured_data = await fetch_pathbuilder_character(pathbuilder_id)
        except PathbuilderError as exc:
            await thinking_msg.edit(content=f"Grug can't reach Pathbuilder: {exc}")
            return

        char_name = structured_data.get("name") or f"Pathbuilder #{pathbuilder_id}"
        user_id = interaction.user.id

        factory = get_session_factory()
        async with factory() as session:
            # Check if this Pathbuilder ID is already linked
            existing = await session.execute(
                select(Character).where(
                    Character.owner_discord_user_id == user_id,
                    Character.pathbuilder_id == pathbuilder_id,
                )
            )
            character_row = existing.scalar_one_or_none()
            if character_row is not None:
                # Update existing
                character_row.structured_data = structured_data
                character_row.name = char_name
                character_row.system = "pf2e"
            else:
                # Create new
                character_row = Character(
                    owner_discord_user_id=user_id,
                    name=char_name,
                    system="pf2e",
                    structured_data=structured_data,
                    pathbuilder_id=pathbuilder_id,
                )
                session.add(character_row)
            await session.commit()
            await session.refresh(character_row)
            character_id = character_row.id

        await _ensure_user_profile(user_id, default_character_id=character_id)

        system_label = GAME_SYSTEM_LABELS.get("pf2e", "pf2e")
        char_level = structured_data.get("level")
        char_class = structured_data.get("class_and_subclass") or "?"
        embed = discord.Embed(
            title=f"📜 {char_name}",
            description=f"Linked from Pathbuilder! (ID: {character_id})",
            color=discord.Color.green(),
        )
        embed.add_field(name="System", value=system_label, inline=True)
        embed.add_field(name="Class", value=char_class, inline=True)
        if char_level:
            embed.add_field(name="Level", value=str(char_level), inline=True)
        embed.add_field(
            name="Pathbuilder ID",
            value=str(pathbuilder_id),
            inline=True,
        )
        embed.set_footer(
            text="Use /character sync to refresh from Pathbuilder anytime!"
        )
        await thinking_msg.edit(content=None, embed=embed)

    @character.command(
        name="sync",
        description="Re-sync your active character from Pathbuilder.",
    )
    @app_commands.describe(
        name="Character name (leave blank for your active character).",
    )
    async def sync_pathbuilder(
        self, interaction: discord.Interaction, name: str | None = None
    ) -> None:
        character_row = await _resolve_character(interaction.user.id, name)
        if character_row is None:
            await interaction.response.send_message(
                "No character found. Link one with `/character pathbuilder` first.",
                ephemeral=True,
            )
            return
        if not character_row.pathbuilder_id:
            await interaction.response.send_message(
                f"**{character_row.name}** isn't linked to Pathbuilder. "
                "Use `/character pathbuilder <id>` to link one.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()
        try:
            structured_data = await fetch_pathbuilder_character(
                character_row.pathbuilder_id
            )
        except PathbuilderError as exc:
            await interaction.followup.send(f"Sync failed: {exc}")
            return

        factory = get_session_factory()
        async with factory() as session:
            row = (
                await session.execute(
                    select(Character).where(Character.id == character_row.id)
                )
            ).scalar_one()
            row.structured_data = structured_data
            new_name = structured_data.get("name")
            if new_name:
                row.name = new_name
            await session.commit()

        char_name = structured_data.get("name") or character_row.name
        await interaction.followup.send(
            f"⚔️ **{char_name}** synced from Pathbuilder! Data is fresh. 🔄"
        )


# ------------------------------------------------------------------
# Helpers
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
    system_label = GAME_SYSTEM_LABELS.get(character.system, character.system)

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
