"""Tests for passive score computation and the check_party_passives agent tool."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from grug.character.passives import compute_passive_score


# ---------------------------------------------------------------------------
# compute_passive_score — D&D 5e
# ---------------------------------------------------------------------------


class TestPassiveDnD5e:
    """D&D 5e passive score calculation."""

    def test_perception_from_explicit_field(self):
        """Uses the pre-computed passive_perception field when present."""
        sd = {"system": "dnd5e", "passive_perception": 14}
        assert compute_passive_score(sd, "perception") == 14

    def test_perception_from_skills_dict(self):
        """Falls back to 10 + skill modifier when passive_perception is absent."""
        sd = {"system": "dnd5e", "skills": {"perception": 4}}
        assert compute_passive_score(sd, "perception") == 14

    def test_insight(self):
        """Passive Insight = 10 + insight modifier."""
        sd = {"system": "dnd5e", "skills": {"insight": 2}}
        assert compute_passive_score(sd, "insight") == 12

    def test_investigation(self):
        """Passive Investigation = 10 + investigation modifier."""
        sd = {"system": "dnd5e", "skills": {"investigation": 5}}
        assert compute_passive_score(sd, "investigation") == 15

    def test_fallback_to_ability_score(self):
        """When skills dict is missing, derive from the governing ability score."""
        sd = {
            "system": "dnd5e",
            "ability_scores": {"WIS": 14},  # mod = +2
        }
        assert compute_passive_score(sd, "perception") == 12

    def test_negative_modifier(self):
        """Handles negative ability modifiers correctly."""
        sd = {
            "system": "dnd5e",
            "ability_scores": {"INT": 8},  # mod = -1
        }
        assert compute_passive_score(sd, "investigation") == 9

    def test_no_data_returns_none(self):
        """Returns None when there's nothing to compute from."""
        sd = {"system": "dnd5e"}
        assert compute_passive_score(sd, "stealth") is None

    def test_empty_dict_returns_none(self):
        """Returns None for an empty dict."""
        assert compute_passive_score({}, "perception") is None

    def test_none_returns_none(self):
        """Returns None for None input."""
        assert compute_passive_score(None, "perception") is None

    def test_case_insensitive(self):
        """Skill name is case-insensitive."""
        sd = {"system": "dnd5e", "skills": {"perception": 3}}
        assert compute_passive_score(sd, "Perception") == 13
        assert compute_passive_score(sd, "PERCEPTION") == 13

    def test_space_to_underscore(self):
        """Spaces in skill names are converted to underscores."""
        sd = {"system": "dnd5e", "skills": {"sleight_of_hand": 6}}
        assert compute_passive_score(sd, "sleight of hand") == 16

    def test_passive_perception_preferred_over_skills(self):
        """Pre-computed passive_perception takes precedence over skills dict."""
        sd = {
            "system": "dnd5e",
            "passive_perception": 15,
            "skills": {"perception": 3},
        }
        assert compute_passive_score(sd, "perception") == 15


# ---------------------------------------------------------------------------
# compute_passive_score — PF2e
# ---------------------------------------------------------------------------


class TestPassivePF2e:
    """PF2e passive DC computation."""

    def test_perception_trained(self):
        """Trained perception: 10 + WIS_mod + level + rank."""
        sd = {
            "system": "pf2e",
            "level": 5,
            "ability_scores": {"WIS": 14},  # mod = +2
            "perception": 4,  # Expert rank
        }
        # 10 + 2 + (5 + 4) = 21
        assert compute_passive_score(sd, "perception") == 21

    def test_perception_untrained(self):
        """Untrained perception: 10 + WIS_mod (no level added)."""
        sd = {
            "system": "pf2e",
            "level": 5,
            "ability_scores": {"WIS": 12},  # mod = +1
            "perception": 0,
        }
        # 10 + 1 + 0 = 11
        assert compute_passive_score(sd, "perception") == 11

    def test_perception_from_proficiencies(self):
        """Falls back to proficiencies dict when top-level perception is absent."""
        sd = {
            "system": "pf2e",
            "level": 3,
            "ability_scores": {"WIS": 16},  # mod = +3
            "proficiencies": {"perception": 2},  # Trained
        }
        # 10 + 3 + (3 + 2) = 18
        assert compute_passive_score(sd, "perception") == 18

    def test_stealth_trained(self):
        """Trained stealth: 10 + DEX_mod + level + rank."""
        sd = {
            "system": "pf2e",
            "level": 7,
            "ability_scores": {"DEX": 18},  # mod = +4
            "proficiencies": {"stealth": 4},  # Expert
        }
        # 10 + 4 + (7 + 4) = 25
        assert compute_passive_score(sd, "perception") is None  # no perception data
        assert compute_passive_score(sd, "stealth") == 25

    def test_missing_level_returns_none(self):
        """Returns None when level is missing."""
        sd = {
            "system": "pf2e",
            "ability_scores": {"WIS": 14},
            "perception": 2,
        }
        assert compute_passive_score(sd, "perception") is None

    def test_missing_ability_score_uses_zero(self):
        """Uses 0 ability modifier when score is missing."""
        sd = {
            "system": "pf2e",
            "level": 5,
            "perception": 2,  # Trained
        }
        # 10 + 0 + (5 + 2) = 17
        assert compute_passive_score(sd, "perception") == 17

    def test_legendary_perception(self):
        """Legendary rank (8) is handled correctly."""
        sd = {
            "system": "pf2e",
            "level": 15,
            "ability_scores": {"WIS": 20},  # mod = +5
            "perception": 8,  # Legendary
        }
        # 10 + 5 + (15 + 8) = 38
        assert compute_passive_score(sd, "perception") == 38

    def test_unknown_skill_returns_none(self):
        """Returns None for a skill not in the PF2e mapping."""
        sd = {"system": "pf2e", "level": 5, "ability_scores": {"WIS": 14}}
        assert compute_passive_score(sd, "xyzzy") is None


# ---------------------------------------------------------------------------
# compute_passive_score — Unknown system
# ---------------------------------------------------------------------------


class TestPassiveUnknownSystem:
    """Unknown/homebrew system returns None (can't calculate)."""

    def test_unknown_system(self):
        sd = {"system": "unknown", "skills": {"perception": 5}}
        assert compute_passive_score(sd, "perception") is None


# ---------------------------------------------------------------------------
# check_party_passives agent tool
# ---------------------------------------------------------------------------


def _make_character(name, structured_data, owner_id=100):
    """Create a mock Character ORM object."""
    c = MagicMock()
    c.name = name
    c.structured_data = structured_data
    c.owner_discord_user_id = owner_id
    return c


@pytest.mark.asyncio
async def test_check_party_passives_gm_with_dc(monkeypatch):
    """GM gets pass/fail results when checking against a DC."""
    monkeypatch.setenv("GRUG_SUPER_ADMIN_IDS", "")
    import grug.config.settings as s

    s.get_settings.cache_clear()

    from grug.agent.core import GrugDeps

    deps = GrugDeps(
        guild_id=1, channel_id=2, user_id=42, username="gm", campaign_id=10
    )
    ctx = MagicMock()
    ctx.deps = deps

    campaign = MagicMock()
    campaign.gm_discord_user_id = 42  # requesting user IS the GM

    chars = [
        _make_character(
            "Gandalf", {"system": "dnd5e", "passive_perception": 18}, owner_id=100
        ),
        _make_character(
            "Frodo", {"system": "dnd5e", "skills": {"perception": 2}}, owner_id=101
        ),
    ]

    # Mock DB: first query returns campaign, second returns characters.
    call_count = 0

    async def _mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            result.scalar_one_or_none.return_value = campaign
        else:
            scalars_mock = MagicMock()
            scalars_mock.all.return_value = chars
            result.scalars.return_value = scalars_mock
        return result

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=_mock_execute)

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch(
        "grug.db.session.get_session_factory",
        return_value=mock_factory,
    ):
        # Import the tool function after patching
        from grug.agent.tools.campaign_tools import register_campaign_tools
        from pydantic_ai import Agent

        agent = Agent(
            "test",
            deps_type=GrugDeps,
            output_type=str,
        )
        register_campaign_tools(agent)

        # Find the check_party_passives tool
        tools = agent._function_toolset.tools
        tool_fn = tools["check_party_passives"]
        result = await tool_fn.function(ctx, skill="perception", dc=15)

    assert "Passive Perception" in result
    assert "DC 15" in result
    assert "Gandalf" in result
    assert "18" in result
    assert "✅ pass" in result
    assert "Frodo" in result
    assert "12" in result  # 10 + 2
    assert "❌ fail" in result


@pytest.mark.asyncio
async def test_check_party_passives_non_gm_denied(monkeypatch):
    """Non-GM, non-admin users are denied access."""
    monkeypatch.setenv("GRUG_SUPER_ADMIN_IDS", "")
    import grug.config.settings as s

    s.get_settings.cache_clear()

    from grug.agent.core import GrugDeps

    deps = GrugDeps(
        guild_id=1, channel_id=2, user_id=999, username="player", campaign_id=10
    )
    ctx = MagicMock()
    ctx.deps = deps

    campaign = MagicMock()
    campaign.gm_discord_user_id = 42  # someone else is the GM

    # _is_admin makes two DB queries (GrugUser, GuildConfig) → both return None.
    # Then check_party_passives queries Campaign → return the campaign mock.
    call_count = 0

    async def _mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count <= 2:
            # _is_admin queries for GrugUser and GuildConfig — not found.
            result.scalar_one_or_none.return_value = None
        else:
            # check_party_passives queries for Campaign.
            result.scalar_one_or_none.return_value = campaign
        return result

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=_mock_execute)

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch(
        "grug.db.session.get_session_factory",
        return_value=mock_factory,
    ):
        from grug.agent.tools.campaign_tools import register_campaign_tools
        from pydantic_ai import Agent

        agent = Agent("test", deps_type=GrugDeps, output_type=str)
        register_campaign_tools(agent)

        tools = agent._function_toolset.tools
        tool_fn = tools["check_party_passives"]
        result = await tool_fn.function(ctx, skill="perception", dc=15)

    assert "Only the GM or an admin" in result


@pytest.mark.asyncio
async def test_check_party_passives_no_campaign():
    """Returns a helpful message when no campaign is linked."""
    from grug.agent.core import GrugDeps

    deps = GrugDeps(
        guild_id=1, channel_id=2, user_id=42, username="gm", campaign_id=None
    )
    ctx = MagicMock()
    ctx.deps = deps

    from grug.agent.tools.campaign_tools import register_campaign_tools
    from pydantic_ai import Agent

    agent = Agent("test", deps_type=GrugDeps, output_type=str)
    register_campaign_tools(agent)

    tools = agent._function_toolset.tools
    tool_fn = tools["check_party_passives"]
    result = await tool_fn.function(ctx, skill="perception", dc=15)

    assert "No campaign" in result


@pytest.mark.asyncio
async def test_check_party_passives_without_dc(monkeypatch):
    """Without a DC, lists scores without pass/fail indicators."""
    monkeypatch.setenv("GRUG_SUPER_ADMIN_IDS", "42")
    import grug.config.settings as s

    s.get_settings.cache_clear()

    from grug.agent.core import GrugDeps

    deps = GrugDeps(
        guild_id=1, channel_id=2, user_id=42, username="admin", campaign_id=10
    )
    ctx = MagicMock()
    ctx.deps = deps

    campaign = MagicMock()
    campaign.gm_discord_user_id = 99

    chars = [
        _make_character(
            "Legolas", {"system": "dnd5e", "passive_perception": 20}, owner_id=200
        ),
    ]

    call_count = 0

    async def _mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        result = MagicMock()
        if call_count == 1:
            result.scalar_one_or_none.return_value = campaign
        else:
            scalars_mock = MagicMock()
            scalars_mock.all.return_value = chars
            result.scalars.return_value = scalars_mock
        return result

    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(side_effect=_mock_execute)

    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch(
        "grug.db.session.get_session_factory",
        return_value=mock_factory,
    ):
        from grug.agent.tools.campaign_tools import register_campaign_tools
        from pydantic_ai import Agent

        agent = Agent("test", deps_type=GrugDeps, output_type=str)
        register_campaign_tools(agent)

        tools = agent._function_toolset.tools
        tool_fn = tools["check_party_passives"]
        result = await tool_fn.function(ctx, skill="perception", dc=None)

    assert "Passive Perception" in result
    assert "Legolas" in result
    assert "20" in result
    assert "✅" not in result
    assert "❌" not in result
