"""TTRPG rule-lookup agent tools.

Grug can query built-in sources (Archives of Nethys, dnd5eapi.co, Open5e)
as well as custom guild-configured sources when a user asks a rules question.
Guild admins control which sources are active via the web UI.
"""

from __future__ import annotations

import logging
from urllib.parse import quote_plus

import httpx
from pydantic_ai import Agent, RunContext

from grug.agent.core import GrugDeps

logger = logging.getLogger(__name__)

# Maximum characters returned per source so Grug's context stays manageable.
_MAX_SOURCE_CHARS = 6000


# Source attribution strings included in every result block so Grug can cite them.
_SOURCE_HEADERS = {
    "aon_pf2e": "Archives of Nethys (https://2e.aonprd.com)",
    "srd_5e": "D&D 5e SRD (https://www.dnd5eapi.co)",
    "open5e": "Open5e (https://open5e.com)",
}


async def _fetch_aon_pf2e(query: str, *, size: int = 3) -> str:
    """Query the Archives of Nethys Elasticsearch index directly.

    Args:
        query: Search query string.
        size: Maximum number of hits to return.  Defaults to 3 for agent calls;
            the admin test UI passes a higher value.
    """
    from elasticsearch import AsyncElasticsearch

    header = f"Source: {_SOURCE_HEADERS['aon_pf2e']}"
    try:
        async with AsyncElasticsearch(
            "https://elasticsearch.aonprd.com/",
            headers={
                "Accept": "application/vnd.elasticsearch+json",
                "Content-Type": "application/vnd.elasticsearch+json",
            },
        ) as es:
            es_response = await es.search(
                index="aon",
                query={
                    "function_score": {
                        "query": {
                            "bool": {
                                "should": [
                                    {
                                        "match_phrase_prefix": {
                                            "name.sayt": {"query": query}
                                        }
                                    },
                                    {
                                        "match_phrase_prefix": {
                                            "text.sayt": {"query": query, "boost": 0.1}
                                        }
                                    },
                                    {"term": {"name": query}},
                                    {
                                        "bool": {
                                            "must": [
                                                {
                                                    "multi_match": {
                                                        "query": word,
                                                        "type": "best_fields",
                                                        "fields": [
                                                            "name",
                                                            "text^0.1",
                                                            "trait_raw",
                                                            "type",
                                                        ],
                                                        "fuzziness": "auto",
                                                    }
                                                }
                                                for word in query.split(" ")
                                            ]
                                        }
                                    },
                                ],
                                "must_not": [{"term": {"exclude_from_search": True}}],
                                "minimum_should_match": 1,
                            }
                        },
                        "boost_mode": "multiply",
                        "functions": [
                            {
                                "filter": {"terms": {"type": ["Ancestry", "Class"]}},
                                "weight": 1.1,
                            },
                            {"filter": {"terms": {"type": ["Trait"]}}, "weight": 1.05},
                        ],
                    }
                },
                sort=["_score", "_doc"],
                source={},
                size=size,
            )

        hits = es_response["hits"]["hits"]
        if not hits:
            return f"{header}\nNo results found on Archives of Nethys."

        parts = []
        for hit in hits:
            src = hit["_source"]
            name = src.get("name", "?")
            entry_type = src.get("type", "")
            # Prefer full text when available (test mode); fall back to summary snippet.
            body_text = (src.get("text") or src.get("summary") or "").strip()
            entry_url = f"https://2e.aonprd.com{src['url']}" if src.get("url") else ""
            entry = f"**{name}**"
            if entry_type:
                entry += f" ({entry_type})"
            if entry_url:
                entry += f" — {entry_url}"
            if body_text:
                entry += f": {body_text}"
            parts.append(entry)

        return header + "\nArchives of Nethys results:\n" + "\n".join(parts)
    except Exception as exc:
        logger.warning("AON Elasticsearch lookup failed: %s", exc)
        return f"{header}\nCould not reach Archives of Nethys Elasticsearch: {exc}"


async def _fetch_srd_5e(query: str) -> str:
    """Query the D&D 5e SRD API (dnd5eapi.co) for query."""
    header = f"Source: {_SOURCE_HEADERS['srd_5e']}"
    url = f"https://www.dnd5eapi.co/api/spells?name={quote_plus(query)}"
    try:
        async with httpx.AsyncClient(timeout=10) as http:
            resp = await http.get(url)
        if resp.status_code != 200:
            return f"{header}\nD&D 5e SRD API returned HTTP {resp.status_code}."
        data = resp.json()
        if not data.get("results"):
            # Try equipment and monsters as fallback
            return await _fetch_srd_5e_resource(query)
        items = data["results"][:4]
        parts = []
        for item in items:
            # Convert JSON API path (/api/spells/fireball) to human-readable URL
            api_path = item.get("url", "")
            page_url = (
                "https://www.dnd5eapi.co" + api_path.replace("/api/", "/", 1)
                if api_path
                else ""
            )
            entry = f"**{item.get('name', '?')}**"
            if page_url:
                entry += f" — {page_url}"
            parts.append(entry)
        return header + "\nD&D 5e SRD (spells):\n" + "\n".join(parts)
    except Exception as exc:
        logger.warning("D&D 5e SRD API lookup failed: %s", exc)
        return f"{header}\nCould not reach D&D 5e SRD API: {exc}"


async def _fetch_srd_5e_resource(query: str) -> str:
    """Fallback — search monsters, magic items, and conditions via SRD API."""
    header = f"Source: {_SOURCE_HEADERS['srd_5e']}"
    q = quote_plus(query)
    async with httpx.AsyncClient(timeout=10) as http:
        search_url = f"https://www.dnd5eapi.co/api/monsters?name={q}"
        resp = await http.get(search_url)
    if resp.status_code == 200:
        data = resp.json()
        items = data.get("results", [])[:4]
        if items:
            parts = []
            for i in items:
                api_path = i.get("url", "")
                page_url = (
                    "https://www.dnd5eapi.co" + api_path.replace("/api/", "/", 1)
                    if api_path
                    else ""
                )
                entry = f"**{i.get('name', '?')}**"
                if page_url:
                    entry += f" — {page_url}"
                parts.append(entry)
            return header + "\nD&D 5e SRD (monsters):\n" + "\n".join(parts)
    return f"{header}\nNo results found in D&D 5e SRD."


async def _fetch_open5e(query: str) -> str:
    """Query Open5e's search endpoint."""
    header = f"Source: {_SOURCE_HEADERS['open5e']}"
    url = f"https://api.open5e.com/v2/search/?text={quote_plus(query)}&limit=5"
    try:
        async with httpx.AsyncClient(timeout=10) as http:
            resp = await http.get(url)
        if resp.status_code != 200:
            return f"{header}\nOpen5e returned HTTP {resp.status_code}."
        data = resp.json()
        results = data.get("results", [])[:5]
        if not results:
            return f"{header}\nNo results found on Open5e."
        parts = []
        for r in results:
            name = r.get("name") or r.get("slug") or "?"
            doc = r.get("document__title", "")
            slug = r.get("slug", "")
            route = r.get("route", "")
            # Map API route (e.g. "/v2/spells/fireball/") to open5e.com human page.
            # Drop the version prefix (v1, v2, ...) to get /spells/fireball.
            if route:
                route_parts = [p for p in route.strip("/").split("/") if p]
                if (
                    route_parts
                    and route_parts[0].startswith("v")
                    and route_parts[0][1:].isdigit()
                ):
                    route_parts = route_parts[1:]
                page_url = (
                    "https://open5e.com/" + "/".join(route_parts) if route_parts else ""
                )
            elif slug:
                page_url = f"https://open5e.com/{slug}"
            else:
                page_url = ""
            text_snippet = r.get("desc") or r.get("combat_tip") or ""
            text_snippet = text_snippet[:200].replace("\n", " ") if text_snippet else ""
            entry = f"**{name}**"
            if doc:
                entry += f" ({doc})"
            if page_url:
                entry += f" — {page_url}"
            if text_snippet:
                entry += f": {text_snippet}"
            parts.append(entry)
        return header + "\nOpen5e results:\n" + "\n".join(parts)
    except Exception as exc:
        logger.warning("Open5e lookup failed: %s", exc)
        return f"{header}\nCould not reach Open5e: {exc}"


async def _fetch_custom_source(name: str, url: str, query: str) -> str:
    """Return attribution for a custom source so Grug can cite it by name and URL."""
    # Custom sources are cited but not scraped (arbitrary URL scraping is a security risk).
    # Grug should direct the user to the source URL and tell them what to search for.
    return (
        f"Source: {name} ({url})\n"
        f"This source was not searched automatically. "
        f"Direct the user to {url} and tell them to search for '{query}' there."
    )


def register_rules_tools(agent: Agent[GrugDeps, str]) -> None:
    """Register TTRPG rule-lookup tools on *agent*."""

    @agent.tool
    async def lookup_ttrpg_rules(
        ctx: RunContext[GrugDeps],
        query: str,
        system: str | None = None,
    ) -> str:
        """Look up TTRPG rules, spells, monsters, feats, or other game content.

        Searches all enabled rule sources for this guild — built-in sources
        (Archives of Nethys for PF2e, D&D 5e SRD API, Open5e) and any custom
        sources the guild has added.  Optionally filter by ``system`` (e.g.
        ``"pf2e"``, ``"dnd5e"``).  If ``system`` is not provided, the guild's
        configured default TTRPG system is used automatically.  Returns a
        combined summary from all matching sources.

        Use when a user asks about rules, spells, feats, monsters, conditions,
        or any game-specific content that may not be in your training data.

        IMPORTANT: Every result block returned by this tool begins with a
        "Source: <name> (<url>)" line.  Always tell the user which source the
        information came from and include the URL so they can verify or read
        more.  Never present rule information without the source attribution.
        """
        from grug.db.models import GuildBuiltinOverride, GuildConfig, RuleSource
        from grug.db.session import get_session_factory
        from grug.rules.sources import BUILTIN_RULE_SOURCES
        from sqlalchemy import select

        factory = get_session_factory()
        async with factory() as session:
            # Load per-guild enabled/disabled overrides for built-ins
            result = await session.execute(
                select(GuildBuiltinOverride).where(
                    GuildBuiltinOverride.guild_id == ctx.deps.guild_id
                )
            )
            override_rows = result.scalars().all()
            overrides: dict[str, bool] = {r.source_id: r.enabled for r in override_rows}

            # Load custom sources ordered by priority
            result = await session.execute(
                select(RuleSource)
                .where(
                    RuleSource.guild_id == ctx.deps.guild_id,
                    RuleSource.enabled.is_(True),
                )
                .order_by(RuleSource.sort_order, RuleSource.created_at)
            )
            custom_sources = result.scalars().all()

            # Load guild default system as fallback when caller didn't specify
            if system is None:
                result = await session.execute(
                    select(GuildConfig.default_ttrpg_system).where(
                        GuildConfig.guild_id == ctx.deps.guild_id
                    )
                )
                row = result.scalar_one_or_none()
                if row:
                    system = row

        sections: list[str] = []

        # ── Query built-in sources ──────────────────────────────────────
        for builtin in BUILTIN_RULE_SOURCES:
            if not overrides.get(builtin.source_id, True):
                continue  # explicitly disabled for this guild
            if system and builtin.system and builtin.system != system:
                continue  # system filter — skip mismatched sources
            if builtin.source_id == "aon_pf2e":
                text = await _fetch_aon_pf2e(query)
            elif builtin.source_id == "srd_5e":
                text = await _fetch_srd_5e(query)
            elif builtin.source_id == "open5e":
                text = await _fetch_open5e(query)
            else:
                continue
            sections.append(text[:_MAX_SOURCE_CHARS])

        # ── Query custom sources ────────────────────────────────────────
        for src in custom_sources:
            if system and src.system and src.system != system:
                continue
            text = await _fetch_custom_source(src.name, src.url, query)
            if src.notes:
                text += f"\n  Notes: {src.notes}"
            sections.append(text)

        if not sections:
            return (
                "No rule sources are enabled or matched the requested system for "
                "this server. A guild admin can enable sources in the Config tab."
            )

        return "\n\n---\n\n".join(sections)
