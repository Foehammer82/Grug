"""Tests for the loot generation module (grug/loot.py)."""

import time

from grug.loot import (
    TREASURE_TABLE,
    AoNItem,
    _ITEM_CACHE_TTL,
    _item_cache,
    _item_cache_get,
    _item_cache_key,
    _item_cache_set,
    format_loot_table,
    format_treasure_table,
    get_treasure_budget,
    pick_random_items,
    _ItemSlot,
)


class TestTreasureTable:
    """Verify the static treasure-by-level data."""

    def test_table_has_all_levels(self):
        """Table covers levels 1–20."""
        assert set(TREASURE_TABLE.keys()) == set(range(1, 21))

    def test_level_1_row(self):
        row = TREASURE_TABLE[1]
        assert row.party_level == 1
        assert row.currency_gp == 40
        assert row.extra_currency_per_pc == 10
        # 2 permanent item slots
        assert len(row.permanent_items) == 2
        # 2 consumable slots
        assert len(row.consumables) == 2

    def test_level_20_row(self):
        row = TREASURE_TABLE[20]
        assert row.party_level == 20
        assert row.currency_gp == 140_000
        assert row.extra_currency_per_pc == 35_000
        # Level 20 has a single permanent slot of 4x level-20 items
        assert len(row.permanent_items) == 1
        assert row.permanent_items[0].count == 4
        assert row.permanent_items[0].item_level == 20

    def test_currency_increases_with_level(self):
        """Currency should always increase as level goes up."""
        prev_gp = 0
        for level in range(1, 21):
            row = TREASURE_TABLE[level]
            assert row.currency_gp > prev_gp, f"Level {level} currency <= level {level - 1}"
            prev_gp = row.currency_gp


class TestGetTreasureBudget:
    def test_valid_level(self):
        row = get_treasure_budget(5)
        assert row is not None
        assert row.party_level == 5

    def test_invalid_level_returns_none(self):
        assert get_treasure_budget(0) is None
        assert get_treasure_budget(21) is None
        assert get_treasure_budget(-1) is None


class TestFormatTreasureTable:
    def test_basic_formatting(self):
        row = TREASURE_TABLE[3]
        text = format_treasure_table(row, party_size=4)
        assert "Party Level 3" in text
        assert "party of 4" in text
        assert "Permanent Items" in text
        assert "Consumables" in text
        assert "Currency" in text
        assert "120 gp" in text

    def test_extra_pcs_currency(self):
        row = TREASURE_TABLE[3]
        text = format_treasure_table(row, party_size=6)
        # 120 + 30*2 = 180
        assert "180 gp" in text
        assert "extra PCs" in text

    def test_party_of_4_no_extra(self):
        row = TREASURE_TABLE[3]
        text = format_treasure_table(row, party_size=4)
        assert "extra PCs" not in text


class TestPickRandomItems:
    def test_picks_correct_count(self):
        slots = (_ItemSlot(item_level=3, count=2), _ItemSlot(item_level=2, count=1))
        items_by_level = {
            3: [
                AoNItem(name="Sword +1", item_level=3),
                AoNItem(name="Shield +1", item_level=3),
                AoNItem(name="Armor +1", item_level=3),
            ],
            2: [
                AoNItem(name="Healing Potion", item_level=2),
            ],
        }
        picked = pick_random_items(slots, items_by_level)
        assert len(picked) == 3  # 2 + 1

    def test_empty_pool_creates_placeholders(self):
        slots = (_ItemSlot(item_level=5, count=2),)
        items_by_level = {}  # nothing available
        picked = pick_random_items(slots, items_by_level)
        assert len(picked) == 2
        for item in picked:
            assert "Level 5" in item.name
            assert "aonprd.com" in item.url

    def test_small_pool_allows_duplicates(self):
        slots = (_ItemSlot(item_level=3, count=3),)
        items_by_level = {
            3: [AoNItem(name="Only Item", item_level=3)],
        }
        picked = pick_random_items(slots, items_by_level)
        assert len(picked) == 3
        assert all(p.name == "Only Item" for p in picked)


class TestFormatLootTable:
    def test_includes_all_sections(self):
        permanent = [
            AoNItem(name="Flaming Sword", item_level=5, price="160 gp", item_type="Weapon"),
        ]
        consumable = [
            AoNItem(name="Healing Potion", item_level=3, price="12 gp", item_type="Potion"),
        ]
        text = format_loot_table(5, 4, permanent, consumable, 320)
        assert "Loot Bundle" in text
        assert "Level 5" in text
        assert "Permanent Items" in text
        assert "Flaming Sword" in text
        assert "Consumables" in text
        assert "Healing Potion" in text
        assert "320 gp" in text

    def test_includes_rarity_for_uncommon(self):
        items = [
            AoNItem(name="Rare Gem", item_level=3, rarity="Uncommon"),
        ]
        text = format_loot_table(3, 4, items, [], 120)
        assert "[Uncommon]" in text

    def test_omits_rarity_for_common(self):
        items = [
            AoNItem(name="Basic Sword", item_level=3, rarity="Common"),
        ]
        text = format_loot_table(3, 4, items, [], 120)
        assert "[Common]" not in text

    def test_includes_aon_reference_url(self):
        text = format_loot_table(5, 4, [], [], 320)
        assert "2e.aonprd.com/Rules.aspx?ID=2656" in text


class TestItemCache:
    """Verify the in-memory TTL cache for AoN item searches."""

    def setup_method(self):
        """Clear the cache before each test."""
        _item_cache.clear()

    def test_cache_key_format(self):
        key = _item_cache_key(5, "permanent", 20)
        assert key == "5|permanent|20"

    def test_cache_miss_returns_none(self):
        assert _item_cache_get("nonexistent") is None

    def test_cache_set_and_get(self):
        items = [AoNItem(name="Sword", item_level=3)]
        _item_cache_set("test_key", items)
        result = _item_cache_get("test_key")
        assert result is not None
        assert len(result) == 1
        assert result[0].name == "Sword"

    def test_cache_expired_returns_none(self, monkeypatch):
        items = [AoNItem(name="Expired Item", item_level=1)]
        _item_cache_set("exp_key", items)
        # Confirm it's there
        assert _item_cache_get("exp_key") is not None
        # Fast-forward past TTL
        future = time.monotonic() + _ITEM_CACHE_TTL + 1
        monkeypatch.setattr(time, "monotonic", lambda: future)
        assert _item_cache_get("exp_key") is None

    def test_cache_evicts_expired_on_overflow(self, monkeypatch):
        # Fill cache to max
        from grug.loot import _ITEM_CACHE_MAX

        base_time = time.monotonic()
        for i in range(_ITEM_CACHE_MAX):
            _item_cache[f"old_{i}"] = ([], base_time - 1)  # already expired

        # Adding one more should trigger eviction
        monkeypatch.setattr(time, "monotonic", lambda: base_time)
        _item_cache_set("new_key", [AoNItem(name="New", item_level=1)])
        assert "new_key" in _item_cache
        # All expired entries should be removed
        assert len(_item_cache) <= 1
