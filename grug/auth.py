import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

import requests
from authlib.integrations.base_client import MismatchingStateError
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import ExpiredSignatureError, JWTError, jwt
from pydantic import BaseModel
from sqladmin.authentication import AuthenticationBackend
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from starlette import status
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from grug.db import async_session, get_db_session_dependency
from grug.models import User
from grug.settings import settings

auth_router = APIRouter(tags=["Auth"])
_oauth = OAuth()


class Token(BaseModel):
    """Token model."""

    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Token data."""

    username: str | None = None


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def get_user(username: str, db_session: AsyncSession) -> User | None:
    """Get the user from the database given the username."""

    # Check if the username is the admin user
    if username == settings.admin_user:
        return User(username=settings.admin_user, is_admin=True)

    # if the username is not the admin user, check the database for the user
    else:
        return (await db_session.execute(select(User).where(User.username == username))).scalars().one_or_none()


async def authenticate_user(username: str, password: str, db_session: AsyncSession):
    """Authenticate the user."""
    user = await get_user(username, db_session)

    # Check if the user is the system admin account
    if user and user.username == settings.admin_user:
        # Check if the password is the admin password
        if secrets.compare_digest(password, settings.admin_password.get_secret_value()):
            return user

    # Check if the user is the discord admin user
    elif (
        user
        and user.discord_member_id
        and settings.discord
        and settings.discord.admin_user_id
        and user.discord_member_id == settings.discord.admin_user_id
    ):
        return user

    # Otherwise, check the database for the user
    else:
        user = (await db_session.execute(select(User).where(User.username == username))).scalars().one_or_none()

        # Check if the user exists and the password is correct
        if user and user.secrets:
            hashed_password = hashlib.scrypt(
                password.encode(),
                salt=settings.security_key.get_secret_value().encode(),
                n=2**14,
                r=8,
                p=1,
                dklen=64,
            )

            if secrets.compare_digest(hashed_password, user.secrets[0].hashed_password):
                return user

    # ALWAYS return False by default, above code should return the user if they are authenticated
    return False


def create_access_token(username: str, expires_delta: timedelta | None = None):
    """

    Args:
        username: The username of the authenticating user.
        expires_delta: The expiration time for the token.

    Returns:
        The encoded JWT token.
    """
    to_encode = {"sub": username}.copy()
    to_encode.update(
        {
            "exp": str(
                int(
                    (datetime.now(timezone.utc) + expires_delta).timestamp()
                    if expires_delta
                    else (datetime.now(timezone.utc) + timedelta(minutes=15)).timestamp()
                )
            )
        }
    )
    encoded_jwt = jwt.encode(to_encode, settings.security_key.get_secret_value(), algorithm=settings.security_algorithm)
    return encoded_jwt


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db_session: AsyncSession):
    """Get the current user."""

    try:
        payload = jwt.decode(token, settings.security_key.get_secret_value(), algorithms=[settings.security_algorithm])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
        token_data = TokenData(username=username)
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=e,
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = (await get_user(username=token_data.username, db_session=db_session)) if token_data.username else None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_active_user(
    current_user: Annotated[User, Annotated[AsyncSession, Depends(get_current_user)]],
) -> User:
    """Get the current active user."""
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


@auth_router.post("/token")
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db_session: Annotated[AsyncSession, Depends(get_db_session_dependency)],
) -> Token:
    """Get an access token for the user."""

    user = await authenticate_user(form_data.username, form_data.password, db_session)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        username=user.username,
        expires_delta=timedelta(minutes=settings.security_access_token_expire_minutes),
    )
    return Token(access_token=access_token, token_type="bearer")  # noqa: B106 # nosec B106


class AdminAuth(AuthenticationBackend):
    """Authentication backend for the admin interface."""

    async def login(self, request: Request) -> bool:
        """Admin UI login."""
        form = await request.form()

        async with async_session() as db_session:
            user = await authenticate_user(
                form["username"],
                form["password"],
                db_session,
            )

        # Validate username/password credentials and update session
        if user:
            access_token = create_access_token(
                username=user.username,
                expires_delta=timedelta(minutes=settings.security_access_token_expire_minutes),
            )
            request.session.update({"token": access_token})
            return True

        # Return False if the credentials are invalid
        return False

    async def logout(self, request: Request) -> bool:
        """Admin UI logout."""
        # Usually you'd want to just clear the session
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        """Admin UI authentication."""
        # Check that the active user is authenticated and the token is not expired
        if token := request.session.get("token"):
            async with async_session() as db_session:
                current_active_user = await get_current_active_user(await get_current_user(token, db_session))

            # Check if the user is an admin or owner
            if current_active_user.is_admin or current_active_user.is_owner:
                return True
            else:
                raise HTTPException(status_code=403, detail="Not Authorized")

        return False


# Configure and enable OAuth for discord authentication if enabled in the settings
if settings.discord and settings.discord.enable_oauth:
    _oauth.register(  # nosec B106
        "discord",
        client_id=settings.discord.client_id,
        client_secret=settings.discord.client_secret.get_secret_value(),
        access_token_url="https://discord.com/api/oauth2/token",
        access_token_params=None,
        authorize_url="https://discord.com/api/oauth2/authorize",
        authorize_params=None,
        api_base_url="https://discord.com/api/",
        client_kwargs={"scope": "identify email"},
    )
    _discord_oauth = _oauth.create_client("discord")

    @auth_router.get("/oauth/discord-redirect")
    async def oauth_login_server_redirect(request: Request):
        return await _discord_oauth.authorize_redirect(request, request.url_for("oauth_login_discord"))

    @auth_router.get("/oauth/discord")
    async def oauth_login_discord(
        request: Request,
        db_session: AsyncSession = Depends(get_db_session_dependency),
    ) -> Response:
        # Validate oauth returned user is known in the app and log them by providing a jwt
        try:
            token = await _discord_oauth.authorize_access_token(request)
        except MismatchingStateError as e:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Invalid state error.  Most likely, it's an issue with cookies and the user having the issue "
                    "just needs to reset their cached cookies in their browser."
                ),
            ) from e

        # Get the user info from the discord api
        user_info_response = requests.get(
            "https://discord.com/api/users/@me",
            headers={"Authorization": f"Bearer {token['access_token']}"},
            timeout=5,
        )
        user_info_response.raise_for_status()
        user_info = user_info_response.json()  # username, email, id

        # Look up the user in the database
        user = (
            (await db_session.execute(select(User).where(User.discord_member_id == int(user_info["id"]))))
            .scalars()
            .one_or_none()
        )

        # Create the user if they do not exist
        if not user:
            user = User(
                username=user_info["username"],
                email=user_info["email"],
                discord_member_id=user_info["id"],
                discord_username=user_info["username"],
            )
            db_session.add(user)
            await db_session.commit()
            await db_session.refresh(user)

        # Update the user's email if it is not set
        elif user.email is None:
            user.email = user_info["email"]
            db_session.add(user)
            await db_session.commit()
            await db_session.refresh(user)

        # Create the access token and update the session
        access_token = create_access_token(
            username=user.username,
            expires_delta=timedelta(minutes=settings.security_access_token_expire_minutes),
        )
        request.session.update({"token": access_token})

        # Redirect to the admin index
        return RedirectResponse(request.url_for("admin:index"))


def init_auth(app: FastAPI):
    """Initialize application authentication"""
    app.include_router(auth_router)
