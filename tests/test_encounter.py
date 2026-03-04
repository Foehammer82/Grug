"""Tests for the encounter / initiative tracker service (grug.encounter)."""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from grug.encounter import (
    STATUS_ACTIVE,
    STATUS_ENDED,
    STATUS_PREPARING,
    EncounterError,
    add_combatant,
    advance_turn,
    create_encounter,
    end_encounter,
    format_initiative_order,
    remove_combatant,
    roll_all_initiative,
    roll_combatant_initiative,
    sorted_combatants,
    start_encounter,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_encounter(**overrides):
    """Build a fake Encounter with sensible defaults."""
    enc = MagicMock()
    enc.id = overrides.get("id", 1)
    enc.campaign_id = overrides.get("campaign_id", 10)
    enc.guild_id = overrides.get("guild_id", 100)
    enc.name = overrides.get("name", "Goblin Ambush")
    enc.status = overrides.get("status", STATUS_PREPARING)
    enc.current_turn_index = overrides.get("current_turn_index", 0)
    enc.round_number = overrides.get("round_number", 1)
    enc.channel_id = overrides.get("channel_id", None)
    enc.created_by = overrides.get("created_by", 999)
    enc.created_at = overrides.get("created_at", datetime.now(timezone.utc))
    enc.ended_at = overrides.get("ended_at", None)
    enc.combatants = overrides.get("combatants", [])
    return enc


def _make_combatant(**overrides):
    """Build a fake Combatant with sensible defaults."""
    c = MagicMock()
    c.id = overrides.get("id", 1)
    c.encounter_id = overrides.get("encounter_id", 1)
    c.character_id = overrides.get("character_id", None)
    c.name = overrides.get("name", "Fighter")
    c.initiative_roll = overrides.get("initiative_roll", None)
    c.initiative_modifier = overrides.get("initiative_modifier", 0)
    c.is_enemy = overrides.get("is_enemy", False)
    c.sort_order = overrides.get("sort_order", 0)
    c.is_active = overrides.get("is_active", True)
    return c


# ---------------------------------------------------------------------------
# sorted_combatants
# ---------------------------------------------------------------------------


class TestSortedCombatants:
    def test_sorts_by_initiative_desc(self):
        enc = _make_encounter(
            combatants=[
                _make_combatant(id=1, name="Slow", initiative_roll=5),
                _make_combatant(id=2, name="Fast", initiative_roll=20),
                _make_combatant(id=3, name="Mid", initiative_roll=12),
            ]
        )
        order = sorted_combatants(enc)
        assert [c.name for c in order] == ["Fast", "Mid", "Slow"]

    def test_excludes_inactive(self):
        enc = _make_encounter(
            combatants=[
                _make_combatant(
                    id=1, name="Active", initiative_roll=10, is_active=True
                ),
                _make_combatant(
                    id=2, name="Removed", initiative_roll=15, is_active=False
                ),
            ]
        )
        order = sorted_combatants(enc)
        assert len(order) == 1
        assert order[0].name == "Active"

    def test_unrolled_combatants_sort_last(self):
        enc = _make_encounter(
            combatants=[
                _make_combatant(id=1, name="Rolled", initiative_roll=10),
                _make_combatant(id=2, name="Unrolled", initiative_roll=None),
            ]
        )
        order = sorted_combatants(enc)
        assert order[0].name == "Rolled"
        assert order[1].name == "Unrolled"

    def test_empty_combatants(self):
        enc = _make_encounter(combatants=[])
        assert sorted_combatants(enc) == []


# ---------------------------------------------------------------------------
# create_encounter
# ---------------------------------------------------------------------------


class TestCreateEncounter:
    @pytest.mark.asyncio
    async def test_creates_new_encounter(self):
        db = AsyncMock()
        db.execute = AsyncMock()

        # Mock get_active_encounter returning None (no existing)
        with patch(
            "grug.encounter.get_active_encounter", new=AsyncMock(return_value=None)
        ):
            enc = await create_encounter(
                db,
                campaign_id=10,
                guild_id=100,
                name="Dragon Fight",
                created_by=999,
            )

        assert enc.name == "Dragon Fight"
        assert enc.status == STATUS_PREPARING
        assert enc.campaign_id == 10
        db.add.assert_called_once()
        db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_ends_existing_encounter(self):
        db = AsyncMock()
        existing = _make_encounter(id=1, status=STATUS_ACTIVE)

        with patch(
            "grug.encounter.get_active_encounter", new=AsyncMock(return_value=existing)
        ):
            await create_encounter(
                db,
                campaign_id=10,
                guild_id=100,
                name="New Fight",
                created_by=999,
            )

        assert existing.status == STATUS_ENDED
        assert existing.ended_at is not None


# ---------------------------------------------------------------------------
# add_combatant
# ---------------------------------------------------------------------------


class TestAddCombatant:
    @pytest.mark.asyncio
    async def test_adds_combatant(self):
        db = AsyncMock()
        c = await add_combatant(
            db,
            encounter_id=1,
            name="Goblin",
            initiative_modifier=2,
            is_enemy=True,
        )
        assert c.name == "Goblin"
        assert c.initiative_modifier == 2
        assert c.is_enemy is True
        db.add.assert_called_once()
        db.flush.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_defaults(self):
        db = AsyncMock()
        c = await add_combatant(db, encounter_id=1, name="Fighter")
        assert c.initiative_modifier == 0
        assert c.is_enemy is False
        assert c.character_id is None


# ---------------------------------------------------------------------------
# remove_combatant
# ---------------------------------------------------------------------------


class TestRemoveCombatant:
    @pytest.mark.asyncio
    async def test_soft_removes(self):
        combatant = _make_combatant(id=5, encounter_id=1, is_active=True)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = combatant

        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        await remove_combatant(db, encounter_id=1, combatant_id=5)
        assert combatant.is_active is False

    @pytest.mark.asyncio
    async def test_raises_on_not_found(self):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(EncounterError, match="Combatant not found"):
            await remove_combatant(db, encounter_id=1, combatant_id=999)


# ---------------------------------------------------------------------------
# roll_all_initiative
# ---------------------------------------------------------------------------


class TestRollAllInitiative:
    @pytest.mark.asyncio
    async def test_rolls_for_unrolled_combatants(self):
        combatants = [
            _make_combatant(
                id=1, name="A", initiative_roll=None, initiative_modifier=3
            ),
            _make_combatant(id=2, name="B", initiative_roll=15, initiative_modifier=2),
        ]
        encounter = _make_encounter(combatants=combatants)

        db = AsyncMock()
        with patch(
            "grug.encounter.get_encounter_by_id", new=AsyncMock(return_value=encounter)
        ):
            with patch("grug.encounter._roll_d20", return_value=14):
                result = await roll_all_initiative(db, encounter_id=1)

        # Combatant A should now have 14 + 3 = 17
        assert combatants[0].initiative_roll == 17
        # Combatant B should remain unchanged
        assert combatants[1].initiative_roll == 15
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_raises_on_missing_encounter(self):
        db = AsyncMock()
        with patch(
            "grug.encounter.get_encounter_by_id", new=AsyncMock(return_value=None)
        ):
            with pytest.raises(EncounterError, match="Encounter not found"):
                await roll_all_initiative(db, encounter_id=999)


# ---------------------------------------------------------------------------
# roll_combatant_initiative
# ---------------------------------------------------------------------------


class TestRollCombatantInitiative:
    @pytest.mark.asyncio
    async def test_rolls_for_combatant(self):
        combatant = _make_combatant(id=1, initiative_modifier=5, initiative_roll=None)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = combatant

        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        with patch("grug.encounter._roll_d20", return_value=18):
            result = await roll_combatant_initiative(db, combatant_id=1)

        assert result.initiative_roll == 23  # 18 + 5

    @pytest.mark.asyncio
    async def test_rerolls_existing(self):
        combatant = _make_combatant(id=1, initiative_modifier=2, initiative_roll=10)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = combatant

        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        with patch("grug.encounter._roll_d20", return_value=7):
            result = await roll_combatant_initiative(db, combatant_id=1)

        assert result.initiative_roll == 9  # 7 + 2

    @pytest.mark.asyncio
    async def test_raises_on_not_found(self):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        db = AsyncMock()
        db.execute = AsyncMock(return_value=mock_result)

        with pytest.raises(EncounterError, match="Combatant not found"):
            await roll_combatant_initiative(db, combatant_id=999)


# ---------------------------------------------------------------------------
# start_encounter
# ---------------------------------------------------------------------------


class TestStartEncounter:
    @pytest.mark.asyncio
    async def test_transitions_to_active(self):
        combatants = [
            _make_combatant(
                id=1, name="Fighter", initiative_roll=None, initiative_modifier=2
            ),
        ]
        encounter = _make_encounter(status=STATUS_PREPARING, combatants=combatants)

        db = AsyncMock()
        with patch(
            "grug.encounter.get_encounter_by_id", new=AsyncMock(return_value=encounter)
        ):
            with patch("grug.encounter._roll_d20", return_value=15):
                result = await start_encounter(db, encounter_id=1)

        assert result.status == STATUS_ACTIVE
        assert result.round_number == 1
        assert result.current_turn_index == 0
        assert combatants[0].initiative_roll == 17  # 15 + 2

    @pytest.mark.asyncio
    async def test_already_active_is_noop(self):
        encounter = _make_encounter(
            status=STATUS_ACTIVE,
            combatants=[_make_combatant(initiative_roll=10)],
        )
        db = AsyncMock()
        with patch(
            "grug.encounter.get_encounter_by_id", new=AsyncMock(return_value=encounter)
        ):
            result = await start_encounter(db, encounter_id=1)

        assert result.status == STATUS_ACTIVE

    @pytest.mark.asyncio
    async def test_cannot_start_ended(self):
        encounter = _make_encounter(status=STATUS_ENDED)
        db = AsyncMock()
        with patch(
            "grug.encounter.get_encounter_by_id", new=AsyncMock(return_value=encounter)
        ):
            with pytest.raises(EncounterError, match="Cannot start an ended"):
                await start_encounter(db, encounter_id=1)

    @pytest.mark.asyncio
    async def test_cannot_start_with_no_combatants(self):
        encounter = _make_encounter(status=STATUS_PREPARING, combatants=[])
        db = AsyncMock()
        with patch(
            "grug.encounter.get_encounter_by_id", new=AsyncMock(return_value=encounter)
        ):
            with pytest.raises(EncounterError, match="no combatants"):
                await start_encounter(db, encounter_id=1)


# ---------------------------------------------------------------------------
# advance_turn
# ---------------------------------------------------------------------------


class TestAdvanceTurn:
    @pytest.mark.asyncio
    async def test_advances_to_next(self):
        combatants = [
            _make_combatant(id=1, name="First", initiative_roll=20),
            _make_combatant(id=2, name="Second", initiative_roll=15),
            _make_combatant(id=3, name="Third", initiative_roll=10),
        ]
        encounter = _make_encounter(
            status=STATUS_ACTIVE,
            current_turn_index=0,
            round_number=1,
            combatants=combatants,
        )

        db = AsyncMock()
        with patch(
            "grug.encounter.get_encounter_by_id", new=AsyncMock(return_value=encounter)
        ):
            result_enc, next_c = await advance_turn(db, encounter_id=1)

        assert result_enc.current_turn_index == 1
        assert next_c.name == "Second"
        assert result_enc.round_number == 1

    @pytest.mark.asyncio
    async def test_wraps_to_next_round(self):
        combatants = [
            _make_combatant(id=1, name="First", initiative_roll=20),
            _make_combatant(id=2, name="Second", initiative_roll=10),
        ]
        encounter = _make_encounter(
            status=STATUS_ACTIVE,
            current_turn_index=1,  # at last combatant
            round_number=2,
            combatants=combatants,
        )

        db = AsyncMock()
        with patch(
            "grug.encounter.get_encounter_by_id", new=AsyncMock(return_value=encounter)
        ):
            result_enc, next_c = await advance_turn(db, encounter_id=1)

        assert result_enc.current_turn_index == 0
        assert result_enc.round_number == 3
        assert next_c.name == "First"

    @pytest.mark.asyncio
    async def test_not_active_raises(self):
        encounter = _make_encounter(status=STATUS_PREPARING)
        db = AsyncMock()
        with patch(
            "grug.encounter.get_encounter_by_id", new=AsyncMock(return_value=encounter)
        ):
            with pytest.raises(EncounterError, match="not active"):
                await advance_turn(db, encounter_id=1)

    @pytest.mark.asyncio
    async def test_missing_encounter_raises(self):
        db = AsyncMock()
        with patch(
            "grug.encounter.get_encounter_by_id", new=AsyncMock(return_value=None)
        ):
            with pytest.raises(EncounterError, match="Encounter not found"):
                await advance_turn(db, encounter_id=999)


# ---------------------------------------------------------------------------
# end_encounter
# ---------------------------------------------------------------------------


class TestEndEncounter:
    @pytest.mark.asyncio
    async def test_ends_active(self):
        encounter = _make_encounter(status=STATUS_ACTIVE)
        db = AsyncMock()
        with patch(
            "grug.encounter.get_encounter_by_id", new=AsyncMock(return_value=encounter)
        ):
            result = await end_encounter(db, encounter_id=1)

        assert result.status == STATUS_ENDED
        assert result.ended_at is not None

    @pytest.mark.asyncio
    async def test_ends_preparing(self):
        encounter = _make_encounter(status=STATUS_PREPARING)
        db = AsyncMock()
        with patch(
            "grug.encounter.get_encounter_by_id", new=AsyncMock(return_value=encounter)
        ):
            result = await end_encounter(db, encounter_id=1)

        assert result.status == STATUS_ENDED

    @pytest.mark.asyncio
    async def test_already_ended_is_idempotent(self):
        encounter = _make_encounter(status=STATUS_ENDED)
        db = AsyncMock()
        with patch(
            "grug.encounter.get_encounter_by_id", new=AsyncMock(return_value=encounter)
        ):
            result = await end_encounter(db, encounter_id=1)

        assert result.status == STATUS_ENDED


# ---------------------------------------------------------------------------
# format_initiative_order
# ---------------------------------------------------------------------------


class TestFormatInitiativeOrder:
    def test_basic_format(self):
        combatants = [
            _make_combatant(id=1, name="Fighter", initiative_roll=20, is_enemy=False),
            _make_combatant(id=2, name="Goblin", initiative_roll=15, is_enemy=True),
            _make_combatant(id=3, name="Wizard", initiative_roll=10, is_enemy=False),
        ]
        enc = _make_encounter(
            name="Battle",
            status=STATUS_ACTIVE,
            current_turn_index=0,
            round_number=1,
            combatants=combatants,
        )
        text = format_initiative_order(enc)

        assert "⚔️ Battle — Round 1" in text
        assert "▶" in text
        assert "Fighter" in text
        assert "[Enemy]" in text  # Goblin is enemy

    def test_current_turn_marker(self):
        combatants = [
            _make_combatant(id=1, name="Zara", initiative_roll=20),
            _make_combatant(id=2, name="Xander", initiative_roll=10),
        ]
        enc = _make_encounter(
            status=STATUS_ACTIVE,
            current_turn_index=1,
            combatants=combatants,
        )
        text = format_initiative_order(enc)
        lines = text.strip().split("\n")

        # The second combatant (index 1) should have the ▶ marker
        combatant_lines = [line for line in lines if "Zara" in line or "Xander" in line]
        assert not combatant_lines[0].strip().startswith("▶")
        assert combatant_lines[1].strip().startswith("▶")

    def test_empty_combatants(self):
        enc = _make_encounter(combatants=[])
        assert "No combatants" in format_initiative_order(enc)

    def test_preparing_no_marker(self):
        combatants = [
            _make_combatant(id=1, name="A", initiative_roll=10),
        ]
        enc = _make_encounter(status=STATUS_PREPARING, combatants=combatants)
        text = format_initiative_order(enc)
        assert "▶" not in text
