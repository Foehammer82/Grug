"""Party gold / banking tools for the Grug agent.

Registers tools that let Grug act as the party banker — tracking individual
character wallets and a shared party gold pool.  All tools respect the
``banking_enabled`` flag on the campaign and gate write access to the
appropriate combination of (admin, GM, or permitted player).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydantic_ai import RunContext
from sqlalchemy import select

from grug.agent.core import GrugDeps

if TYPE_CHECKING:
    from pydantic_ai import Agent

logger = logging.getLogger(__name__)

_NO_CAMPAIGN = (
    "No campaign is linked to this channel. "
    "An admin can create one with /campaign create."
)
_BANKING_DISABLED = (
    "Banking is not enabled for this campaign. "
    "An admin can enable it in the campaign settings."
)
_PLAYER_BANKING_DISABLED = (
    "Player transactions are not enabled for this campaign. "
    "Only the GM or an admin can adjust gold here."
)


async def _get_campaign(ctx: RunContext[GrugDeps]):
    """Return the campaign for the current channel, or None."""
    from grug.db.models import Campaign
    from grug.db.session import get_session_factory

    if ctx.deps.campaign_id is None:
        return None

    factory = get_session_factory()
    async with factory() as session:
        return (
            await session.execute(
                select(Campaign).where(Campaign.id == ctx.deps.campaign_id)
            )
        ).scalar_one_or_none()


async def _is_admin_or_gm(ctx: RunContext[GrugDeps]) -> bool:
    """Return True if the requesting user is a guild admin or the campaign GM."""
    from grug.agent.tools.campaign_tools import _is_admin
    from grug.db.models import Campaign
    from grug.db.session import get_session_factory

    if await _is_admin(ctx):
        return True

    if ctx.deps.campaign_id is None:
        return False

    factory = get_session_factory()
    async with factory() as session:
        campaign = (
            await session.execute(
                select(Campaign).where(Campaign.id == ctx.deps.campaign_id)
            )
        ).scalar_one_or_none()
        return campaign is not None and campaign.gm_discord_user_id == ctx.deps.user_id


def register_banking_tools(agent: Agent[GrugDeps, str]) -> None:
    """Register all gold banking tools on *agent*."""

    @agent.tool
    async def get_gold_summary(ctx: RunContext[GrugDeps]) -> str:
        """Get the current gold balances for the party.

        Returns the party pool total and each character's wallet.
        Only the character owner, the GM, or an admin can see individual
        character balances — others see only the party pool.

        Use when players ask "how much gold do we have", "what's my gold",
        "show me the party treasury", or similar.
        """
        from grug.db.models import Character
        from grug.db.session import get_session_factory

        campaign = await _get_campaign(ctx)
        if campaign is None:
            return _NO_CAMPAIGN
        if not campaign.banking_enabled:
            return _BANKING_DISABLED

        privileged = await _is_admin_or_gm(ctx)

        factory = get_session_factory()
        async with factory() as session:
            chars = (
                (
                    await session.execute(
                        select(Character).where(
                            Character.campaign_id == ctx.deps.campaign_id
                        )
                    )
                )
                .scalars()
                .all()
            )

        party_gold = float(campaign.party_gold or 0)
        lines = [f"**Party treasury:** {party_gold:,.4g} gp", ""]

        if chars:
            lines.append("**Character wallets:**")
            for ch in chars:
                is_owner = ch.owner_discord_user_id == ctx.deps.user_id
                if privileged or is_owner:
                    lines.append(f"  - {ch.name}: {float(ch.gold or 0):,.4g} gp")
                else:
                    lines.append(f"  - {ch.name}: [private]")
        else:
            lines.append("(no characters in this campaign)")

        return "\n".join(lines)

    @agent.tool
    async def adjust_party_gold(
        ctx: RunContext[GrugDeps], amount: float, reason: str | None = None
    ) -> str:
        """Add or subtract gold from the shared party pool.

        Use a positive *amount* to deposit gold and a negative amount to
        withdraw.  Only the GM and guild admins can call this tool; players
        must use ``transfer_gold`` to move gold between their wallet and the
        pool.

        Parameters
        ----------
        amount:
            Amount to add (positive) or remove (negative) from the pool.
        reason:
            Optional flavour reason logged to the ledger if ledger mode is on.
        """
        from grug.db.session import get_session_factory

        campaign = await _get_campaign(ctx)
        if campaign is None:
            return _NO_CAMPAIGN
        if not campaign.banking_enabled:
            return _BANKING_DISABLED
        if not await _is_admin_or_gm(ctx):
            return (
                "Only the GM or an admin can adjust the party pool directly. "
                "Use 'transfer_gold' to deposit from your own wallet."
            )

        factory = get_session_factory()
        async with factory() as session:
            from grug.db.models import Campaign

            camp = await session.get(Campaign, campaign.id)
            if camp is None:
                return "Campaign not found."
            new_balance = float(camp.party_gold or 0) + amount
            if new_balance < 0:
                return (
                    f"Not enough gold in the party pool. "
                    f"Current balance: {float(camp.party_gold or 0):,.4g} gp, "
                    f"requested withdrawal: {abs(amount):,.4g} gp."
                )
            camp.party_gold = new_balance  # type: ignore[assignment]

            from grug.db.models import GoldTransaction

            session.add(
                GoldTransaction(
                    campaign_id=camp.id,
                    character_id=None,
                    actor_discord_user_id=ctx.deps.user_id,
                    amount=amount,
                    reason=reason,
                )
            )
            await session.commit()

        verb = "Added" if amount >= 0 else "Removed"
        abs_amt = abs(amount)
        return (
            f"{verb} {abs_amt:,.4g} gp {'to' if amount >= 0 else 'from'} the party pool. "
            f"New balance: {new_balance:,.4g} gp."
        )

    @agent.tool
    async def adjust_character_gold(
        ctx: RunContext[GrugDeps],
        character_name: str,
        amount: float,
        reason: str | None = None,
    ) -> str:
        """Add or subtract gold from a specific character's personal wallet.

        Players can only adjust their **own** wallet (requires
        ``player_banking_enabled`` on the campaign).  The GM and admins can
        adjust any character's wallet.

        Parameters
        ----------
        character_name:
            Name (or partial name) of the character whose wallet to adjust.
        amount:
            Amount to add (positive) or remove (negative).
        reason:
            Optional reason, saved to the ledger when ledger mode is on.
        """
        from grug.db.models import Character
        from grug.db.session import get_session_factory

        campaign = await _get_campaign(ctx)
        if campaign is None:
            return _NO_CAMPAIGN
        if not campaign.banking_enabled:
            return _BANKING_DISABLED

        privileged = await _is_admin_or_gm(ctx)

        factory = get_session_factory()
        async with factory() as session:
            chars = (
                (
                    await session.execute(
                        select(Character).where(
                            Character.campaign_id == ctx.deps.campaign_id
                        )
                    )
                )
                .scalars()
                .all()
            )

        # Fuzzy name match
        search = character_name.strip().lower()
        match = None
        for c in chars:
            if c.name.lower() == search:
                match = c
                break
        if match is None:
            for c in chars:
                if search in c.name.lower():
                    match = c
                    break
        if match is None:
            names = ", ".join(c.name for c in chars)
            return f"No character matching '{character_name}' found. Available: {names}"

        # Permission check
        is_owner = match.owner_discord_user_id == ctx.deps.user_id
        if not privileged:
            if not is_owner:
                return "You can only adjust your own gold."
            if not campaign.player_banking_enabled:
                return _PLAYER_BANKING_DISABLED

        async with factory() as session:
            char = await session.get(Character, match.id)
            if char is None:
                return "Character not found."
            new_balance = float(char.gold or 0) + amount
            if new_balance < 0:
                return (
                    f"Not enough gold in {char.name}'s wallet. "
                    f"Current: {float(char.gold or 0):,.4g} gp, "
                    f"withdrawal: {abs(amount):,.4g} gp."
                )
            char.gold = new_balance  # type: ignore[assignment]

            from grug.db.models import GoldTransaction

            session.add(
                GoldTransaction(
                    campaign_id=campaign.id,
                    character_id=char.id,
                    actor_discord_user_id=ctx.deps.user_id,
                    amount=amount,
                    reason=reason,
                )
            )
            await session.commit()

        verb = "Added" if amount >= 0 else "Removed"
        abs_amt = abs(amount)
        return (
            f"{verb} {abs_amt:,.4g} gp {'to' if amount >= 0 else 'from'} {match.name}'s wallet. "
            f"New balance: {new_balance:,.4g} gp."
        )

    @agent.tool
    async def transfer_gold(
        ctx: RunContext[GrugDeps],
        amount: float,
        from_name: str | None = None,
        to_name: str | None = None,
        reason: str | None = None,
    ) -> str:
        """Transfer gold between a character's wallet and the party pool.

        Exactly one of *from_name* / *to_name* should be a character name;
        the other should be omitted (or set to ``null``) to represent the
        party pool.

        Examples
        --------
        - Player deposits 10 gp into the party pool:
          ``transfer_gold(amount=10, from_name="Thorn")``
        - GM pays out 50 gp from the pool to a character:
          ``transfer_gold(amount=50, to_name="Thorn")``

        Parameters
        ----------
        amount:
            Positive amount to move.
        from_name:
            Source character name, or omit to draw from the party pool.
        to_name:
            Destination character name, or omit to deposit into the party pool.
        reason:
            Optional description logged to the ledger.
        """
        from grug.db.models import Character
        from grug.db.session import get_session_factory

        if amount <= 0:
            return "Amount must be positive for a transfer."
        if (from_name is None) == (to_name is None):
            return (
                "Exactly one of 'from_name' or 'to_name' must be a character name; "
                "the other represents the party pool (leave it blank)."
            )

        campaign = await _get_campaign(ctx)
        if campaign is None:
            return _NO_CAMPAIGN
        if not campaign.banking_enabled:
            return _BANKING_DISABLED

        privileged = await _is_admin_or_gm(ctx)

        factory = get_session_factory()
        async with factory() as session:
            chars = (
                (
                    await session.execute(
                        select(Character).where(
                            Character.campaign_id == ctx.deps.campaign_id
                        )
                    )
                )
                .scalars()
                .all()
            )

        def _find(name: str) -> Character | None:
            search = name.strip().lower()
            for c in chars:
                if c.name.lower() == search:
                    return c
            for c in chars:
                if search in c.name.lower():
                    return c
            return None

        char_name = from_name or to_name
        assert char_name is not None
        char = _find(char_name)
        if char is None:
            names = ", ".join(c.name for c in chars)
            return f"No character matching '{char_name}' found. Available: {names}"

        # Permission check
        is_owner = char.owner_discord_user_id == ctx.deps.user_id
        if not privileged:
            if not is_owner:
                return "You can only transfer gold for your own character."
            if not campaign.player_banking_enabled:
                return _PLAYER_BANKING_DISABLED

        async with factory() as session:
            from grug.db.models import Campaign as CampaignModel
            from grug.db.models import GoldTransaction

            char_obj = await session.get(Character, char.id)
            camp_obj = await session.get(CampaignModel, campaign.id)
            if char_obj is None or camp_obj is None:
                return "Character or campaign not found."

            char_balance = float(char_obj.gold or 0)
            party_balance = float(camp_obj.party_gold or 0)

            if from_name is not None:
                # Character → party pool
                if char_balance < amount:
                    return (
                        f"Not enough gold in {char_obj.name}'s wallet. "
                        f"Current: {char_balance:,.4g} gp, transfer: {amount:,.4g} gp."
                    )
                char_obj.gold = char_balance - amount  # type: ignore[assignment]
                camp_obj.party_gold = party_balance + amount  # type: ignore[assignment]
                direction = f"from {char_obj.name}'s wallet to the party pool"
            else:
                # Party pool → character
                if party_balance < amount:
                    return (
                        f"Not enough gold in the party pool. "
                        f"Current: {party_balance:,.4g} gp, transfer: {amount:,.4g} gp."
                    )
                camp_obj.party_gold = party_balance - amount  # type: ignore[assignment]
                char_obj.gold = char_balance + amount  # type: ignore[assignment]
                direction = f"from the party pool to {char_obj.name}'s wallet"

            session.add(
                GoldTransaction(
                    campaign_id=campaign.id,
                    character_id=char_obj.id,
                    actor_discord_user_id=ctx.deps.user_id,
                    amount=amount if to_name else -amount,
                    reason=reason,
                )
            )
            await session.commit()

            return (
                f"Transferred {amount:,.4g} gp {direction}. "
                f"{char_obj.name} wallet: {float(char_obj.gold):,.4g} gp. "
                f"Party pool: {float(camp_obj.party_gold):,.4g} gp."
            )
