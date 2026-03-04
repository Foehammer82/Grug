"""Tests for the role-based access control permission helpers in api.deps."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# Helpers — build fake JWT payloads
# ---------------------------------------------------------------------------


def _user(user_id: str = "111", guilds: list[dict] | None = None) -> dict:
    """Return a minimal JWT-style user dict."""
    payload = {"sub": user_id, "id": user_id}
    if guilds is not None:
        payload["guilds"] = guilds
    return payload


def _guild(
    guild_id: str = "999",
    permissions: int | str = 0,
) -> dict:
    return {"id": guild_id, "name": "Test", "permissions": str(permissions)}


# ---------------------------------------------------------------------------
# is_super_admin / assert_super_admin
# ---------------------------------------------------------------------------


class TestSuperAdmin:
    def test_returns_true_when_user_in_env_list(self, monkeypatch):
        monkeypatch.setenv("GRUG_SUPER_ADMIN_IDS", "111,222")
        import grug.config.settings as s

        s.get_settings.cache_clear()
        from api.deps import is_super_admin

        assert is_super_admin(_user("111")) is True
        assert is_super_admin(_user("222")) is True

    def test_returns_false_when_user_not_in_env_list(self, monkeypatch):
        monkeypatch.setenv("GRUG_SUPER_ADMIN_IDS", "111")
        import grug.config.settings as s

        s.get_settings.cache_clear()
        from api.deps import is_super_admin

        assert is_super_admin(_user("999")) is False

    def test_returns_false_when_env_var_empty(self, monkeypatch):
        monkeypatch.setenv("GRUG_SUPER_ADMIN_IDS", "")
        import grug.config.settings as s

        s.get_settings.cache_clear()
        from api.deps import is_super_admin

        assert is_super_admin(_user("111")) is False

    async def test_assert_raises_403_for_non_super_admin(
        self, monkeypatch, mock_db_session
    ):
        monkeypatch.setenv("GRUG_SUPER_ADMIN_IDS", "111")
        import grug.config.settings as s

        s.get_settings.cache_clear()
        from api.deps import assert_super_admin

        mock_factory, mock_session = mock_db_session
        # User "999" not in DB either
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        with patch("api.deps.get_session_factory", return_value=mock_factory):
            with pytest.raises(HTTPException) as exc_info:
                await assert_super_admin(_user("999"))
        assert exc_info.value.status_code == 403

    async def test_assert_passes_for_super_admin(self, monkeypatch):
        monkeypatch.setenv("GRUG_SUPER_ADMIN_IDS", "42")
        import grug.config.settings as s

        s.get_settings.cache_clear()
        from api.deps import assert_super_admin

        # User "42" is in the env var — fast path, no DB check needed
        await assert_super_admin(_user("42"))  # should not raise


# ---------------------------------------------------------------------------
# has_can_invite
# ---------------------------------------------------------------------------


class TestCanInvite:
    @pytest.mark.asyncio
    async def test_super_admin_always_can_invite(self, monkeypatch):
        monkeypatch.setenv("GRUG_SUPER_ADMIN_IDS", "42")
        import grug.config.settings as s

        s.get_settings.cache_clear()
        from api.deps import has_can_invite

        assert await has_can_invite(_user("42")) is True

    @pytest.mark.asyncio
    async def test_can_invite_from_db(self, monkeypatch, mock_db_session):
        monkeypatch.setenv("GRUG_SUPER_ADMIN_IDS", "")
        import grug.config.settings as s

        s.get_settings.cache_clear()
        mock_factory, mock_session = mock_db_session

        # Simulate GrugUser with can_invite=True
        mock_grug_user = MagicMock(can_invite=True)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_grug_user
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("api.deps.get_session_factory", return_value=mock_factory):
            from api.deps import has_can_invite

            assert await has_can_invite(_user("555")) is True

    @pytest.mark.asyncio
    async def test_cannot_invite_when_not_in_db(self, monkeypatch, mock_db_session):
        monkeypatch.setenv("GRUG_SUPER_ADMIN_IDS", "")
        import grug.config.settings as s

        s.get_settings.cache_clear()
        mock_factory, mock_session = mock_db_session

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("api.deps.get_session_factory", return_value=mock_factory):
            from api.deps import has_can_invite

            assert await has_can_invite(_user("555")) is False


# ---------------------------------------------------------------------------
# is_guild_admin / assert_guild_admin
# ---------------------------------------------------------------------------


class TestIsGuildAdmin:
    @pytest.mark.asyncio
    async def test_super_admin_is_always_guild_admin(self, monkeypatch):
        monkeypatch.setenv("GRUG_SUPER_ADMIN_IDS", "42")
        import grug.config.settings as s

        s.get_settings.cache_clear()
        from api.deps import is_guild_admin

        user = _user("42", guilds=[])
        assert await is_guild_admin("999", user) is True

    @pytest.mark.asyncio
    async def test_discord_admin_perm_grants_access(self, monkeypatch):
        """JWT Discord ADMINISTRATOR bit no longer grants guild admin access.

        The ``permissions`` field was removed from the JWT to prevent stale
        permission escalation.  Only Grug super-admins and users with the
        grug-admin role have guild admin access.
        """
        monkeypatch.setenv("GRUG_SUPER_ADMIN_IDS", "")
        import grug.config.settings as s

        s.get_settings.cache_clear()
        from api.deps import is_guild_admin

        user = _user("555", guilds=[_guild("999", permissions=0x8)])
        with (
            patch(
                "api.deps._has_grug_admin_role",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "api.deps.is_super_admin_full",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            # JWT ADMINISTRATOR bit alone no longer grants access
            assert await is_guild_admin("999", user) is False

    @pytest.mark.asyncio
    async def test_grug_admin_role_grants_access(self, monkeypatch):
        monkeypatch.setenv("GRUG_SUPER_ADMIN_IDS", "")
        import grug.config.settings as s

        s.get_settings.cache_clear()
        from api.deps import is_guild_admin

        user = _user("555", guilds=[_guild("999", permissions=0)])
        with (
            patch(
                "api.deps._has_grug_admin_role",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "api.deps.is_super_admin_full",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            assert await is_guild_admin("999", user) is True

    @pytest.mark.asyncio
    async def test_no_admin_access(self, monkeypatch):
        monkeypatch.setenv("GRUG_SUPER_ADMIN_IDS", "")
        import grug.config.settings as s

        s.get_settings.cache_clear()
        from api.deps import is_guild_admin

        user = _user("555", guilds=[_guild("999", permissions=0)])
        with (
            patch(
                "api.deps._has_grug_admin_role",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "api.deps.is_super_admin_full",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            assert await is_guild_admin("999", user) is False

    @pytest.mark.asyncio
    async def test_assert_guild_admin_raises_403(self, monkeypatch):
        monkeypatch.setenv("GRUG_SUPER_ADMIN_IDS", "")
        import grug.config.settings as s

        s.get_settings.cache_clear()
        from api.deps import assert_guild_admin

        user = _user("555", guilds=[_guild("999", permissions=0)])
        with (
            patch(
                "api.deps._has_grug_admin_role",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "api.deps.is_super_admin_full",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await assert_guild_admin("999", user)
            assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# assert_guild_member
# ---------------------------------------------------------------------------


class TestAssertGuildMember:
    def setup_method(self):
        """Clear the member cache before each test to avoid state leakage."""
        import api.deps as deps

        deps._MEMBER_CACHE.clear()

    @pytest.mark.asyncio
    async def test_passes_for_member(self, monkeypatch):
        monkeypatch.setenv("GRUG_SUPER_ADMIN_IDS", "")
        import grug.config.settings as s

        s.get_settings.cache_clear()
        from api.deps import assert_guild_member

        user = _user()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)
        with (
            patch("api.deps.httpx.AsyncClient", return_value=mock_client),
            patch("api.deps.get_bot_token", return_value="fake-token"),
        ):
            await assert_guild_member("999", user)  # should not raise

    @pytest.mark.asyncio
    async def test_raises_403_for_non_member(self, monkeypatch):
        monkeypatch.setenv("GRUG_SUPER_ADMIN_IDS", "")
        import grug.config.settings as s

        s.get_settings.cache_clear()
        from api.deps import assert_guild_member

        user = _user()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_resp)
        with (
            patch("api.deps.httpx.AsyncClient", return_value=mock_client),
            patch("api.deps.get_bot_token", return_value="fake-token"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await assert_guild_member("999", user)
            assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_super_admin_bypasses_check(self, monkeypatch):
        monkeypatch.setenv("GRUG_SUPER_ADMIN_IDS", "42")
        import grug.config.settings as s

        s.get_settings.cache_clear()
        from api.deps import assert_guild_member

        user = _user("42")
        # No bot token needed — super-admins bypass the Discord check entirely
        await assert_guild_member("999", user)  # should not raise


# ---------------------------------------------------------------------------
# _check_role_match
# ---------------------------------------------------------------------------


class TestCheckRoleMatch:
    @pytest.mark.asyncio
    async def test_match_found(self, mock_db_session):
        mock_factory, mock_session = mock_db_session
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = 12345
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("api.deps.get_session_factory", return_value=mock_factory):
            from api.deps import _check_role_match

            assert await _check_role_match("999", ["12345", "6789"]) is True

    @pytest.mark.asyncio
    async def test_no_match(self, mock_db_session):
        mock_factory, mock_session = mock_db_session
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = 12345
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("api.deps.get_session_factory", return_value=mock_factory):
            from api.deps import _check_role_match

            assert await _check_role_match("999", ["6789"]) is False

    @pytest.mark.asyncio
    async def test_no_role_configured(self, mock_db_session):
        mock_factory, mock_session = mock_db_session
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("api.deps.get_session_factory", return_value=mock_factory):
            from api.deps import _check_role_match

            assert await _check_role_match("999", ["12345"]) is False


# ---------------------------------------------------------------------------
# Settings: grug_super_admin_ids parsing
# ---------------------------------------------------------------------------


class TestSuperAdminIdsParsing:
    def test_comma_separated(self, monkeypatch):
        monkeypatch.setenv("GRUG_SUPER_ADMIN_IDS", "111, 222 , 333")
        import grug.config.settings as s

        s.get_settings.cache_clear()
        settings = s.get_settings()
        assert settings.grug_super_admin_ids == ["111", "222", "333"]

    def test_single_value(self, monkeypatch):
        monkeypatch.setenv("GRUG_SUPER_ADMIN_IDS", "42")
        import grug.config.settings as s

        s.get_settings.cache_clear()
        settings = s.get_settings()
        assert settings.grug_super_admin_ids == ["42"]

    def test_empty_string(self, monkeypatch):
        monkeypatch.setenv("GRUG_SUPER_ADMIN_IDS", "")
        import grug.config.settings as s

        s.get_settings.cache_clear()
        settings = s.get_settings()
        assert settings.grug_super_admin_ids == []

    def test_not_set_defaults_empty(self, monkeypatch):
        # Use setenv("") rather than delenv so the OS env var overrides any
        # .env file value that may be present in the developer's local checkout.
        monkeypatch.setenv("GRUG_SUPER_ADMIN_IDS", "")
        import grug.config.settings as s

        s.get_settings.cache_clear()
        settings = s.get_settings()
        assert settings.grug_super_admin_ids == []
