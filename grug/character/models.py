"""Pydantic models for character sheet structured data.

These models provide typed access to the JSON stored in
``Character.structured_data``.  The on-disk / in-DB format is a plain dict;
use :func:`parse_character_sheet` to get a typed model from the dict, and
``.model_dump(mode="json")`` to serialize back for storage.

Systems
-------
- ``DnD5eCharacterSheet``    — D&D 5e (extracted by Claude or form-fill)
- ``PF2eCharacterSheet``     — Pathfinder 2e (from Pathbuilder or Claude)
- ``UnknownCharacterSheet``  — Any other / homebrew system

All models use ``extra="allow"`` so that unrecognised fields from older
records or future Claude extractions are round-tripped without loss.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# ── Sub-models shared by all systems ──────────────────────────────────────


class CharacterHP(BaseModel):
    """Hit points — current, max, and temporary."""

    model_config = ConfigDict(extra="allow")

    current: int | None = None
    max: int | None = None
    temp: int | None = None


class CharacterAbilityScores(BaseModel):
    """The six core ability scores."""

    model_config = ConfigDict(extra="allow")

    STR: int | None = None
    DEX: int | None = None
    CON: int | None = None
    INT: int | None = None
    WIS: int | None = None
    CHA: int | None = None


# ── D&D 5e sub-models ─────────────────────────────────────────────────────


class DnD5eSavingThrows(BaseModel):
    """D&D 5e saving throw totals (ability modifier + proficiency if proficient)."""

    model_config = ConfigDict(extra="allow")

    strength: int | None = None
    dexterity: int | None = None
    constitution: int | None = None
    intelligence: int | None = None
    wisdom: int | None = None
    charisma: int | None = None
    # Abbreviated aliases stored by some extractors.
    STR: int | None = None
    DEX: int | None = None
    CON: int | None = None
    INT: int | None = None
    WIS: int | None = None
    CHA: int | None = None

    def get_save(self, ability: str) -> int | None:
        """Return the save value for *ability* (accepts full name or abbreviation)."""
        abbr_map = {
            "strength": "STR",
            "dexterity": "DEX",
            "constitution": "CON",
            "intelligence": "INT",
            "wisdom": "WIS",
            "charisma": "CHA",
        }
        full_map = {v: k for k, v in abbr_map.items()}
        key = ability.lower()
        # Try full name first, then abbreviation.
        val = getattr(self, key, None)
        if val is None:
            abbr = abbr_map.get(key)
            if abbr:
                val = getattr(self, abbr, None)
        if val is None:
            full = full_map.get(ability.upper())
            if full:
                val = getattr(self, full, None)
        return val


class DnD5eSkills(BaseModel):
    """D&D 5e skill check totals (ability modifier + proficiency, if applicable)."""

    model_config = ConfigDict(extra="allow")

    acrobatics: int | None = None
    animal_handling: int | None = None
    arcana: int | None = None
    athletics: int | None = None
    deception: int | None = None
    history: int | None = None
    insight: int | None = None
    intimidation: int | None = None
    investigation: int | None = None
    medicine: int | None = None
    nature: int | None = None
    perception: int | None = None
    performance: int | None = None
    persuasion: int | None = None
    religion: int | None = None
    sleight_of_hand: int | None = None
    stealth: int | None = None
    survival: int | None = None
    # Alternate spellings sometimes emitted by Claude.
    animal: int | None = None
    sleightofhand: int | None = None


class DnD5eAttack(BaseModel):
    """A single weapon / attack entry on a D&D 5e sheet."""

    model_config = ConfigDict(extra="allow")

    name: str | None = None
    attack_bonus: int | None = None
    to_hit: str | None = None  # formatted string e.g. "+5"
    damage: str | None = None  # e.g. "1d6+3 slashing"
    die: str | None = None  # raw die string e.g. "1d6"
    damage_type: str | None = None
    reach: str | None = None
    notes: str | None = None


class DnD5eCurrency(BaseModel):
    """D&D 5e coin purse."""

    model_config = ConfigDict(extra="allow")

    cp: int | None = None
    sp: int | None = None
    ep: int | None = None
    gp: int | None = None
    pp: int | None = None


# ── D&D 5e character sheet ────────────────────────────────────────────────


class DnD5eCharacterSheet(BaseModel):
    """Structured data for a D&D 5th Edition character."""

    model_config = ConfigDict(extra="allow")

    # Discriminator — always "dnd5e"
    system: Literal["dnd5e"] = "dnd5e"

    # Identity
    name: str | None = None
    player_name: str | None = None
    level: int | None = None
    class_and_subclass: str | None = None
    race_or_ancestry: str | None = None
    background: str | None = None
    alignment: str | None = None
    xp: int | None = None

    # Appearance / background
    age: str | None = None
    height: str | None = None
    weight: str | None = None
    eyes: str | None = None
    skin: str | None = None
    hair: str | None = None

    # Core stats
    ability_scores: CharacterAbilityScores = Field(
        default_factory=CharacterAbilityScores
    )
    hp: CharacterHP = Field(default_factory=CharacterHP)
    armor_class: int | None = None
    speed: str | None = None
    initiative: int | None = None
    proficiency_bonus: int | None = None
    passive_perception: int | None = None
    inspiration: bool | int | None = None

    # Hit dice
    hit_dice: str | None = None  # e.g. "1d10"
    hit_dice_total: str | None = None  # e.g. "5d10"

    # Death saves
    death_save_successes: int | None = None
    death_save_failures: int | None = None

    # Proficiency & saving throws
    saving_throws: DnD5eSavingThrows = Field(default_factory=DnD5eSavingThrows)
    skills: DnD5eSkills = Field(default_factory=DnD5eSkills)
    proficiencies_text: str | None = None

    # Combat
    attacks: list[DnD5eAttack] = Field(default_factory=list)

    # Magic
    spells: list[dict[str, Any]] = Field(default_factory=list)
    spell_save_dc: int | None = None
    spell_attack_bonus: int | None = None

    # Gear / loot
    inventory: list[str] = Field(default_factory=list)
    currency: DnD5eCurrency = Field(default_factory=DnD5eCurrency)
    treasure: str | None = None

    # Features
    features_and_traits: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)

    # Personality (page 2 of the official sheet)
    personality_traits: str | None = None
    ideals: str | None = None
    bonds: str | None = None
    flaws: str | None = None
    backstory: str | None = None
    allies: str | None = None

    # Free-form notes (not the character's in-game notes)
    notes: str | None = None

    # Catch-all for any extra fields the extractor or future versions add
    extra: dict[str, Any] = Field(default_factory=dict)


# ── PF2e sub-models ───────────────────────────────────────────────────────


class PF2eSavingThrows(BaseModel):
    """PF2e saving throw proficiency ranks (0 = Untrained … 8 = Legendary in raw Pathbuilder values)."""

    model_config = ConfigDict(extra="allow")

    fortitude: int | None = None
    reflex: int | None = None
    will: int | None = None


class PF2eAttack(BaseModel):
    """A weapon entry from a PF2e character (Pathbuilder format)."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    name: str | None = None
    display: str | None = None  # friendly display name
    die: str | None = None
    damage_type: str | None = None
    runes: list[str] = Field(default_factory=list)
    pot: int = 0  # potency rune bonus
    striking: int = Field(0, alias="str")  # striking rune bonus


class PF2eSpellLevel(BaseModel):
    """Spells known / memorised at a specific spell level for a PF2e caster."""

    model_config = ConfigDict(extra="allow")

    level: int = 0
    spells: list[str] = Field(default_factory=list)


class PF2eSpellCaster(BaseModel):
    """A single spellcasting tradition/class entry in a PF2e character."""

    model_config = ConfigDict(extra="allow")

    tradition: str | None = None
    type: str | None = None  # e.g. "Prepared", "Spontaneous"
    ability: str | None = None  # key spellcasting ability
    per_day: list[int] = Field(default_factory=list)
    focus_points: int = 0
    spells_by_level: list[PF2eSpellLevel] = Field(default_factory=list)


class PF2eLoreSkill(BaseModel):
    """A Lore skill specific to a PF2e character."""

    model_config = ConfigDict(extra="allow")

    name: str
    rank: int = 0


class PF2eCurrency(BaseModel):
    """PF2e coin purse (platinum, gold, silver, copper)."""

    model_config = ConfigDict(extra="allow")

    pp: int = 0
    gp: int = 0
    sp: int = 0
    cp: int = 0


# ── PF2e character sheet ──────────────────────────────────────────────────


class PF2eCharacterSheet(BaseModel):
    """Structured data for a Pathfinder 2nd Edition character."""

    model_config = ConfigDict(extra="allow")

    # Discriminator — always "pf2e"
    system: Literal["pf2e"] = "pf2e"

    # Identity
    name: str | None = None
    player_name: str | None = None
    level: int | None = None
    class_and_subclass: str | None = None  # primary class
    dual_class: str | None = None
    race_or_ancestry: str | None = None
    heritage: str | None = None
    background: str | None = None
    alignment: str | None = None
    deity: str | None = None
    size: str | None = None
    key_ability: str | None = None

    # Appearance
    age: str | None = None
    gender: str | None = None

    # Core stats
    ability_scores: CharacterAbilityScores = Field(
        default_factory=CharacterAbilityScores
    )
    hp: CharacterHP = Field(default_factory=CharacterHP)
    armor_class: int | None = None
    speed: str | None = None
    initiative: int | None = None
    perception: int | None = None  # proficiency rank

    # Saving throws (ranks, not modifiers)
    saving_throws: PF2eSavingThrows = Field(default_factory=PF2eSavingThrows)

    # Proficiency ranks — flat dict keyed by skill/category name
    # Values follow Pathbuilder: 0 = Untrained, 2 = Trained, 4 = Expert, 6 = Master, 8 = Legendary
    proficiencies: dict[str, int | None] = Field(default_factory=dict)

    # Lore skills (character-specific, not in the standard set)
    lore_skills: list[PF2eLoreSkill] = Field(default_factory=list)

    # Combat
    attacks: list[PF2eAttack] = Field(default_factory=list)
    weapons: list[dict[str, Any]] = Field(
        default_factory=list
    )  # raw Pathbuilder weapon dicts
    armor: list[dict[str, Any]] = Field(
        default_factory=list
    )  # raw Pathbuilder armor dicts

    # Magic
    spells: list[PF2eSpellCaster] = Field(default_factory=list)

    # Gear / loot
    inventory: list[str] = Field(default_factory=list)
    currency: PF2eCurrency = Field(default_factory=PF2eCurrency)

    # Features
    features_and_traits: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)

    # Free-form notes
    notes: str | None = None

    # Catch-all for any extra Pathbuilder fields
    extra: dict[str, Any] = Field(default_factory=dict)


# ── Unknown / homebrew character sheet ────────────────────────────────────


class UnknownCharacterSheet(BaseModel):
    """Structured data for any game system Grug doesn't recognise."""

    model_config = ConfigDict(extra="allow")

    system: str = "unknown"

    name: str | None = None
    player_name: str | None = None
    level: int | None = None
    class_and_subclass: str | None = None
    race_or_ancestry: str | None = None
    background: str | None = None
    alignment: str | None = None
    hp: CharacterHP = Field(default_factory=CharacterHP)
    ability_scores: CharacterAbilityScores = Field(
        default_factory=CharacterAbilityScores
    )
    armor_class: int | None = None
    speed: str | None = None
    saving_throws: dict[str, Any] = Field(default_factory=dict)
    skills: dict[str, Any] = Field(default_factory=dict)
    attacks: list[dict[str, Any]] = Field(default_factory=list)
    spells: list[dict[str, Any]] = Field(default_factory=list)
    features_and_traits: list[str] = Field(default_factory=list)
    inventory: list[str] = Field(default_factory=list)
    currency: dict[str, Any] = Field(default_factory=dict)
    languages: list[str] = Field(default_factory=list)
    notes: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


# ── Union type ────────────────────────────────────────────────────────────

# Convenience type alias for any character sheet.
CharacterSheet = DnD5eCharacterSheet | PF2eCharacterSheet | UnknownCharacterSheet


# ── Factory function ──────────────────────────────────────────────────────


def parse_character_sheet(
    data: dict[str, Any] | None,
) -> DnD5eCharacterSheet | PF2eCharacterSheet | UnknownCharacterSheet | None:
    """Parse a raw structured_data dict from the DB into a typed model.

    Dispatches to the correct model based on the ``"system"`` field.
    Returns ``None`` if *data* is ``None`` or empty.

    Parameters
    ----------
    data:
        Raw JSON dict as stored in ``Character.structured_data``.

    Returns
    -------
    A typed :class:`DnD5eCharacterSheet`, :class:`PF2eCharacterSheet`, or
    :class:`UnknownCharacterSheet`, or ``None``.
    """
    if not data:
        return None
    system = data.get("system", "unknown") or "unknown"
    if system == "dnd5e":
        return DnD5eCharacterSheet.model_validate(data)
    if system == "pf2e":
        return PF2eCharacterSheet.model_validate(data)
    return UnknownCharacterSheet.model_validate(data)


def sheet_to_dict(
    sheet: DnD5eCharacterSheet | PF2eCharacterSheet | UnknownCharacterSheet,
) -> dict[str, Any]:
    """Serialise a character sheet model to a JSON-safe dict for DB storage.

    Uses ``model_dump(mode="json")`` so all sub-models are recursively
    serialised to plain Python types.  Excludes ``None``-valued fields
    that were never set so old records don't get polluted with nulls.
    """
    return sheet.model_dump(mode="json", exclude_none=False)
