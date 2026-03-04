"""Gold banking routes — party pool and per-character wallet management.

All endpoints require ``campaign.banking_enabled = True``.
GM and guild admins can always adjust any balance.
Players can always spend (negative-adjust) their own wallet and transfer
between their wallet and the party pool.
``campaign.player_banking_enabled = True`` is required only for players to
add gold to their own wallet directly (i.e. positive self-adjustment).
"""

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import (
    assert_guild_member,
    get_current_user,
    get_db,
    get_or_404,
    is_guild_admin,
)
from api.schemas import (
    GoldAdjustRequest,
    GoldTransactionOut,
    GoldTransferRequest,
)
from grug.db.models import Campaign, Character, GoldTransaction

logger = logging.getLogger(__name__)

router = APIRouter(tags=["gold"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_banking(campaign: Campaign) -> None:
    """Raise 409 if banking is not enabled for this campaign."""
    if not campaign.banking_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Banking is not enabled for this campaign.",
        )


def _is_campaign_gm(campaign: Campaign, user: dict[str, Any]) -> bool:
    """Return True if the user is the designated GM of this campaign."""
    if campaign.gm_discord_user_id is None:
        return False
    return campaign.gm_discord_user_id == int(user.get("id", 0))


async def _assert_can_manage_gold(
    campaign: Campaign,
    user: dict[str, Any],
    guild_id: int,
    character_owner_id: int | None = None,
) -> None:
    """Raise 403 unless the user has permission to make a gold adjustment.

    Permission is granted when ANY of the following is true:
    - User is a guild admin
    - User is the campaign GM
    - ``player_banking_enabled`` is True AND (no specific character is targeted
      OR the user owns the target character)
    """
    admin = await is_guild_admin(guild_id, user)
    if admin or _is_campaign_gm(campaign, user):
        return

    if not campaign.player_banking_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Player banking is not enabled for this campaign.",
        )

    # Players can only adjust their own character wallet or the party pool.
    if character_owner_id is not None:
        user_id = int(user.get("id", 0))
        if character_owner_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only adjust your own character's gold.",
            )


async def _record_transaction(
    db: AsyncSession,
    campaign: Campaign,
    user: dict[str, Any],
    amount: float,
    reason: str | None,
    character_id: int | None = None,
) -> None:
    """Insert a GoldTransaction row for the given gold movement."""
    tx = GoldTransaction(
        campaign_id=campaign.id,
        character_id=character_id,
        actor_discord_user_id=int(user.get("id", 0)),
        amount=amount,
        reason=reason,
        created_at=datetime.now(timezone.utc),
    )
    db.add(tx)


# ---------------------------------------------------------------------------
# Party pool
# ---------------------------------------------------------------------------


@router.post(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/gold/party",
    response_model=dict,
    status_code=200,
)
async def adjust_party_gold(
    guild_id: int,
    campaign_id: int,
    body: GoldAdjustRequest,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Add or remove gold from the shared party pool.

    Pass a positive ``amount`` to credit and negative to debit.
    """
    await assert_guild_member(guild_id, user)
    campaign = await get_or_404(
        db,
        Campaign,
        Campaign.id == campaign_id,
        Campaign.guild_id == guild_id,
        detail="Campaign not found",
    )
    _require_banking(campaign)
    await _assert_can_manage_gold(campaign, user, guild_id)

    campaign.party_gold = float(campaign.party_gold) + body.amount  # type: ignore[assignment]
    await _record_transaction(db, campaign, user, body.amount, body.reason)
    await db.commit()
    await db.refresh(campaign)
    return {"party_gold": float(campaign.party_gold)}


# ---------------------------------------------------------------------------
# Character wallet
# ---------------------------------------------------------------------------


@router.post(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/gold/characters/{character_id}",
    response_model=dict,
    status_code=200,
)
async def adjust_character_gold(
    guild_id: int,
    campaign_id: int,
    character_id: int,
    body: GoldAdjustRequest,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Add or remove gold from a character's personal wallet.

    Pass a positive ``amount`` to credit and negative to debit.
    """
    await assert_guild_member(guild_id, user)
    campaign = await get_or_404(
        db,
        Campaign,
        Campaign.id == campaign_id,
        Campaign.guild_id == guild_id,
        detail="Campaign not found",
    )
    _require_banking(campaign)

    character = await get_or_404(
        db,
        Character,
        Character.id == character_id,
        Character.campaign_id == campaign_id,
        detail="Character not found in this campaign",
    )

    # Admins / GMs: unrestricted.
    # Players: may always spend (negative amount) their own gold.
    #          Positive self-adjustments (adding gold from nowhere) require player_banking_enabled.
    admin = await is_guild_admin(guild_id, user)
    if not admin and not _is_campaign_gm(campaign, user):
        user_id = int(user.get("id", 0))
        if character.owner_discord_user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only adjust your own character's gold.",
            )
        if body.amount > 0 and not campaign.player_banking_enabled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Player banking is not enabled — you cannot add gold to your wallet directly.",
            )

    character.gold = float(character.gold) + body.amount  # type: ignore[assignment]
    await _record_transaction(
        db, campaign, user, body.amount, body.reason, character_id
    )
    await db.commit()
    await db.refresh(character)
    return {"gold": float(character.gold)}


# ---------------------------------------------------------------------------
# Transfer between character wallet and party pool
# ---------------------------------------------------------------------------


@router.post(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/gold/transfer",
    response_model=dict,
    status_code=200,
)
async def transfer_gold(
    guild_id: int,
    campaign_id: int,
    body: GoldTransferRequest,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Transfer gold between a character's wallet and the party pool.

    Exactly one of ``from_character_id`` / ``to_character_id`` should be set;
    the other ``None`` side represents the party pool.

    Examples:
    - Player deposits to party  → ``from_character_id=<id>, to_character_id=null``
    - GM gives from party pool  → ``from_character_id=null, to_character_id=<id>``
    """
    await assert_guild_member(guild_id, user)
    if (body.from_character_id is None) == (body.to_character_id is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Exactly one of from_character_id / to_character_id must be null "
                "(the null side represents the party pool)."
            ),
        )
    if body.amount <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Transfer amount must be positive.",
        )

    campaign = await get_or_404(
        db,
        Campaign,
        Campaign.id == campaign_id,
        Campaign.guild_id == guild_id,
        detail="Campaign not found",
    )
    _require_banking(campaign)

    # Determine the source and destination characters.
    source_char: Character | None = None
    dest_char: Character | None = None

    if body.from_character_id is not None:
        source_char = await get_or_404(
            db,
            Character,
            Character.id == body.from_character_id,
            Character.campaign_id == campaign_id,
            detail="Source character not found in this campaign",
        )

    if body.to_character_id is not None:
        dest_char = await get_or_404(
            db,
            Character,
            Character.id == body.to_character_id,
            Character.campaign_id == campaign_id,
            detail="Destination character not found in this campaign",
        )

    # Admins / GMs: unrestricted.
    # Players: may freely move their own gold to/from the party pool.
    admin = await is_guild_admin(guild_id, user)
    if not admin and not _is_campaign_gm(campaign, user):
        user_id = int(user.get("id", 0))
        if source_char is not None and source_char.owner_discord_user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only transfer from your own character's wallet.",
            )
        if dest_char is not None and dest_char.owner_discord_user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only transfer gold to your own character.",
            )

    # Apply the transfer atomically.
    if source_char is not None:
        if float(source_char.gold) < body.amount:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"{source_char.name} only has {source_char.gold} gold.",
            )
        source_char.gold = float(source_char.gold) - body.amount  # type: ignore[assignment]
        await _record_transaction(
            db, campaign, user, -body.amount, body.reason, source_char.id
        )
        campaign.party_gold = float(campaign.party_gold) + body.amount  # type: ignore[assignment]
        await _record_transaction(db, campaign, user, body.amount, body.reason)
    else:
        # From party pool to character.
        if float(campaign.party_gold) < body.amount:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Party pool only has {campaign.party_gold} gold.",
            )
        campaign.party_gold = float(campaign.party_gold) - body.amount  # type: ignore[assignment]
        await _record_transaction(db, campaign, user, -body.amount, body.reason)
        assert dest_char is not None
        dest_char.gold = float(dest_char.gold) + body.amount  # type: ignore[assignment]
        await _record_transaction(
            db, campaign, user, body.amount, body.reason, dest_char.id
        )

    await db.commit()
    result: dict = {"party_gold": float(campaign.party_gold)}
    if source_char is not None:
        await db.refresh(source_char)
        result["from_character_gold"] = float(source_char.gold)
    if dest_char is not None:
        await db.refresh(dest_char)
        result["to_character_gold"] = float(dest_char.gold)
    return result


# ---------------------------------------------------------------------------
# Ledger (admin / GM view)
# ---------------------------------------------------------------------------


@router.get(
    "/api/guilds/{guild_id}/campaigns/{campaign_id}/gold/ledger",
    response_model=list[GoldTransactionOut],
)
async def get_gold_ledger(
    guild_id: int,
    campaign_id: int,
    limit: int = 100,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[GoldTransaction]:
    """Return the most recent gold transactions for this campaign.

    Accessible to all campaign members — players can see the full ledger so
    all deposits, withdrawals, and transfers are transparent.
    """
    await assert_guild_member(guild_id, user)
    await get_or_404(
        db,
        Campaign,
        Campaign.id == campaign_id,
        Campaign.guild_id == guild_id,
        detail="Campaign not found",
    )

    result = await db.execute(
        select(GoldTransaction)
        .where(GoldTransaction.campaign_id == campaign_id)
        .order_by(GoldTransaction.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
