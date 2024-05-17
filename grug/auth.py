import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from loguru import logger
from pydantic import BaseModel
from sqladmin.authentication import AuthenticationBackend
from starlette import status
from starlette.requests import Request

from grug.models import User
from grug.settings import settings

auth_router = APIRouter(tags=["Auth"])


class Token(BaseModel):
    """Token model."""

    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Token data."""

    username: str | None = None


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def get_user(username: str) -> User | None:
    """Get the user from the database given the username."""

    # Check if the username is the admin user
    if username == settings.admin_user:
        return User(username=settings.admin_user)

    # if the username is not the admin user, check the database for the user
    else:
        logger.error("General user lookup is not implemented yet.  returning None.")


def authenticate_user(username: str, password: str):
    """Authenticate the user."""
    user = get_user(username)

    # Check if the user is the system admin account
    if user.username == settings.admin_user:
        # Check if the password is the admin password
        if secrets.compare_digest(password, settings.admin_password.get_secret_value()):
            return user

    # Otherwise, check the database for the user
    else:
        hashed_password = hashlib.scrypt(
            password.encode(),
            salt=settings.security_key.get_secret_value().encode(),
            n=2**14,
            r=8,
            p=1,
            dklen=64,
        )

        if hashed_password is not None:
            raise NotImplementedError("General user authentication is not implemented yet.")

        # TODO: lookup the user in the database and confirm their hashed_password against the stored hash
        logger.error("General user authentication is not implemented yet.")
        return False

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
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.security_key.get_secret_value(), algorithm=settings.security_algorithm)
    return encoded_jwt


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    """
    Get the current user.

    Args:
        token: JWT token

    Returns:
        User
    """

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.security_key.get_secret_value(), algorithms=[settings.security_algorithm])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
    user = get_user(username=token_data.username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Get the current active user.

    Args:
        current_user: The current user.

    Returns:
        The current user.

    """
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


@auth_router.post("/token")
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    """
    Get an access token for the user.

    Args:
        form_data: OAuth2PasswordRequestForm

    Returns:
        Token

    """

    user = authenticate_user(form_data.username, form_data.password)
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
    return Token(access_token=access_token, token_type="bearer")  # noqa: B106


class AdminAuth(AuthenticationBackend):
    """Authentication backend for the admin interface."""

    async def login(self, request: Request) -> bool:
        """Admin UI login."""
        form = await request.form()
        user = authenticate_user(form["username"], form["password"])

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
            try:
                if await get_current_active_user(await get_current_user(token)):
                    return True
            except Exception as e:
                logger.error(f"Error authenticating user: {e}")

        return False


def init_auth(app: FastAPI):
    """Initialize application authentication"""
    app.include_router(auth_router)
