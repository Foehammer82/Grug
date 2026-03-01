"""FastAPI application for the Grug web UI companion."""

from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .auth import (
    build_discord_oauth_url,
    create_jwt,
    exchange_code,
    fetch_discord_guilds,
    fetch_discord_user,
)
from .config import settings
from .database import get_db
from .deps import get_current_user
from .models import (
    CalendarEvent,
    Document,
    GlossaryTerm,
    GlossaryTermHistory,
    GuildConfig,
    Reminder,
    ScheduledTask,
)
from .schemas import (
    CalendarEventOut,
    DiscordChannelOut,
    DocumentOut,
    GlossaryTermCreate,
    GlossaryTermHistoryOut,
    GlossaryTermOut,
    GlossaryTermUpdate,
    GuildConfigOut,
    GuildConfigUpdate,
    GuildOut,
    ReminderOut,
    ScheduledTaskOut,
    TaskToggle,
    UserOut,
)

app = FastAPI(title="Grug API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.web_cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@app.get("/auth/discord/login")
async def discord_login() -> RedirectResponse:
    return RedirectResponse(build_discord_oauth_url())


@app.get("/auth/discord/callback")
async def discord_callback(code: str, response: Response) -> dict[str, str]:
    token_data = await exchange_code(code)
    access_token = token_data["access_token"]
    user = await fetch_discord_user(access_token)
    guilds = await fetch_discord_guilds(access_token)

    payload: dict[str, Any] = {
        "sub": user["id"],
        "username": user["username"],
        "discriminator": user.get("discriminator", "0"),
        "avatar": user.get("avatar"),
        "guilds": [
            {"id": g["id"], "name": g["name"], "icon": g.get("icon")} for g in guilds
        ],
    }
    jwt_token = create_jwt(payload)
    response.set_cookie(
        key="session",
        value=jwt_token,
        httponly=True,
        samesite="lax",
        max_age=86400,
    )
    # Redirect to the frontend dashboard after successful login
    return RedirectResponse(url=f"{settings.frontend_url}/dashboard", status_code=302)


@app.get("/auth/me", response_model=UserOut)
async def get_me(user: dict[str, Any] = Depends(get_current_user)) -> UserOut:
    return UserOut(
        id=user["sub"],
        username=user["username"],
        discriminator=user["discriminator"],
        avatar=user.get("avatar"),
    )


@app.post("/auth/logout")
async def logout(response: Response) -> dict[str, str]:
    response.delete_cookie("session")
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _assert_guild_member(guild_id: str, user: dict[str, Any]) -> None:
    guild_ids = {g["id"] for g in user.get("guilds", [])}
    if str(guild_id) not in guild_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this guild"
        )


# ---------------------------------------------------------------------------
# Guilds
# ---------------------------------------------------------------------------


@app.get("/api/guilds", response_model=list[GuildOut])
async def list_guilds(
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[GuildOut]:
    user_guild_ids = {int(g["id"]) for g in user.get("guilds", [])}
    result = await db.execute(select(GuildConfig))
    configs = result.scalars().all()
    bot_guild_ids = {c.guild_id for c in configs}
    shared = user_guild_ids & bot_guild_ids
    return [
        GuildOut(id=g["id"], name=g["name"], icon=g.get("icon"))
        for g in user.get("guilds", [])
        if int(g["id"]) in shared
    ]


# ---------------------------------------------------------------------------
# Guild config
# ---------------------------------------------------------------------------


@app.get("/api/guilds/{guild_id}/config", response_model=GuildConfigOut)
async def get_guild_config(
    guild_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GuildConfig:
    _assert_guild_member(str(guild_id), user)
    result = await db.execute(
        select(GuildConfig).where(GuildConfig.guild_id == guild_id)
    )
    cfg = result.scalar_one_or_none()
    if cfg is None:
        raise HTTPException(status_code=404, detail="Guild config not found")
    return cfg


@app.patch("/api/guilds/{guild_id}/config", response_model=GuildConfigOut)
async def update_guild_config(
    guild_id: int,
    body: GuildConfigUpdate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GuildConfig:
    _assert_guild_member(str(guild_id), user)
    result = await db.execute(
        select(GuildConfig).where(GuildConfig.guild_id == guild_id)
    )
    cfg = result.scalar_one_or_none()
    if cfg is None:
        raise HTTPException(status_code=404, detail="Guild config not found")
    if body.timezone is not None:
        cfg.timezone = body.timezone
    if body.announce_channel_id is not None:
        cfg.announce_channel_id = body.announce_channel_id
    cfg.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(cfg)
    return cfg


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------


@app.get("/api/guilds/{guild_id}/events", response_model=list[CalendarEventOut])
async def list_events(
    guild_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[CalendarEvent]:
    _assert_guild_member(str(guild_id), user)
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(CalendarEvent)
        .where(CalendarEvent.guild_id == guild_id, CalendarEvent.start_time >= now)
        .order_by(CalendarEvent.start_time)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Scheduled tasks
# ---------------------------------------------------------------------------


@app.get("/api/guilds/{guild_id}/tasks", response_model=list[ScheduledTaskOut])
async def list_tasks(
    guild_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ScheduledTask]:
    _assert_guild_member(str(guild_id), user)
    result = await db.execute(
        select(ScheduledTask)
        .where(ScheduledTask.guild_id == guild_id)
        .order_by(ScheduledTask.created_at)
    )
    return list(result.scalars().all())


@app.patch("/api/guilds/{guild_id}/tasks/{task_id}", response_model=ScheduledTaskOut)
async def toggle_task(
    guild_id: int,
    task_id: int,
    body: TaskToggle,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ScheduledTask:
    _assert_guild_member(str(guild_id), user)
    result = await db.execute(
        select(ScheduledTask).where(
            ScheduledTask.id == task_id, ScheduledTask.guild_id == guild_id
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    task.enabled = body.enabled
    await db.commit()
    await db.refresh(task)
    return task


@app.delete("/api/guilds/{guild_id}/tasks/{task_id}", status_code=204)
async def delete_task(
    guild_id: int,
    task_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    _assert_guild_member(str(guild_id), user)
    result = await db.execute(
        select(ScheduledTask).where(
            ScheduledTask.id == task_id, ScheduledTask.guild_id == guild_id
        )
    )
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    await db.delete(task)
    await db.commit()


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


@app.get("/api/guilds/{guild_id}/documents", response_model=list[DocumentOut])
async def list_documents(
    guild_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Document]:
    _assert_guild_member(str(guild_id), user)
    result = await db.execute(
        select(Document)
        .where(Document.guild_id == guild_id)
        .order_by(Document.created_at)
    )
    return list(result.scalars().all())


@app.delete("/api/guilds/{guild_id}/documents/{doc_id}", status_code=204)
async def delete_document(
    guild_id: int,
    doc_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    _assert_guild_member(str(guild_id), user)
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.guild_id == guild_id)
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    await db.delete(doc)
    await db.commit()


# ---------------------------------------------------------------------------
# Reminders
# ---------------------------------------------------------------------------


@app.get("/api/guilds/{guild_id}/reminders", response_model=list[ReminderOut])
async def list_reminders(
    guild_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Reminder]:
    _assert_guild_member(str(guild_id), user)
    result = await db.execute(
        select(Reminder)
        .where(Reminder.guild_id == guild_id)
        .order_by(Reminder.remind_at)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Guild channels (proxied from Discord API — used by web UI channel selectors)
# ---------------------------------------------------------------------------


@app.get("/api/guilds/{guild_id}/channels", response_model=list[DiscordChannelOut])
async def list_guild_channels(
    guild_id: int,
    user: dict[str, Any] = Depends(get_current_user),
) -> list[DiscordChannelOut]:
    """Proxy Discord's channel list for a guild so the web UI can display channel names."""
    import httpx

    _assert_guild_member(str(guild_id), user)
    bot_token = settings.discord_bot_token
    if not bot_token:
        raise HTTPException(status_code=503, detail="Bot token not configured")
    async with httpx.AsyncClient() as http:
        resp = await http.get(
            f"https://discord.com/api/v10/guilds/{guild_id}/channels",
            headers={"Authorization": f"Bot {bot_token}"},
        )
    if resp.status_code != 200:
        raise HTTPException(
            status_code=502, detail="Failed to fetch channels from Discord"
        )
    channels = resp.json()
    # Only return text channels (type 0) and announcement channels (type 5)
    return [
        DiscordChannelOut(id=str(c["id"]), name=c["name"], type=c["type"])
        for c in channels
        if c.get("type") in (0, 5)
    ]


# ---------------------------------------------------------------------------
# Glossary
# ---------------------------------------------------------------------------


@app.get("/api/guilds/{guild_id}/glossary", response_model=list[GlossaryTermOut])
async def list_glossary_terms(
    guild_id: int,
    channel_id: int | None = None,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[GlossaryTerm]:
    """List glossary terms for a guild. Pass ?channel_id= to scope to a channel."""
    _assert_guild_member(str(guild_id), user)
    stmt = select(GlossaryTerm).where(GlossaryTerm.guild_id == guild_id)
    if channel_id is not None:
        stmt = stmt.where(GlossaryTerm.channel_id == channel_id)
    stmt = stmt.order_by(GlossaryTerm.term)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@app.post(
    "/api/guilds/{guild_id}/glossary", response_model=GlossaryTermOut, status_code=201
)
async def create_glossary_term(
    guild_id: int,
    body: GlossaryTermCreate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GlossaryTerm:
    """Create a human-authored glossary term."""
    _assert_guild_member(str(guild_id), user)
    now = datetime.now(timezone.utc)
    term = GlossaryTerm(
        guild_id=guild_id,
        channel_id=body.channel_id,
        term=body.term,
        definition=body.definition,
        ai_generated=False,
        originally_ai_generated=False,
        created_by=int(user["sub"]),
        updated_at=now,
    )
    db.add(term)
    await db.commit()
    await db.refresh(term)
    return term


@app.patch("/api/guilds/{guild_id}/glossary/{term_id}", response_model=GlossaryTermOut)
async def update_glossary_term(
    guild_id: int,
    term_id: int,
    body: GlossaryTermUpdate,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GlossaryTerm:
    """Update a glossary term. Saves a history row first and clears the ai_generated flag."""
    _assert_guild_member(str(guild_id), user)
    result = await db.execute(
        select(GlossaryTerm).where(
            GlossaryTerm.id == term_id, GlossaryTerm.guild_id == guild_id
        )
    )
    term = result.scalar_one_or_none()
    if term is None:
        raise HTTPException(status_code=404, detail="Glossary term not found")

    # Snapshot before changing.
    history = GlossaryTermHistory(
        term_id=term.id,
        guild_id=term.guild_id,
        old_term=term.term,
        old_definition=term.definition,
        old_ai_generated=term.ai_generated,
        changed_by=int(user["sub"]),
    )
    db.add(history)

    if body.term is not None:
        term.term = body.term
    if body.definition is not None:
        term.definition = body.definition
    # Human edit → clear the AI ownership flag; originally_ai_generated is never touched.
    term.ai_generated = False
    term.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(term)
    return term


@app.delete("/api/guilds/{guild_id}/glossary/{term_id}", status_code=204)
async def delete_glossary_term(
    guild_id: int,
    term_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a glossary term (and its history via cascade)."""
    _assert_guild_member(str(guild_id), user)
    result = await db.execute(
        select(GlossaryTerm).where(
            GlossaryTerm.id == term_id, GlossaryTerm.guild_id == guild_id
        )
    )
    term = result.scalar_one_or_none()
    if term is None:
        raise HTTPException(status_code=404, detail="Glossary term not found")
    await db.delete(term)
    await db.commit()


@app.get(
    "/api/guilds/{guild_id}/glossary/{term_id}/history",
    response_model=list[GlossaryTermHistoryOut],
)
async def get_glossary_term_history(
    guild_id: int,
    term_id: int,
    user: dict[str, Any] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[GlossaryTermHistory]:
    """Retrieve the full change history for a glossary term."""
    _assert_guild_member(str(guild_id), user)
    # Verify the term belongs to this guild.
    term_result = await db.execute(
        select(GlossaryTerm).where(
            GlossaryTerm.id == term_id, GlossaryTerm.guild_id == guild_id
        )
    )
    if term_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Glossary term not found")

    history_result = await db.execute(
        select(GlossaryTermHistory)
        .where(GlossaryTermHistory.term_id == term_id)
        .order_by(GlossaryTermHistory.changed_at.desc())
    )
    return list(history_result.scalars().all())
