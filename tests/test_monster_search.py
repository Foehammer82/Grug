"""Tests for the monster search service (grug.monster_search)."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from grug.monster_search import (
    MonsterResult,
    _ability_mod,
    search_monsters,
    search_monsters_5e,
    search_monsters_pf2e,
)


# ---------------------------------------------------------------------------
# _ability_mod
# ---------------------------------------------------------------------------


class TestAbilityMod:
    def test_even_score(self):
        assert _ability_mod(10) == 0
        assert _ability_mod(16) == 3
        assert _ability_mod(20) == 5

    def test_odd_score(self):
        assert _ability_mod(11) == 0
        assert _ability_mod(15) == 2
        assert _ability_mod(9) == -1

    def test_low_score(self):
        assert _ability_mod(1) == -5
        assert _ability_mod(3) == -4


# ---------------------------------------------------------------------------
# search_monsters_5e
# ---------------------------------------------------------------------------


class TestSearchMonsters5e:
    @pytest.mark.asyncio
    async def test_returns_parsed_results(self):
        """A successful search returns structured MonsterResult objects."""
        list_response = MagicMock()
        list_response.status_code = 200
        list_response.json.return_value = {
            "results": [{"name": "Goblin", "url": "/api/2014/monsters/goblin"}]
        }

        detail_response = MagicMock()
        detail_response.status_code = 200
        detail_response.json.return_value = {
            "name": "Goblin",
            "hit_points": 7,
            "armor_class": [{"value": 15}],
            "dexterity": 14,
            "challenge_rating": 0.25,
            "size": "Small",
            "type": "humanoid",
            "proficiencies": [
                {"proficiency": {"name": "Saving Throw: DEX"}, "value": 4},
            ],
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[list_response, detail_response])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("grug.monster_search.httpx.AsyncClient", return_value=mock_client):
            results = await search_monsters_5e("goblin", limit=5)

        assert len(results) == 1
        r = results[0]
        assert r.name == "Goblin"
        assert r.source == "srd_5e"
        assert r.system == "dnd5e"
        assert r.hp == 7
        assert r.ac == 15
        assert r.initiative_modifier == 2  # DEX 14 → +2
        assert r.cr == "0.25"
        assert r.save_modifiers == {"DEX": 4}

    @pytest.mark.asyncio
    async def test_handles_api_failure(self):
        """Returns empty list when the API returns non-200."""
        list_response = MagicMock()
        list_response.status_code = 500

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=list_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("grug.monster_search.httpx.AsyncClient", return_value=mock_client):
            results = await search_monsters_5e("goblin")

        assert results == []

    @pytest.mark.asyncio
    async def test_handles_missing_fields(self):
        """Gracefully handles monsters with missing optional fields."""
        list_response = MagicMock()
        list_response.status_code = 200
        list_response.json.return_value = {
            "results": [{"name": "Blob", "url": "/api/2014/monsters/blob"}]
        }

        detail_response = MagicMock()
        detail_response.status_code = 200
        detail_response.json.return_value = {
            "name": "Blob",
            "proficiencies": [],
        }

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[list_response, detail_response])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("grug.monster_search.httpx.AsyncClient", return_value=mock_client):
            results = await search_monsters_5e("blob")

        assert len(results) == 1
        r = results[0]
        assert r.name == "Blob"
        assert r.hp is None
        assert r.ac is None
        assert r.initiative_modifier is None
        assert r.save_modifiers is None


# ---------------------------------------------------------------------------
# search_monsters_pf2e
# ---------------------------------------------------------------------------


class TestSearchMonstersPf2e:
    @pytest.mark.asyncio
    async def test_returns_parsed_results(self):
        """A successful PF2e search returns structured results."""
        es_response = MagicMock()
        es_response.status_code = 200
        es_response.json.return_value = {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "name": "Kobold Warrior",
                            "hp": 8,
                            "ac": 16,
                            "perception": 3,
                            "level": -1,
                            "size": "Small",
                            "creature_type": "Humanoid",
                            "fort_save": 2,
                            "ref_save": 5,
                            "will_save": 3,
                        }
                    }
                ]
            }
        }

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=es_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("grug.monster_search.httpx.AsyncClient", return_value=mock_client):
            results = await search_monsters_pf2e("kobold")

        assert len(results) == 1
        r = results[0]
        assert r.name == "Kobold Warrior"
        assert r.source == "aon_pf2e"
        assert r.system == "pf2e"
        assert r.hp == 8
        assert r.ac == 16
        assert r.initiative_modifier == 3  # Perception
        assert r.cr == "Level -1"
        assert r.save_modifiers == {"CON": 2, "DEX": 5, "WIS": 3}

    @pytest.mark.asyncio
    async def test_handles_api_failure(self):
        """Returns empty list when ES returns non-200."""
        es_response = MagicMock()
        es_response.status_code = 500

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=es_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("grug.monster_search.httpx.AsyncClient", return_value=mock_client):
            results = await search_monsters_pf2e("goblin")

        assert results == []


# ---------------------------------------------------------------------------
# search_monsters (dispatcher)
# ---------------------------------------------------------------------------


class TestSearchMonsters:
    @pytest.mark.asyncio
    async def test_searches_both_systems_by_default(self):
        """With no system filter, searches both 5e and PF2e."""
        with (
            patch(
                "grug.monster_search.search_monsters_5e", new_callable=AsyncMock
            ) as m5e,
            patch(
                "grug.monster_search.search_monsters_pf2e", new_callable=AsyncMock
            ) as mpf2e,
        ):
            m5e.return_value = [
                MonsterResult(name="Goblin", source="srd_5e", system="dnd5e", hp=7)
            ]
            mpf2e.return_value = [
                MonsterResult(
                    name="Goblin Warrior", source="aon_pf2e", system="pf2e", hp=6
                )
            ]

            results = await search_monsters("goblin")

        assert len(results) == 2
        assert results[0].source == "srd_5e"
        assert results[1].source == "aon_pf2e"
        m5e.assert_awaited_once()
        mpf2e.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_filters_to_5e_only(self):
        """System filter 'dnd5e' only searches 5e."""
        with (
            patch(
                "grug.monster_search.search_monsters_5e", new_callable=AsyncMock
            ) as m5e,
            patch(
                "grug.monster_search.search_monsters_pf2e", new_callable=AsyncMock
            ) as mpf2e,
        ):
            m5e.return_value = []
            mpf2e.return_value = []

            await search_monsters("goblin", system="dnd5e")

        m5e.assert_awaited_once()
        mpf2e.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_filters_to_pf2e_only(self):
        """System filter 'pf2e' only searches PF2e."""
        with (
            patch(
                "grug.monster_search.search_monsters_5e", new_callable=AsyncMock
            ) as m5e,
            patch(
                "grug.monster_search.search_monsters_pf2e", new_callable=AsyncMock
            ) as mpf2e,
        ):
            m5e.return_value = []
            mpf2e.return_value = []

            await search_monsters("goblin", system="pf2e")

        m5e.assert_not_awaited()
        mpf2e.assert_awaited_once()
