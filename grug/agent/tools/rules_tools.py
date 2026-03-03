"""TTRPG rule-lookup agent tools.

Grug can query built-in sources (Archives of Nethys for PF2e, dnd5eapi.co for
D&D 5e SRD) when a user asks a rules question.  Guild admins control which
sources are active via the web UI.
"""

from __future__ import annotations

import asyncio
import logging
from urllib.parse import quote_plus

import httpx
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext

from grug.agent.core import GrugDeps

logger = logging.getLogger(__name__)

# Maximum characters returned per source so Grug's context stays manageable.
_MAX_SOURCE_CHARS = 6000


# Source attribution strings included in every result block so Grug can cite them.
_SOURCE_HEADERS = {
    "aon_pf2e": "Archives of Nethys (https://2e.aonprd.com)",
    "srd_5e": "D&D 5e SRD (https://www.dnd5eapi.co)",
}


class _AONQueryPlan(BaseModel):
    """Routing plan produced by the LLM classifier for an AoN Elasticsearch query."""

    search_query: str
    """Curated Elasticsearch search string — concise, focused, no conversational preamble."""

    preferred_types: list[str] = []
    """PF2e content types to boost in relevance scoring, e.g. ["Spell", "Class", "Ancestry"].
    Leave empty if the content type is unknown or the query is broad.
    Valid types include: Ancestry, Background, Class, Feat, Spell, Action, Condition,
    Creature, Item, Skill, Trait, Rule, Hazard, Ritual."""


_AON_CLASSIFIER_PROMPT = """\
You are a query curator for the Archives of Nethys Pathfinder 2e (PF2e) search engine.
Given a user question or phrase, produce a focused Elasticsearch search query and optionally a
list of PF2e content types to prioritise.

Rules:
- Strip all conversational preamble ("how do I", "what is", "explain", "can I", etc.)
- Extract the core PF2e concept, entity name, or mechanic being asked about.
- If the question is about a named thing (spell, feat, ancestry, class, creature, etc.),
  make the search_query that thing's name as it appears in PF2e.
- If the question is about a mechanic or rule (flanking, dying, conditions, actions),
  use the PF2e term for that mechanic.
- preferred_types: include the 1-2 most likely content types; omit if unclear.

Examples:
  "how do I make a rogue?"                     → search_query: "rogue", preferred_types: ["Class"]
  "what does the goblin ancestry give you?"    → search_query: "goblin", preferred_types: ["Ancestry"]
  "fireball"                                   → search_query: "fireball", preferred_types: ["Spell"]
  "how does flanking work in pf2e?"            → search_query: "flanking", preferred_types: ["Rule"]
  "best feats for a fighter"                   → search_query: "fighter", preferred_types: ["Feat", "Class"]
  "what is the dying condition?"               → search_query: "dying", preferred_types: ["Condition"]
  "how many actions does casting a spell take" → search_query: "casting a spell actions", preferred_types: ["Rule"]
  "goblin wizard build"                        → search_query: "goblin wizard", preferred_types: ["Ancestry", "Class"]
"""


async def _plan_aon_query(user_query: str) -> _AONQueryPlan:
    """Use a fast LLM to curate the user query for AoN Elasticsearch."""
    from pydantic_ai.models.anthropic import AnthropicModel
    from pydantic_ai.providers.anthropic import AnthropicProvider

    from grug.config.settings import get_settings

    settings = get_settings()
    provider = AnthropicProvider(api_key=settings.anthropic_api_key)
    model = AnthropicModel("claude-haiku-4-5", provider=provider)

    classifier: Agent[None, _AONQueryPlan] = Agent(
        model,
        output_type=_AONQueryPlan,
        system_prompt=_AON_CLASSIFIER_PROMPT,
    )
    result = await classifier.run(user_query)
    return result.output


async def _fetch_aon_pf2e(query: str, *, size: int = 1) -> str:
    """Query the Archives of Nethys Elasticsearch index directly.

    Before searching, a fast LLM call curates the query into a focused PF2e
    search term and optionally identifies content types to boost.  Falls back
    to the raw query if the planner fails.

    Args:
        query: Search query string (natural language or direct term).
        size: Maximum number of hits to return.  Defaults to 1 for agent calls;
            the admin test UI passes 5 explicitly.
    """
    from elasticsearch import AsyncElasticsearch

    header = f"Source: {_SOURCE_HEADERS['aon_pf2e']}"

    # ── Curate the query with haiku ────────────────────────────────────────
    try:
        plan = await _plan_aon_query(query)
        search_query = plan.search_query or query
        preferred_types = plan.preferred_types
    except Exception as exc:  # noqa: BLE001
        logger.warning("AON query planner failed, using raw query: %s", exc)
        search_query = query
        preferred_types = []

    try:
        async with AsyncElasticsearch(
            "https://elasticsearch.aonprd.com/",
            headers={
                "Accept": "application/vnd.elasticsearch+json",
                "Content-Type": "application/vnd.elasticsearch+json",
            },
        ) as es:
            # Build dynamic type-boost functions from the plan
            boost_functions: list[dict] = [
                {
                    "filter": {"terms": {"type": ["Ancestry", "Class"]}},
                    "weight": 1.1,
                },
                {"filter": {"terms": {"type": ["Trait"]}}, "weight": 1.05},
            ]
            if preferred_types:
                boost_functions.insert(
                    0,
                    {
                        "filter": {"terms": {"type": preferred_types}},
                        "weight": 2.0,
                    },
                )

            es_response = await es.search(
                index="aon",
                query={
                    "function_score": {
                        "query": {
                            "bool": {
                                "should": [
                                    {
                                        "match_phrase_prefix": {
                                            "name.sayt": {"query": search_query}
                                        }
                                    },
                                    {
                                        "match_phrase_prefix": {
                                            "text.sayt": {
                                                "query": search_query,
                                                "boost": 0.1,
                                            }
                                        }
                                    },
                                    {"term": {"name": search_query}},
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
                                                for word in search_query.split(" ")
                                            ]
                                        }
                                    },
                                ],
                                "must_not": [{"term": {"exclude_from_search": True}}],
                                "minimum_should_match": 1,
                            }
                        },
                        "boost_mode": "multiply",
                        "functions": boost_functions,
                    }
                },
                sort=["_score", "_doc"],
                source=[
                    "name",
                    "type",
                    "text",
                    "summary",
                    "url",
                    "source_raw",
                    "level",
                    "rarity",
                    "trait_raw",
                ],
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
            level = src.get("level")
            rarity = src.get("rarity", "")
            source_raw = src.get("source_raw", "")
            traits = src.get("trait_raw", [])
            # text field contains the full plain-text stat block; fall back to summary
            body_text = (src.get("text") or src.get("summary") or "").strip()
            entry_url = f"https://2e.aonprd.com{src['url']}" if src.get("url") else ""

            heading = f"**{name}**"
            if entry_type:
                heading += f" ({entry_type}"
                if level is not None:
                    heading += f" {level}"
                heading += ")"
            if rarity and rarity.lower() not in ("common", ""):
                heading += f" [{rarity}]"
            if entry_url:
                heading += f" — {entry_url}"
            if source_raw:
                heading += f" | Source: {source_raw}"
            if traits:
                heading += f"\nTraits: {', '.join(traits)}"
            if body_text:
                heading += f"\n{body_text}"
            parts.append(heading)

        return header + "\nArchives of Nethys results:\n\n" + "\n\n---\n".join(parts)
    except Exception as exc:
        logger.warning("AON Elasticsearch lookup failed: %s", exc)
        return f"{header}\nCould not reach Archives of Nethys Elasticsearch: {exc}"


def _detect_srd_type(d: dict) -> str:
    """Infer the content type from a dnd5eapi.co detail record."""
    url = d.get("url", "")
    if "/spells/" in url:
        return "Spell"
    if "/monsters/" in url:
        return "Monster"
    if "/magic-items/" in url:
        return "Magic Item"
    if "/conditions/" in url:
        return "Condition"
    if "/equipment/" in url:
        return "Equipment"
    if "/features/" in url:
        return "Feature"
    if "/backgrounds/" in url:
        return "Background"
    if "/rule-sections/" in url:
        return "Rule Section"
    if "/rules/" in url:
        return "Rule"
    if "/classes/" in url:
        return "Class"
    if "/races/" in url:
        return "Race"
    if "/subclasses/" in url:
        return "Subclass"
    if "/skills/" in url:
        return "Skill"
    if "/traits/" in url:
        return "Trait"
    # Fallback: sniff from fields
    if "school" in d:
        return "Spell"
    if "challenge_rating" in d or "hit_points" in d:
        return "Monster"
    return "Entry"


def _format_srd_entry(d: dict) -> str:
    """Format a single dnd5eapi.co detail record into a readable summary block."""
    name = d.get("name", "?")
    raw_url = d.get("url", "")
    # raw_url is an API path like /api/2014/spells/fireball — prepend base host directly
    page_url = "https://www.dnd5eapi.co" + raw_url if raw_url else ""
    entry_type = _detect_srd_type(d)

    lines: list[str] = []
    heading = f"**{name}** ({entry_type})"
    if page_url:
        heading += f" — {page_url}"
    lines.append(heading)

    # ── Spell fields ─────────────────────────────────────────────────
    if entry_type == "Spell":
        level = d.get("level", "?")
        school = (d.get("school") or {}).get("name", "")
        casting_time = d.get("casting_time", "")
        duration = d.get("duration", "")
        range_ = d.get("range", "")
        concentration = "Concentration" if d.get("concentration") else ""
        ritual = "Ritual" if d.get("ritual") else ""
        classes = ", ".join(c.get("name", "") for c in (d.get("classes") or []))
        meta_parts = [f"Level {level} {school}".strip()]
        if casting_time:
            meta_parts.append(f"Cast: {casting_time}")
        if range_:
            meta_parts.append(f"Range: {range_}")
        if duration:
            meta_parts.append(f"Duration: {duration}")
        for flag in (concentration, ritual):
            if flag:
                meta_parts.append(flag)
        if classes:
            meta_parts.append(f"Classes: {classes}")
        lines.append(" | ".join(meta_parts))
        # Damage info
        damage = d.get("damage") or {}
        dmg_type = (damage.get("damage_type") or {}).get("name", "")
        dmg_table = (
            damage.get("damage_at_slot_level")
            or damage.get("damage_at_character_level")
            or {}
        )
        if dmg_table:
            first_val = next(iter(dmg_table.values()), "")
            lines.append(f"Damage: {first_val} {dmg_type}".strip())
        # DC / Save
        dc = d.get("dc") or {}
        if dc.get("dc_type"):
            save_type = dc["dc_type"].get("name", "")
            on_success = dc.get("dc_success", "")
            lines.append(f"Save: {save_type} ({on_success})")
        # Description
        desc = d.get("desc") or []
        if isinstance(desc, list):
            lines.extend(desc[:2])
        elif isinstance(desc, str):
            lines.append(desc[:400])
        higher = d.get("higher_level") or []
        if higher:
            lines.append(
                "At Higher Levels: "
                + (higher[0] if isinstance(higher, list) else higher)
            )

    # ── Monster fields ───────────────────────────────────────────────
    elif entry_type == "Monster":
        size = d.get("size", "")
        mtype = d.get("type", "")
        alignment = d.get("alignment", "")
        ac_list = d.get("armor_class") or []
        ac_val = (
            ac_list[0].get("value", "?")
            if isinstance(ac_list, list) and ac_list
            else "?"
        )
        hp = d.get("hit_points", "?")
        hp_roll = d.get("hit_points_roll", "")
        cr = d.get("challenge_rating", "?")
        speed_dict = d.get("speed") or {}
        speed_str = ", ".join(f"{k} {v}" for k, v in speed_dict.items())
        lines.append(
            f"{size} {mtype} ({alignment}) | AC {ac_val} | HP {hp} ({hp_roll}) | CR {cr}"
        )
        if speed_str:
            lines.append(f"Speed: {speed_str}")
        # Ability scores
        stats = [
            "strength",
            "dexterity",
            "constitution",
            "intelligence",
            "wisdom",
            "charisma",
        ]
        stat_vals = [f"{s[:3].upper()} {d[s]}" for s in stats if s in d]
        if stat_vals:
            lines.append(" | ".join(stat_vals))
        # Special abilities (first two)
        for ability in (d.get("special_abilities") or [])[:2]:
            lines.append(
                f"• {ability.get('name', '')}: {ability.get('desc', '')[:200]}"
            )

    # ── Condition fields ─────────────────────────────────────────────
    elif entry_type == "Condition":
        desc = d.get("desc") or []
        if isinstance(desc, list):
            lines.extend(desc[:4])
        elif isinstance(desc, str):
            lines.append(desc[:600])

    # ── Magic Item fields ────────────────────────────────────────────
    elif entry_type == "Magic Item":
        rarity = (d.get("rarity") or {}).get("name", "")
        req_attunement = d.get("requires_attunement", "")
        if rarity:
            lines.append(
                f"Rarity: {rarity}"
                + (f" (Attunement: {req_attunement})" if req_attunement else "")
            )
        desc = d.get("desc") or []
        if isinstance(desc, list):
            lines.extend(desc[:3])
        elif isinstance(desc, str):
            lines.append(desc[:400])

    # ── Rule Section / Rule fields ───────────────────────────────────
    elif entry_type in ("Rule Section", "Rule"):
        desc = d.get("desc") or ""
        if isinstance(desc, str):
            # Rule section desc is markdown prose — truncate generously
            lines.append(desc[:2500])
        sub = d.get("subsections") or []
        if sub:
            names = ", ".join(s.get("name", "") for s in sub[:6])
            lines.append(f"Subsections: {names}")

    # ── Class fields ─────────────────────────────────────────────────
    elif entry_type == "Class":
        hit_die = d.get("hit_die", "?")
        saving_throws = ", ".join(
            s.get("name", "") for s in (d.get("saving_throws") or [])
        )
        lines.append(f"Hit Die: d{hit_die} | Saving Throws: {saving_throws}")
        for choice in d.get("proficiency_choices") or []:
            desc = choice.get("desc", "")
            if desc:
                lines.append(f"Skill Proficiencies: {desc}")
        spell_info = d.get("spellcasting") or {}
        if spell_info:
            spell_ability = (spell_info.get("spellcasting_ability") or {}).get(
                "name", ""
            )
            if spell_ability:
                lines.append(f"Spellcasting Ability: {spell_ability}")
            for info_block in (spell_info.get("info") or [])[:2]:
                name_block = info_block.get("name", "")
                desc_parts = info_block.get("desc") or []
                body = " ".join(desc_parts)[:300]
                lines.append(f"{name_block}: {body}")
        subclasses = d.get("subclasses") or []
        if isinstance(subclasses, list) and subclasses:
            sc_names = ", ".join(sc.get("name", "") for sc in subclasses[:6])
            lines.append(f"SRD Subclasses: {sc_names}")

    # ── Race fields ──────────────────────────────────────────────────
    elif entry_type == "Race":
        speed = d.get("speed", "?")
        size = d.get("size", "")
        lines.append(f"Speed: {speed} ft | Size: {size}")
        bonuses = ", ".join(
            f"{b.get('ability_score', {}).get('name', '')} +{b.get('bonus', '')}"
            for b in (d.get("ability_bonuses") or [])
        )
        if bonuses:
            lines.append(f"Ability Score Increases: {bonuses}")
        trait_names = [t.get("name", "") for t in (d.get("traits") or [])]
        if trait_names:
            lines.append(f"Racial Traits: {', '.join(trait_names)}")
        languages = [lang.get("name", "") for lang in (d.get("languages") or [])]
        if languages:
            lines.append(f"Languages: {', '.join(languages)}")

    # ── Subclass fields ──────────────────────────────────────────────
    elif entry_type == "Subclass":
        subclass_flavor = d.get("subclass_flavor", "")
        parent = (d.get("class") or {}).get("name", "")
        if parent:
            lines.append(f"{subclass_flavor} of {parent}")
        desc = d.get("desc") or []
        if isinstance(desc, list):
            lines.extend(desc[:3])
        elif isinstance(desc, str):
            lines.append(desc[:400])

    # ── Skill fields ─────────────────────────────────────────────────
    elif entry_type == "Skill":
        ability = (d.get("ability_score") or {}).get("name", "")
        if ability:
            lines.append(f"Ability: {ability}")
        desc = d.get("desc") or []
        if isinstance(desc, list):
            lines.extend(desc[:2])
        elif isinstance(desc, str):
            lines.append(desc[:300])

    # ── Generic fallback ─────────────────────────────────────────────
    else:
        desc = d.get("desc") or []
        if isinstance(desc, list):
            lines.extend(desc[:3])
        elif isinstance(desc, str):
            lines.append(desc[:400])

    return "\n".join(line for line in lines if line)


# Stop-words used as a fallback when the LLM planner is unavailable.
_SRD_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "do",
        "does",
        "for",
        "from",
        "how",
        "i",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "what",
        "when",
        "which",
        "with",
        "work",
    }
)


# ── LLM-based query planner ────────────────────────────────────────────────────


class _SRDQueryPlan(BaseModel):
    """Routing plan produced by the LLM classifier for a dnd5eapi query."""

    entity_endpoints: list[str] = []
    """Name-searchable endpoints to try with ?name=<search_term> (e.g. spells, monsters)."""

    direct_slugs: dict[str, str] = {}
    """Endpoint → slug for direct record fetches, e.g. {"classes": "wizard"}."""

    rule_keywords: list[str] = []
    """Keywords to score rule-section names against (client-side, no API search)."""

    search_term: str = ""
    """Normalised search term for name lookups; defaults to the original query."""


_SRD_CLASSIFIER_PROMPT = """\
You are a D&D 5e SRD API query router.  Given a user query, decide how to search dnd5eapi.co/api/2014/.

Name-searchable endpoints (support ?name=<substring>):
  spells, monsters, magic-items, equipment, conditions, feats, backgrounds, features

Direct-lookup endpoints (fetch by slug, e.g. /api/2014/classes/wizard):
  classes, races, subclasses, subraces, skills, traits, alignments, damage-types

Rule sections (33 named prose blocks matched client-side by keyword — no API search):
  Examples: "Making an Attack", "Actions in Combat", "Movement and Position", "Casting a Spell"

Rules:
- Populate entity_endpoints for any entity type the query might be asking about.
- Populate direct_slugs for class/race/subclass/skill/trait lookups.
  Slug = the lowercase hyphenated index, e.g. "wizard", "high-elf", "evocation", "perception".
- Populate rule_keywords for mechanical queries (grapple, opportunity attack, cover, flanking …).
  Include the relevant rule-section index slug if you know it.
- search_term: the cleaned term to use for name searches (strip "what is", "how does", etc.).

Examples:
  "wizard"             → direct_slugs: {"classes": "wizard"}
  "fireball"           → entity_endpoints: ["spells"], search_term: "fireball"
  "goblin"             → entity_endpoints: ["monsters"], search_term: "goblin"
  "bag of holding"     → entity_endpoints: ["magic-items"], search_term: "bag of holding"
  "elf race"           → direct_slugs: {"races": "elf"}
  "grapple rules"      → entity_endpoints: ["conditions"], rule_keywords: ["grapple", "making-an-attack"], search_term: "grappled"
  "opportunity attack" → rule_keywords: ["opportunity", "making-an-attack"]
  "perception skill"   → direct_slugs: {"skills": "perception"}
  "fireball wizard"    → entity_endpoints: ["spells"], direct_slugs: {"classes": "wizard"}, search_term: "fireball"
"""


async def _plan_srd_query(query: str) -> _SRDQueryPlan:
    """Use a fast LLM to classify the query and return a structured routing plan."""
    from pydantic_ai.models.anthropic import AnthropicModel
    from pydantic_ai.providers.anthropic import AnthropicProvider

    from grug.config.settings import get_settings

    settings = get_settings()
    provider = AnthropicProvider(api_key=settings.anthropic_api_key)
    model = AnthropicModel("claude-haiku-4-5", provider=provider)

    classifier: Agent[None, _SRDQueryPlan] = Agent(
        model,
        output_type=_SRDQueryPlan,
        system_prompt=_SRD_CLASSIFIER_PROMPT,
    )
    result = await classifier.run(query)
    plan = result.output
    if not plan.search_term:
        plan.search_term = query
    return plan


async def _fetch_srd_5e(query: str) -> str:
    """Query dnd5eapi.co using an LLM routing plan + parallel detail fetching.

    An LLM classifier first produces a :class:`_SRDQueryPlan` that specifies:
    - which name-searchable endpoints to try,
    - any entities to fetch directly by slug (classes, races, skills, etc.),
    - keywords for client-side rule-section scoring.

    All HTTP requests are issued in a single parallel batch; detail records are
    formatted with full mechanical data (spell stats, monster stat blocks, class
    features, rule prose).
    """
    header = f"Source: {_SOURCE_HEADERS['srd_5e']}"
    base = "https://www.dnd5eapi.co"

    # ── Get routing plan from LLM (fast haiku call) ────────────────────────
    try:
        plan = await _plan_srd_query(query)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "SRD query planner failed, using word-tokenisation fallback: %s", exc
        )
        fallback_words = [
            w for w in query.lower().split() if len(w) > 2 and w not in _SRD_STOP_WORDS
        ]
        plan = _SRDQueryPlan(
            entity_endpoints=[
                "spells",
                "monsters",
                "magic-items",
                "equipment",
                "conditions",
                "feats",
            ],
            rule_keywords=fallback_words,
            search_term=query,
        )

    search_term = plan.search_term or query

    try:
        async with httpx.AsyncClient(
            base_url=base, timeout=httpx.Timeout(connect=5, read=15, write=5, pool=5)
        ) as http:
            # ── Phase 1: all searches in one parallel batch ────────────────
            tasks: list = []
            task_labels: list[tuple[str, str]] = []

            for ep in plan.entity_endpoints:
                tasks.append(http.get(f"/api/2014/{ep}?name={quote_plus(search_term)}"))
                task_labels.append(("name_search", ep))

            for ep, slug in plan.direct_slugs.items():
                tasks.append(http.get(f"/api/2014/{ep}/{slug}"))
                task_labels.append(("direct", ep))

            if plan.rule_keywords:
                tasks.append(http.get("/api/2014/rule-sections"))
                task_labels.append(("rule_index", ""))

            if not tasks:
                # Nothing to do — plan was empty; broad fallback
                tasks = [
                    http.get(f"/api/2014/spells?name={quote_plus(search_term)}"),
                    http.get(f"/api/2014/conditions?name={quote_plus(search_term)}"),
                    http.get("/api/2014/rule-sections"),
                ]
                task_labels = [
                    ("name_search", "spells"),
                    ("name_search", "conditions"),
                    ("rule_index", ""),
                ]

            all_resps = await asyncio.gather(*tasks, return_exceptions=True)

            seen: set[str] = set()
            detail_urls: list[str] = []
            direct_bodies: list[dict] = []
            rule_section_urls: list[str] = []

            for (task_type, _ep), resp in zip(task_labels, all_resps):
                if isinstance(resp, Exception) or resp.status_code != 200:
                    continue
                data = resp.json()

                if task_type == "name_search":
                    for item in (data.get("results") or [])[:2]:
                        url = item.get("url", "")
                        if url and url not in seen:
                            seen.add(url)
                            detail_urls.append(url)

                elif task_type == "direct":
                    # Response IS the detail record
                    direct_bodies.append(data)

                elif task_type == "rule_index":
                    index_entries = data.get("results", [])
                    scored: list[tuple[int, str]] = []
                    for entry in index_entries:
                        entry_name = entry.get("name", "").lower()
                        entry_index = entry.get("index", "").lower()
                        score = sum(
                            1
                            for w in plan.rule_keywords
                            if w in entry_name or w in entry_index
                        )
                        if score > 0:
                            scored.append((score, entry.get("url", "")))
                    scored.sort(reverse=True)
                    rule_section_urls = [
                        u for _, u in scored[:2] if u and u not in seen
                    ]

            # ── Phase 2: fetch remaining detail URLs in parallel ───────────
            remaining = detail_urls + rule_section_urls
            if remaining:
                detail_resps = await asyncio.gather(
                    *[http.get(url) for url in remaining[:8]],
                    return_exceptions=True,
                )
                for resp in detail_resps:
                    if not isinstance(resp, Exception) and resp.status_code == 200:
                        direct_bodies.append(resp.json())

        if not direct_bodies:
            return (
                f'{header}\nNo results found in the D&D 5e SRD for "{query}". '
                "The SRD covers only 2014 core rules. Try searching by the exact "
                "name of a spell, monster, condition, magic item, class, or race."
            )

        parts: list[str] = []
        for body in direct_bodies[:8]:
            try:
                parts.append(_format_srd_entry(body))
            except Exception as exc:  # noqa: BLE001
                logger.debug("Failed to format SRD entry: %s", exc)

        if not parts:
            return f'{header}\nNo results found in the D&D 5e SRD for "{query}".'

        note = (
            "\n⚠ Note: dnd5eapi.co covers the 5e SRD only. "
            "Non-SRD monsters, subclasses, and 2024 revised content are not included."
        )
        return header + "\nD&D 5e SRD results:\n\n" + "\n\n---\n".join(parts) + note

    except Exception as exc:
        logger.warning("D&D 5e SRD lookup failed: %s", exc)
        return f"{header}\nCould not reach D&D 5e SRD API: {exc}"


def register_rules_tools(agent: Agent[GrugDeps, str]) -> None:
    """Register TTRPG rule-lookup tools on *agent*."""

    @agent.tool
    async def lookup_ttrpg_rules(
        ctx: RunContext[GrugDeps],
        query: str,
        system: str | None = None,
    ) -> str:
        """Look up TTRPG rules, spells, monsters, feats, or other game content.

        Searches all enabled rule sources for this guild:
        - **Archives of Nethys** (PF2e) — official Paizo-partnered SRD with
          near-complete PF2e coverage and free-text Elasticsearch search.
        - **D&D 5e SRD** (dnd5eapi.co) — SRD-only content; searches spells,
          monsters, magic items, equipment, conditions, and features in parallel.

        Optionally filter by ``system`` (e.g. ``"pf2e"``, ``"dnd5e"``).  If
        ``system`` is not provided, the guild's configured default TTRPG system
        is used automatically.  Returns combined results from all matching
        sources with full mechanical detail where available.

        Use when a user asks about rules, spells, feats, monsters, conditions,
        or any game-specific content that may not be in your training data.

        IMPORTANT: Every result block begins with a "Source: <name> (<url>)"
        line.  Always cite the source and include the URL so users can verify.
        Never present rule information without the source attribution.
        """
        from grug.db.models import GuildBuiltinOverride, GuildConfig
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
            else:
                continue
            sections.append(text[:_MAX_SOURCE_CHARS])

        if not sections:
            return (
                "No rule sources are enabled or matched the requested system for "
                "this server. A guild admin can enable sources in the Config tab."
            )

        return "\n\n---\n\n".join(sections)
