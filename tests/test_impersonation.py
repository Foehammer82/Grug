"""Tests for the super-admin impersonation feature."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from api.auth import create_jwt, decode_jwt


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _admin(user_id: str = "42") -> dict:
    """Return a minimal JWT-style user dict for a super-admin."""
    return {
        "sub": user_id,
        "id": user_id,
        "username": "admin",
        "discriminator": "0",
        "avatar": "abc",
    }


def _impersonating_user(admin_id: str = "42", target_id: str = "999") -> dict:
    """Return a JWT-style user dict representing an active impersonation session."""
    return {
        "sub": target_id,
        "id": target_id,
        "username": "target_user",
        "discriminator": "0",
        "avatar": None,
        "impersonator": {
            "sub": admin_id,
            "username": "admin",
            "discriminator": "0",
            "avatar": "abc",
        },
    }


# ---------------------------------------------------------------------------
# JWT impersonation claim round-trip
# ---------------------------------------------------------------------------


class TestImpersonationJWT:
    def test_jwt_preserves_impersonator_claim(self):
        """Impersonator claim should survive JWT encode/decode round-trip."""
        payload = {
            "sub": "999",
            "username": "target",
            "discriminator": "0",
            "avatar": None,
            "impersonator": {
                "sub": "42",
                "username": "admin",
                "discriminator": "0",
                "avatar": "abc",
            },
        }
        token = create_jwt(payload)
        decoded = decode_jwt(token)
        assert decoded["sub"] == "999"
        assert decoded["impersonator"]["sub"] == "42"
        assert decoded["impersonator"]["username"] == "admin"

    def test_jwt_without_impersonator(self):
        """Normal JWT should not have impersonator claim."""
        payload = {"sub": "42", "username": "admin", "discriminator": "0"}
        token = create_jwt(payload)
        decoded = decode_jwt(token)
        assert "impersonator" not in decoded


# ---------------------------------------------------------------------------
# Start impersonation
# ---------------------------------------------------------------------------


class TestStartImpersonation:
    @pytest.mark.asyncio
    async def test_requires_super_admin(self, monkeypatch, mock_db_session):
        """Non-super-admin should get 403."""
        monkeypatch.setenv("GRUG_SUPER_ADMIN_IDS", "42")
        import grug.config.settings as s

        s.get_settings.cache_clear()
        from api.routes.admin import start_impersonation

        mock_factory, mock_session = mock_db_session
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        user = {"sub": "999", "id": "999", "username": "regular", "discriminator": "0"}
        response = MagicMock()

        with patch("api.deps.get_session_factory", return_value=mock_factory):
            with pytest.raises(HTTPException) as exc_info:
                await start_impersonation("123", response, user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_cannot_impersonate_self(self, monkeypatch):
        """Super-admin should not be able to impersonate themselves."""
        monkeypatch.setenv("GRUG_SUPER_ADMIN_IDS", "42")
        import grug.config.settings as s

        s.get_settings.cache_clear()
        from api.routes.admin import start_impersonation

        user = _admin("42")
        response = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await start_impersonation("42", response, user)
        assert exc_info.value.status_code == 400
        assert "yourself" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_prevents_nested_impersonation(self, monkeypatch):
        """Cannot start impersonation while already impersonating."""
        monkeypatch.setenv("GRUG_SUPER_ADMIN_IDS", "42")
        import grug.config.settings as s

        s.get_settings.cache_clear()
        from api.routes.admin import start_impersonation

        user = _impersonating_user("42", "999")
        response = MagicMock()

        # assert_super_admin will fail because the impersonating user's "sub"
        # is "999" which is not a super admin; the impersonator check happens
        # after that in the real flow. But the function checks for
        # impersonator AFTER assert_super_admin, so with "999" not being a
        # super admin this will raise 403 first.
        # We need to make the assert_super_admin pass first.
        with patch("api.routes.admin.assert_super_admin", new_callable=AsyncMock):
            with pytest.raises(HTTPException) as exc_info:
                await start_impersonation("888", response, user)
        assert exc_info.value.status_code == 400
        assert "already" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_successful_impersonation_sets_cookie(self, monkeypatch):
        """Successful impersonation should set session cookie with impersonator claim."""
        monkeypatch.setenv("GRUG_SUPER_ADMIN_IDS", "42")
        import grug.config.settings as s

        s.get_settings.cache_clear()
        from api.routes.admin import start_impersonation

        user = _admin("42")
        response = MagicMock()

        # Mock the Discord API call
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "id": "999",
            "username": "target_user",
            "discriminator": "0",
            "avatar": None,
        }
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)
        mock_http.get = AsyncMock(return_value=mock_resp)

        with (
            patch("api.routes.admin.httpx.AsyncClient", return_value=mock_http),
            patch("api.routes.admin.get_bot_token", return_value="fake-token"),
        ):
            result = await start_impersonation("999", response, user)

        assert result["status"] == "ok"
        assert result["impersonating"] == "target_user"
        response.set_cookie.assert_called_once()
        cookie_args = response.set_cookie.call_args
        assert cookie_args.kwargs["key"] == "session"
        assert cookie_args.kwargs["httponly"] is True

        # Verify the JWT contains impersonator claim
        jwt_token = cookie_args.kwargs["value"]
        decoded = decode_jwt(jwt_token)
        assert decoded["sub"] == "999"
        assert decoded["impersonator"]["sub"] == "42"
        assert decoded["impersonator"]["username"] == "admin"

    @pytest.mark.asyncio
    async def test_target_user_not_found(self, monkeypatch):
        """Should return 404 when target Discord user doesn't exist."""
        monkeypatch.setenv("GRUG_SUPER_ADMIN_IDS", "42")
        import grug.config.settings as s

        s.get_settings.cache_clear()
        from api.routes.admin import start_impersonation

        user = _admin("42")
        response = MagicMock()

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_http = AsyncMock()
        mock_http.__aenter__ = AsyncMock(return_value=mock_http)
        mock_http.__aexit__ = AsyncMock(return_value=None)
        mock_http.get = AsyncMock(return_value=mock_resp)

        with (
            patch("api.routes.admin.httpx.AsyncClient", return_value=mock_http),
            patch("api.routes.admin.get_bot_token", return_value="fake-token"),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await start_impersonation("999", response, user)
        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Stop impersonation
# ---------------------------------------------------------------------------


class TestStopImpersonation:
    @pytest.mark.asyncio
    async def test_stop_when_not_impersonating(self):
        """Should raise 400 when not impersonating."""
        from api.routes.admin import stop_impersonation

        user = _admin("42")
        response = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            await stop_impersonation(response, user)
        assert exc_info.value.status_code == 400
        assert "not currently" in str(exc_info.value.detail).lower()

    @pytest.mark.asyncio
    async def test_successful_stop(self, monkeypatch):
        """Should restore original admin session."""
        monkeypatch.setenv("GRUG_SUPER_ADMIN_IDS", "42")
        import grug.config.settings as s

        s.get_settings.cache_clear()
        from api.routes.admin import stop_impersonation

        user = _impersonating_user("42", "999")
        response = MagicMock()

        result = await stop_impersonation(response, user)

        assert result["status"] == "ok"
        assert result["restored"] == "admin"
        response.set_cookie.assert_called_once()
        cookie_args = response.set_cookie.call_args
        jwt_token = cookie_args.kwargs["value"]
        decoded = decode_jwt(jwt_token)
        assert decoded["sub"] == "42"
        assert "impersonator" not in decoded

    @pytest.mark.asyncio
    async def test_stop_fails_if_no_longer_super_admin(
        self, monkeypatch, mock_db_session
    ):
        """Should raise 403 if original user lost super-admin status."""
        monkeypatch.setenv("GRUG_SUPER_ADMIN_IDS", "")
        import grug.config.settings as s

        s.get_settings.cache_clear()
        from api.routes.admin import stop_impersonation

        mock_factory, mock_session = mock_db_session
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        user = _impersonating_user("42", "999")
        response = MagicMock()

        with patch("api.deps.get_session_factory", return_value=mock_factory):
            with pytest.raises(HTTPException) as exc_info:
                await stop_impersonation(response, user)
        assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# /auth/me with impersonation
# ---------------------------------------------------------------------------


class TestAuthMeImpersonation:
    @pytest.mark.asyncio
    async def test_me_returns_impersonation_info(self, monkeypatch, mock_db_session):
        """When impersonating, /auth/me should include impersonation metadata."""
        monkeypatch.setenv("GRUG_SUPER_ADMIN_IDS", "")
        import grug.config.settings as s

        s.get_settings.cache_clear()
        from api.routes.auth import get_me

        mock_factory, mock_session = mock_db_session
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        user = _impersonating_user("42", "999")

        with patch("api.deps.get_session_factory", return_value=mock_factory):
            result = await get_me(user)

        assert result.impersonating is True
        assert result.impersonator_id == "42"
        assert result.impersonator_username == "admin"
        assert result.id == "999"

    @pytest.mark.asyncio
    async def test_me_without_impersonation(self, monkeypatch):
        """Normal user should have impersonating=False."""
        monkeypatch.setenv("GRUG_SUPER_ADMIN_IDS", "42")
        import grug.config.settings as s

        s.get_settings.cache_clear()
        from api.routes.auth import get_me

        user = _admin("42")
        result = await get_me(user)

        assert result.impersonating is False
        assert result.impersonator_id is None
        assert result.impersonator_username is None
