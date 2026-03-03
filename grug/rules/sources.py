"""Built-in TTRPG rule sources that Grug can query without any guild setup.

Each :class:`BuiltinRuleSource` describes a publicly-accessible API or
website that Grug knows how to search.  Guild admins can disable any of these
per-server via the web UI (stored in ``guild_builtin_overrides``).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class BuiltinRuleSource:
    """Metadata for a built-in rule lookup source.

    Attributes:
        source_id:  Stable identifier, e.g. ``"aon_pf2e"``.  Used as the key
                    in ``guild_builtin_overrides.source_id``.
        name:       Human-readable display name shown in the web UI.
        description: One-sentence explanation of what the source covers.
        system:     The TTRPG system this source covers, e.g. ``"pf2e"`` or
                    ``"dnd5e"``.  ``None`` means it covers multiple systems.
        url:        Canonical URL for the source (used by Grug in citations).
    """

    source_id: str
    name: str
    description: str
    system: str | None
    url: str


#: All built-in sources, in the order they should appear in the web UI.
BUILTIN_RULE_SOURCES: list[BuiltinRuleSource] = [
    BuiltinRuleSource(
        source_id="aon_pf2e",
        name="Archives of Nethys (PF2e)",
        description=(
            "The official Paizo-partnered SRD for Pathfinder 2e — near-complete "
            "coverage of all rulebooks, supplements, Adventure Paths, and "
            "Pathfinder Society content, updated within weeks of release. "
            "Backed by Elasticsearch for genuine free-text relevance search "
            "across spells, feats, monsters, items, conditions, and rules text."
        ),
        system="pf2e",
        url="https://2e.aonprd.com",
    ),
    BuiltinRuleSource(
        source_id="srd_5e",
        name="D&D 5e SRD (dnd5eapi.co)",
        description=(
            "Community REST/GraphQL API covering the official D&D 5e 2014 "
            "Systems Reference Document — spells, monsters, classes, equipment, "
            "magic items, conditions, and features. "
            "Note: SRD content only; non-SRD subclasses, most named monsters, "
            "and the 2024 revised rulebooks are not included."
        ),
        system="dnd5e",
        url="https://www.dnd5eapi.co",
    ),
]

#: Look-up by source_id for O(1) access.
BUILTIN_SOURCES_BY_ID: dict[str, BuiltinRuleSource] = {
    src.source_id: src for src in BUILTIN_RULE_SOURCES
}
