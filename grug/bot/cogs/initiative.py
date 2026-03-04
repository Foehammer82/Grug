"""Initiative tracker cog — /initiative command group for Discord encounter management."""

import logging

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select

from grug.bot.cogs.base import GrugCogBase
from grug.db.models import Campaign, Character, Encounter
from grug.db.session import get_session_factory
from grug.encounter import (
    EncounterError,
    add_combatant,
    add_condition,
    advance_turn,
    create_encounter,
    deal_damage,
    end_encounter,
    format_damage_results,
    format_heal_results,
    format_save_results,
    get_active_encounter,
    get_encounter_by_id,
    heal_combatant,
    remove_condition,
    roll_death_save,
    roll_saving_throws,
    set_initiative_roll,
    sorted_combatants,
    start_encounter,
)

logger = logging.getLogger(__name__)


def _initiative_embed(enc: Encounter, *, show_hidden: bool = False) -> discord.Embed:
    """Build a rich embed showing the current initiative order.

    When *show_hidden* is False (the default for public channel messages),
    combatants marked ``is_hidden`` are omitted so players never see them.
    The current-turn marker is resolved by combatant ID so it stays correct
    after hidden entries are filtered out.
    """
    full_order = sorted_combatants(enc)
    # Resolve the current combatant's stable ID from the unfiltered list.
    current_id: int | None = None
    if (
        enc.status == "active"
        and full_order
        and 0 <= enc.current_turn_index < len(full_order)
    ):
        current_id = full_order[enc.current_turn_index].id

    order = full_order if show_hidden else [c for c in full_order if not c.is_hidden]
    status_color = {
        "preparing": 0xFFA500,  # orange
        "active": 0x58A6FF,  # blue
        "ended": 0x666666,  # grey
    }

    embed = discord.Embed(
        title=f"⚔️ {enc.name}",
        color=status_color.get(enc.status, 0x58A6FF),
    )

    if not order:
        embed.description = (
            "No combatants yet.\n\n"
            "**How to join:**\n"
            "• Everyone: `/initiative add name:<your character> modifier:<DEX mod>`\n"
            "• DM adds monsters: `/initiative add name:Goblin modifier:2 enemy:True`\n"
            "• When ready, DM runs: `/initiative roll`"
        )
        embed.set_footer(text=f"Status: {enc.status}")
        return embed

    lines: list[str] = []
    for c in order:
        is_current = enc.status == "active" and c.id == current_id
        marker = "▶ " if is_current else "   "
        roll_str = str(c.initiative_roll) if c.initiative_roll is not None else "—"
        enemy_tag = " 👹" if c.is_enemy else ""
        hidden_tag = " 🔒" if show_hidden and c.is_hidden else ""

        # HP badge
        hp_str = ""
        if c.max_hp is not None and c.current_hp is not None:
            if c.temp_hp:
                hp_str = f" `{c.current_hp}+{c.temp_hp}/{c.max_hp}`"
            else:
                hp_str = f" `{c.current_hp}/{c.max_hp}`"

        # Conditions
        cond_str = ""
        if c.conditions:
            cond_str = " " + " ".join(f"⚡{cond}" for cond in c.conditions)

        # Concentration
        conc_str = ""
        if c.concentration_spell:
            conc_str = f" 🔮{c.concentration_spell}"

        # Death saves
        death_str = ""
        if c.current_hp is not None and c.current_hp == 0:
            if c.death_save_successes or c.death_save_failures:
                s = "●" * c.death_save_successes + "○" * (3 - c.death_save_successes)
                f_ = "●" * c.death_save_failures + "○" * (3 - c.death_save_failures)
                death_str = f" 💀S:{s} F:{f_}"

        line = f"{marker}`{roll_str:>3}`  {c.name}{enemy_tag}{hidden_tag}{hp_str}{cond_str}{conc_str}{death_str}"
        if is_current:
            line = f"**{line}**"
        lines.append(line)

    embed.description = "\n".join(lines)
    embed.set_footer(
        text=f"Round {enc.round_number} · {enc.status.capitalize()} · {len(order)} combatants"
    )
    return embed


class InitiativeCog(GrugCogBase, name="Initiative"):
    """Track initiative and encounters in your campaign."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    initiative = app_commands.Group(
        name="initiative",
        description="Initiative tracker — run /initiative start to begin an encounter",
        guild_only=True,
    )

    # ── /initiative start ────────────────────────────────────────

    @initiative.command(
        name="start",
        description="Step 1: Create a new encounter (everyone can then /initiative add themselves)",
    )
    @app_commands.describe(
        name="Give the encounter a name, e.g. 'Goblin Ambush' or 'Boss Fight'"
    )
    async def initiative_start(
        self,
        interaction: discord.Interaction,
        name: str,
    ) -> None:
        factory = get_session_factory()
        async with factory() as session:
            campaign = (
                await session.execute(
                    select(Campaign).where(
                        Campaign.channel_id == interaction.channel_id,
                        Campaign.deleted_at.is_(None),
                    )
                )
            ).scalar_one_or_none()

            if campaign is None:
                await interaction.response.send_message(
                    "⚠️ No campaign linked to this channel.", ephemeral=True
                )
                return

            enc = await create_encounter(
                session,
                campaign_id=campaign.id,
                guild_id=interaction.guild_id,
                name=name,
                created_by=interaction.user.id,
                channel_id=interaction.channel_id,
            )
            await session.commit()
            await session.refresh(enc, attribute_names=["combatants"])

            embed = _initiative_embed(enc)
            embed.add_field(
                name="💡 What's Next?",
                value=(
                    "Everyone use `/initiative add` to join the encounter.\n"
                    "The DM can also add monsters.\n"
                    "When ready, DM runs `/initiative roll` to roll initiative and start combat!"
                ),
                inline=False,
            )
            await interaction.response.send_message(embed=embed)

    # ── /initiative add ──────────────────────────────────────────

    @initiative.command(
        name="add",
        description="Step 2: Add yourself (or a monster) to the encounter",
    )
    @app_commands.describe(
        name="Your character name (or monster name if DM). Auto-links to your character sheet if names match.",
        modifier="Initiative modifier — usually your DEX modifier (e.g. 3 for +3). Auto-pulled from sheet if matched.",
        enemy="Set to True for monsters/enemies (DM only). PCs leave this as False.",
    )
    async def initiative_add(
        self,
        interaction: discord.Interaction,
        name: str,
        modifier: int = 0,
        enemy: bool = False,
    ) -> None:
        factory = get_session_factory()
        async with factory() as session:
            campaign = (
                await session.execute(
                    select(Campaign).where(
                        Campaign.channel_id == interaction.channel_id,
                        Campaign.deleted_at.is_(None),
                    )
                )
            ).scalar_one_or_none()
            if campaign is None:
                await interaction.response.send_message(
                    "⚠️ No campaign linked to this channel.", ephemeral=True
                )
                return

            enc = await get_active_encounter(session, campaign.id)
            if enc is None:
                await interaction.response.send_message(
                    "⚠️ No active encounter. Start one with `/initiative start`.",
                    ephemeral=True,
                )
                return

            # Check if this user has a character in the campaign (for PC auto-linking)
            character_id = None
            if not enemy:
                char = (
                    await session.execute(
                        select(Character).where(
                            Character.campaign_id == campaign.id,
                            Character.owner_discord_user_id == interaction.user.id,
                        )
                    )
                ).scalar_one_or_none()
                if char and char.name.lower() == name.lower():
                    character_id = char.id
                    # Pull initiative modifier from character sheet if available
                    if modifier == 0 and char.structured_data:
                        sheet_init = char.structured_data.get("initiative")
                        if isinstance(sheet_init, (int, float)):
                            modifier = int(sheet_init)

            await add_combatant(
                session,
                encounter_id=enc.id,
                name=name,
                initiative_modifier=modifier,
                is_enemy=enemy,
                character_id=character_id,
            )
            await session.commit()

            enc = await get_encounter_by_id(session, enc.id)
            embed = _initiative_embed(enc)
            await interaction.response.send_message(embed=embed)

    # ── /initiative roll ─────────────────────────────────────────────

    @initiative.command(
        name="roll",
        description="Step 3: Roll initiative for everyone and start combat! (DM only)",
    )
    async def initiative_roll(
        self,
        interaction: discord.Interaction,
    ) -> None:
        factory = get_session_factory()
        async with factory() as session:
            campaign = (
                await session.execute(
                    select(Campaign).where(
                        Campaign.channel_id == interaction.channel_id,
                        Campaign.deleted_at.is_(None),
                    )
                )
            ).scalar_one_or_none()
            if campaign is None:
                await interaction.response.send_message(
                    "⚠️ No campaign linked to this channel.", ephemeral=True
                )
                return

            enc = await get_active_encounter(session, campaign.id)
            if enc is None:
                await interaction.response.send_message(
                    "⚠️ No active encounter.", ephemeral=True
                )
                return

            try:
                enc = await start_encounter(session, enc.id)
                await session.commit()
            except EncounterError as exc:
                await interaction.response.send_message(f"⚠️ {exc}", ephemeral=True)
                return

            enc = await get_encounter_by_id(session, enc.id)
            embed = _initiative_embed(enc)
            await interaction.response.send_message(embed=embed)

    # ── /initiative next ─────────────────────────────────────────────

    @initiative.command(
        name="next", description="Advance to the next combatant's turn (DM)"
    )
    async def initiative_next(
        self,
        interaction: discord.Interaction,
    ) -> None:
        factory = get_session_factory()
        async with factory() as session:
            campaign = (
                await session.execute(
                    select(Campaign).where(
                        Campaign.channel_id == interaction.channel_id,
                        Campaign.deleted_at.is_(None),
                    )
                )
            ).scalar_one_or_none()
            if campaign is None:
                await interaction.response.send_message(
                    "⚠️ No campaign linked to this channel.", ephemeral=True
                )
                return

            enc = await get_active_encounter(session, campaign.id)
            if enc is None:
                await interaction.response.send_message(
                    "⚠️ No active encounter.", ephemeral=True
                )
                return

            try:
                enc, next_combatant = await advance_turn(session, enc.id)
                await session.commit()
            except EncounterError as exc:
                await interaction.response.send_message(f"⚠️ {exc}", ephemeral=True)
                return

            enc = await get_encounter_by_id(session, enc.id)
            embed = _initiative_embed(enc)
            embed.add_field(
                name="Up Next",
                value=f"**{next_combatant.name}** — it's your turn!",
                inline=False,
            )
            await interaction.response.send_message(embed=embed)

    # ── /initiative show ─────────────────────────────────────────────

    @initiative.command(
        name="show", description="Show the current initiative order and round"
    )
    async def initiative_show(
        self,
        interaction: discord.Interaction,
    ) -> None:
        factory = get_session_factory()
        async with factory() as session:
            campaign = (
                await session.execute(
                    select(Campaign).where(
                        Campaign.channel_id == interaction.channel_id,
                        Campaign.deleted_at.is_(None),
                    )
                )
            ).scalar_one_or_none()
            if campaign is None:
                await interaction.response.send_message(
                    "⚠️ No campaign linked to this channel.", ephemeral=True
                )
                return

            enc = await get_active_encounter(session, campaign.id)
            if enc is None:
                await interaction.response.send_message(
                    "No active encounter in this campaign.", ephemeral=True
                )
                return

            embed = _initiative_embed(enc)
            await interaction.response.send_message(embed=embed)

    # ── /initiative end ──────────────────────────────────────────────

    @initiative.command(
        name="end", description="End the current encounter (clears initiative order)"
    )
    async def initiative_end(
        self,
        interaction: discord.Interaction,
    ) -> None:
        factory = get_session_factory()
        async with factory() as session:
            campaign = (
                await session.execute(
                    select(Campaign).where(
                        Campaign.channel_id == interaction.channel_id,
                        Campaign.deleted_at.is_(None),
                    )
                )
            ).scalar_one_or_none()
            if campaign is None:
                await interaction.response.send_message(
                    "⚠️ No campaign linked to this channel.", ephemeral=True
                )
                return

            enc = await get_active_encounter(session, campaign.id)
            if enc is None:
                await interaction.response.send_message(
                    "No active encounter to end.", ephemeral=True
                )
                return

            try:
                enc = await end_encounter(session, enc.id)
                await session.commit()
            except EncounterError as exc:
                await interaction.response.send_message(f"⚠️ {exc}", ephemeral=True)
                return

            embed = discord.Embed(
                title=f"⚔️ {enc.name} — Ended",
                description="The encounter has ended. Good fight!",
                color=0x666666,
            )
            await interaction.response.send_message(embed=embed)

    # ── /initiative setroll ────────────────────────────────────────────

    @initiative.command(
        name="setroll",
        description="Set a manual initiative roll for a combatant (physical dice). Players: before combat only.",
    )
    @app_commands.describe(
        target="Combatant name (exact match) — players can only set their own character's roll",
        roll="The initiative roll result from your physical dice (total, including modifiers)",
    )
    async def initiative_setroll(
        self,
        interaction: discord.Interaction,
        target: str,
        roll: int,
    ) -> None:
        factory = get_session_factory()
        async with factory() as session:
            result = await self._get_active(interaction, session)
            if result is None:
                return
            _campaign, enc = result

            match = [
                c
                for c in enc.combatants
                if c.name.lower() == target.strip().lower() and c.is_active
            ]
            if not match:
                await interaction.response.send_message(
                    f"⚠️ No combatant named: {target}", ephemeral=True
                )
                return

            combatant = match[0]

            # Permission check: GM (creator) can set any roll anytime,
            # players can only set their own character's roll during 'preparing'
            is_gm = enc.created_by == interaction.user.id
            if not is_gm:
                if enc.status != "preparing":
                    await interaction.response.send_message(
                        "⚠️ Players can only set initiative rolls before combat starts.",
                        ephemeral=True,
                    )
                    return
                if combatant.character_id is None:
                    await interaction.response.send_message(
                        "⚠️ You can only set the roll for your own character.",
                        ephemeral=True,
                    )
                    return
                # Verify the linked character belongs to this user
                char = await session.get(Character, combatant.character_id)
                if char is None or char.owner_discord_user_id != interaction.user.id:
                    await interaction.response.send_message(
                        "⚠️ You can only set the roll for your own character.",
                        ephemeral=True,
                    )
                    return

            try:
                await set_initiative_roll(session, enc.id, combatant.id, roll)
                await session.commit()
            except EncounterError as exc:
                await interaction.response.send_message(f"⚠️ {exc}", ephemeral=True)
                return

            enc = await get_encounter_by_id(session, enc.id)
            embed = _initiative_embed(enc)
            await interaction.response.send_message(
                content=f"🎲 Set **{combatant.name}**'s initiative roll to **{roll}**.",
                embed=embed,
            )

    # ── /initiative monster ──────────────────────────────────────────

    @initiative.command(
        name="monster",
        description="Search for a monster and add it with full stats (HP, AC, initiative) auto-filled",
    )
    @app_commands.describe(
        search="Monster name to search for (e.g. 'Goblin', 'Adult Red Dragon', 'Owlbear')",
        display_name="Optional custom name for the combatant (e.g. 'Goblin 1'). Uses official name if not set.",
        system="Game system: 'dnd5e' or 'pf2e'. Searches all if not set.",
    )
    async def initiative_monster(
        self,
        interaction: discord.Interaction,
        search: str,
        display_name: str = "",
        system: str = "",
    ) -> None:
        from grug.monster_search import search_monsters

        await interaction.response.defer()

        sys_filter = system.strip().lower() if system.strip() else None
        results = await search_monsters(search, system=sys_filter, limit=5)
        if not results:
            await interaction.followup.send(
                f"⚠️ No monsters matching '{search}'. Try a different name.",
                ephemeral=True,
            )
            return

        monster = results[0]
        name = display_name.strip() or monster.name

        factory = get_session_factory()
        async with factory() as session:
            campaign = (
                await session.execute(
                    select(Campaign).where(
                        Campaign.channel_id == interaction.channel_id,
                        Campaign.deleted_at.is_(None),
                    )
                )
            ).scalar_one_or_none()
            if campaign is None:
                await interaction.followup.send(
                    "⚠️ No campaign linked to this channel.", ephemeral=True
                )
                return

            enc = await get_active_encounter(session, campaign.id)
            if enc is None:
                await interaction.followup.send(
                    "⚠️ No active encounter.", ephemeral=True
                )
                return

            await add_combatant(
                session,
                encounter_id=enc.id,
                name=name,
                initiative_modifier=monster.initiative_modifier or 0,
                is_enemy=True,
                max_hp=monster.hp,
                armor_class=monster.ac,
                save_modifiers=monster.save_modifiers,
            )
            await session.commit()

            enc = await get_encounter_by_id(session, enc.id)
            embed = _initiative_embed(enc)

            stats = []
            if monster.hp is not None:
                stats.append(f"HP {monster.hp}")
            if monster.ac is not None:
                stats.append(f"AC {monster.ac}")
            if monster.initiative_modifier is not None:
                mod = monster.initiative_modifier
                stats.append(f"Init {mod:+d}")
            if monster.cr:
                stats.append(f"CR {monster.cr}")
            stats_str = " · ".join(stats) if stats else "no stats found"

            source_label = (
                "5e SRD"
                if monster.source == "srd_5e"
                else "PF2e (AoN)"
                if monster.source == "aon_pf2e"
                else monster.source
            )

            # Show other matches if any
            alt_text = ""
            if len(results) > 1:
                alts = ", ".join(r.name for r in results[1:4])
                alt_text = f"\n*Also found: {alts}*"

            await interaction.followup.send(
                content=f"👹 **{name}** added! ({monster.name} from {source_label})\n[{stats_str}]{alt_text}",
                embed=embed,
            )

    # ── Helper: get campaign + active encounter ─────────────────────

    async def _get_active(
        self, interaction: discord.Interaction, session
    ) -> tuple | None:
        """Return (campaign, encounter) or send error and return None."""
        campaign = (
            await session.execute(
                select(Campaign).where(
                    Campaign.channel_id == interaction.channel_id,
                    Campaign.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        if campaign is None:
            await interaction.response.send_message(
                "⚠️ No campaign linked to this channel.", ephemeral=True
            )
            return None

        enc = await get_active_encounter(session, campaign.id)
        if enc is None:
            await interaction.response.send_message(
                "⚠️ No active encounter.", ephemeral=True
            )
            return None
        return campaign, enc

    # ── /initiative damage ──────────────────────────────────────────

    @initiative.command(
        name="damage", description="Deal damage to one or more combatants (DM)"
    )
    @app_commands.describe(
        targets="Combatant names separated by commas (e.g. 'Goblin 1, Goblin 2')",
        amount="How much damage to deal",
        damage_type="Optional: fire, slashing, radiant, etc.",
    )
    async def initiative_damage(
        self,
        interaction: discord.Interaction,
        targets: str,
        amount: int,
        damage_type: str = "",
    ) -> None:
        factory = get_session_factory()
        async with factory() as session:
            result = await self._get_active(interaction, session)
            if result is None:
                return
            _campaign, enc = result

            target_names = [t.strip().lower() for t in targets.split(",")]
            ids = [
                c.id
                for c in enc.combatants
                if c.name.lower() in target_names and c.is_active
            ]
            if not ids:
                await interaction.response.send_message(
                    f"⚠️ No combatants found matching: {targets}", ephemeral=True
                )
                return

            try:
                results = await deal_damage(
                    session,
                    enc.id,
                    ids,
                    amount,
                    damage_type=damage_type or None,
                )
                await session.commit()
            except EncounterError as exc:
                await interaction.response.send_message(f"⚠️ {exc}", ephemeral=True)
                return

            text = format_damage_results(results, amount, damage_type or None)
            enc = await get_encounter_by_id(session, enc.id)
            embed = _initiative_embed(enc)
            await interaction.response.send_message(content=text, embed=embed)

    # ── /initiative heal ────────────────────────────────────────────

    @initiative.command(name="heal", description="Heal one or more combatants (DM)")
    @app_commands.describe(
        targets="Combatant names separated by commas",
        amount="How much to heal",
    )
    async def initiative_heal(
        self,
        interaction: discord.Interaction,
        targets: str,
        amount: int,
    ) -> None:
        factory = get_session_factory()
        async with factory() as session:
            result = await self._get_active(interaction, session)
            if result is None:
                return
            _campaign, enc = result

            target_names = [t.strip().lower() for t in targets.split(",")]
            ids = [
                c.id
                for c in enc.combatants
                if c.name.lower() in target_names and c.is_active
            ]
            if not ids:
                await interaction.response.send_message(
                    f"⚠️ No combatants found matching: {targets}", ephemeral=True
                )
                return

            try:
                results = await heal_combatant(session, enc.id, ids, amount)
                await session.commit()
            except EncounterError as exc:
                await interaction.response.send_message(f"⚠️ {exc}", ephemeral=True)
                return

            text = format_heal_results(results, amount)
            enc = await get_encounter_by_id(session, enc.id)
            embed = _initiative_embed(enc)
            await interaction.response.send_message(content=text, embed=embed)

    # ── /initiative save ────────────────────────────────────────────

    @initiative.command(
        name="save", description="Call for saving throws from combatants (DM)"
    )
    @app_commands.describe(
        targets="Combatant names separated by commas (e.g. 'Goblin 1, Goblin 2')",
        ability="Ability score: STR, DEX, CON, INT, WIS, or CHA",
        dc="Difficulty class to beat (e.g. 15)",
    )
    async def initiative_save(
        self,
        interaction: discord.Interaction,
        targets: str,
        ability: str,
        dc: int,
    ) -> None:
        factory = get_session_factory()
        async with factory() as session:
            result = await self._get_active(interaction, session)
            if result is None:
                return
            _campaign, enc = result

            target_names = [t.strip().lower() for t in targets.split(",")]
            ids = [
                c.id
                for c in enc.combatants
                if c.name.lower() in target_names and c.is_active
            ]
            if not ids:
                await interaction.response.send_message(
                    f"⚠️ No combatants found matching: {targets}", ephemeral=True
                )
                return

            try:
                results = await roll_saving_throws(session, enc.id, ids, ability, dc)
                await session.commit()
            except EncounterError as exc:
                await interaction.response.send_message(f"⚠️ {exc}", ephemeral=True)
                return

            text = format_save_results(results, ability, dc)
            await interaction.response.send_message(content=text)

    # ── /initiative condition ───────────────────────────────────────

    @initiative.command(
        name="condition", description="Add or remove a condition from a combatant (DM)"
    )
    @app_commands.describe(
        target="Combatant name (exact match)",
        condition="Condition name — e.g. Prone, Frightened, Blinded, Stunned",
        remove="Set to True to remove the condition instead of adding it",
    )
    async def initiative_condition(
        self,
        interaction: discord.Interaction,
        target: str,
        condition: str,
        remove: bool = False,
    ) -> None:
        factory = get_session_factory()
        async with factory() as session:
            result = await self._get_active(interaction, session)
            if result is None:
                return
            _campaign, enc = result

            match = [
                c
                for c in enc.combatants
                if c.name.lower() == target.strip().lower() and c.is_active
            ]
            if not match:
                await interaction.response.send_message(
                    f"⚠️ No combatant named: {target}", ephemeral=True
                )
                return

            try:
                if remove:
                    await remove_condition(session, enc.id, [match[0].id], condition)
                    await session.commit()
                    msg = f"Removed **{condition}** from **{match[0].name}**."
                else:
                    await add_condition(session, enc.id, [match[0].id], condition)
                    await session.commit()
                    msg = f"Added **{condition}** to **{match[0].name}**."
            except EncounterError as exc:
                await interaction.response.send_message(f"⚠️ {exc}", ephemeral=True)
                return

            enc = await get_encounter_by_id(session, enc.id)
            embed = _initiative_embed(enc)
            await interaction.response.send_message(content=msg, embed=embed)

    # ── /initiative deathsave ───────────────────────────────────────

    @initiative.command(
        name="deathsave", description="Roll a death saving throw for a downed combatant"
    )
    @app_commands.describe(
        target="Name of the combatant at 0 HP. Nat 20 = revive with 1 HP, Nat 1 = two failures.",
    )
    async def initiative_deathsave(
        self,
        interaction: discord.Interaction,
        target: str,
    ) -> None:
        factory = get_session_factory()
        async with factory() as session:
            result = await self._get_active(interaction, session)
            if result is None:
                return
            _campaign, enc = result

            match = [
                c
                for c in enc.combatants
                if c.name.lower() == target.strip().lower() and c.is_active
            ]
            if not match:
                await interaction.response.send_message(
                    f"⚠️ No combatant named: {target}", ephemeral=True
                )
                return

            try:
                combatant, roll, _success, status = await roll_death_save(
                    session, enc.id, match[0].id
                )
                await session.commit()
            except EncounterError as exc:
                await interaction.response.send_message(f"⚠️ {exc}", ephemeral=True)
                return

            status_msgs = {
                "success": f"✅ Success! ({combatant.death_save_successes}/3 ✅, {combatant.death_save_failures}/3 ❌)",
                "failure": f"❌ Failure! ({combatant.death_save_successes}/3 ✅, {combatant.death_save_failures}/3 ❌)",
                "stabilized": "🛡️ Stabilized! Three successes!",
                "dead": "💀 Dead. Three failures.",
                "nat20_revive": "🌟 Natural 20! Revived with 1 HP!",
                "nat1_double_fail": f"💀 Natural 1! Two failures! ({combatant.death_save_successes}/3 ✅, {combatant.death_save_failures}/3 ❌)",
            }

            msg = f"🎲 **{combatant.name}** death save: **{roll}**\n{status_msgs.get(status, status)}"
            enc = await get_encounter_by_id(session, enc.id)
            embed = _initiative_embed(enc)
            await interaction.response.send_message(content=msg, embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(InitiativeCog(bot))
