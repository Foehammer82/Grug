from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from grug.auth import AdminAuth, create_access_token


@pytest.fixture
def admin_auth(settings):
    return AdminAuth(secret_key=settings.security_key.get_secret_value())


@pytest.mark.asyncio
async def test_admin_auth_login_expected_success(admin_auth, settings):
    mock_good_login_request = MagicMock()
    mock_good_login_request.form = AsyncMock(
        return_value={"username": settings.admin_user, "password": settings.admin_password.get_secret_value()}
    )

    assert await admin_auth.login(mock_good_login_request) is True


@pytest.mark.asyncio
async def test_admin_auth_login_expected_failure(admin_auth, settings):
    mock_bad_login_request = MagicMock()
    mock_bad_login_request.form = AsyncMock(return_value={"username": settings.admin_user, "password": "bad_password"})

    assert await admin_auth.login(mock_bad_login_request) is False


@pytest.mark.asyncio
async def test_admin_auth_logout(admin_auth):
    mock_logout_request = MagicMock()

    assert await admin_auth.logout(mock_logout_request) is True
    assert mock_logout_request.session.clear.called


@pytest.mark.asyncio
async def test_admin_auth_authenticate_expected_success(admin_auth, settings):
    mock_authenticated_request = MagicMock()
    mock_authenticated_request.session = {"token": create_access_token(settings.admin_user)}

    assert await admin_auth.authenticate(mock_authenticated_request) is True


@pytest.mark.asyncio
async def test_admin_auth_authenticate_expected_failure(admin_auth, settings):
    mock_unauthenticated_request = MagicMock()
    mock_unauthenticated_request.session = {}

    assert await admin_auth.authenticate(mock_unauthenticated_request) is False


@pytest.mark.asyncio
async def test_admin_auth_authenticate_expired_token(admin_auth, settings):
    mock_expired_authenticate_request = MagicMock()
    mock_expired_authenticate_request.session = {
        "token": create_access_token(settings.admin_user, expires_delta=timedelta(seconds=-1))
    }

    assert await admin_auth.authenticate(mock_expired_authenticate_request) is False


@pytest.mark.asyncio
async def test_login_for_access_token():
    pass
