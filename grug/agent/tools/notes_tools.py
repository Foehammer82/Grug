"""Notes agent tools — Grug reads and updates his own notes during responses.

Guild notes are scoped to a Discord server; personal notes are scoped to a
single user (used in DM sessions).  Grug should read his notes proactively
when recalling past decisions, naming conventions, house rules, or anything
the group has asked him to remember.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from pydantic_ai import RunContext
from sqlalchemy import select

from grug.agent.core import GrugDeps

if TYPE_CHECKING:
    from pydantic_ai import Agent

logger = logging.getLogger(__name__)

# updated_by value for agent-authored writes.
_AGENT_USER_ID = 0


def register_notes_tools(agent: Agent[GrugDeps, str]) -> None:
    """Register note read/write tools on the provided pydantic-ai Agent."""

    @agent.tool
    async def read_notes(ctx: RunContext[GrugDeps]) -> str:
        """Read Grug's current notes for this server (or this user in a DM).

        Call this when:
        - The user asks about something Grug might have written down before.
        - Recalling server-specific rules, naming conventions, or campaign decisions.
        - Checking what the group has asked Grug to remember.

        Returns the full notes content, or a message that there are no notes yet.
        """
        from grug.db.models import GrugNote
        from grug.db.session import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            if ctx.deps.is_dm_session:
                result = await session.execute(
                    select(GrugNote).where(
                        GrugNote.user_id == ctx.deps.user_id,
                        GrugNote.guild_id.is_(None),
                    )
                )
            else:
                result = await session.execute(
                    select(GrugNote).where(
                        GrugNote.guild_id == ctx.deps.guild_id,
                        GrugNote.user_id.is_(None),
                    )
                )
            note = result.scalar_one_or_none()

        if note is None or not note.content.strip():
            notes_text = "Grug notes: (empty — nothing written down yet)"
        else:
            notes_text = f"Grug notes:\n\n{note.content}"

        # Always remind Grug who is currently speaking so notes can be
        # cross-referenced with the right person.
        if not ctx.deps.is_dm_session:
            notes_text += (
                f"\n\n[Current speaker: user_id={ctx.deps.user_id}, "
                f"username={ctx.deps.username}]"
            )
        return notes_text

    @agent.tool
    async def write_notes(ctx: RunContext[GrugDeps], content: str) -> str:
        """Overwrite Grug's notes for this server (or this user in a DM).

        The *content* argument replaces the current notes entirely — always
        preserve existing information unless it is explicitly being removed.
        Fetch the current notes with ``read_notes`` first if you need to append
        or edit rather than replace.

        Call this when:
        - The user asks Grug to remember something going forward.
        - Updating house rules, campaign notes, or naming conventions.
        - Correcting or expanding notes based on new information.

        IMPORTANT — user identity in guild notes:
        Never write "you", "they", or a display name when referring to a
        specific person in server-scoped notes.  Always tag them with their
        stable Discord identity using the format:
            [user:{user_id} @{username}]
        The current speaker's user_id and username are always included at the
        bottom of the ``read_notes`` output — use those values.  This ensures
        notes remain meaningful after the conversation ends.
        Example: Instead of "you like coffee ice cream", write
        "[user:123456789 @foehammer] likes coffee ice cream".
        """
        from grug.db.models import GrugNote
        from grug.db.session import get_session_factory

        factory = get_session_factory()
        async with factory() as session:
            if ctx.deps.is_dm_session:
                result = await session.execute(
                    select(GrugNote).where(
                        GrugNote.user_id == ctx.deps.user_id,
                        GrugNote.guild_id.is_(None),
                    )
                )
                note = result.scalar_one_or_none()
                if note is None:
                    note = GrugNote(
                        guild_id=None,
                        user_id=ctx.deps.user_id,
                        content=content,
                        updated_by=_AGENT_USER_ID,
                    )
                    session.add(note)
                else:
                    note.content = content
                    note.updated_by = _AGENT_USER_ID
                    note.updated_at = datetime.now(timezone.utc)
            else:
                result = await session.execute(
                    select(GrugNote).where(
                        GrugNote.guild_id == ctx.deps.guild_id,
                        GrugNote.user_id.is_(None),
                    )
                )
                note = result.scalar_one_or_none()
                if note is None:
                    note = GrugNote(
                        guild_id=ctx.deps.guild_id,
                        user_id=None,
                        content=content,
                        updated_by=_AGENT_USER_ID,
                    )
                    session.add(note)
                else:
                    note.content = content
                    note.updated_by = _AGENT_USER_ID
                    note.updated_at = datetime.now(timezone.utc)

            await session.commit()

        return "Grug notes updated!"
