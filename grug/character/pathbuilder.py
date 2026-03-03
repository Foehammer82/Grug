"""Pathbuilder 2e integration — fetch character data by Pathbuilder ID.

The public (unofficial) JSON endpoint returns the full Pathbuilder character
build, which is much richer than Claude-extracted structured_data.  This
module fetches and lightly normalises the response so it can be stored
directly in ``Character.structured_data``.

Endpoint: ``https://pathbuilder2e.com/json.php?id={pathbuilder_id}``
Auth: None required (public, unauthenticated)
Rate limits: Unknown — be polite, cache aggressively, only fetch on user action.
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_PATHBUILDER_URL = "https://pathbuilder2e.com/json.php"
_REQUEST_TIMEOUT = 15.0  # seconds


class PathbuilderError(Exception):
    """Raised when a Pathbuilder fetch fails."""


async def fetch_pathbuilder_character(pathbuilder_id: int) -> dict[str, Any]:
    """Fetch a character from Pathbuilder by ID and return the build dict.

    Returns the raw ``build`` object from the Pathbuilder response, wrapped
    with a ``_source: "pathbuilder"`` marker and the original ID for
    re-sync purposes.

    Raises
    ------
    PathbuilderError
        If the request fails, the character is not found, or the response
        is malformed.
    """
    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
        try:
            resp = await client.get(_PATHBUILDER_URL, params={"id": pathbuilder_id})
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise PathbuilderError(
                f"Pathbuilder returned HTTP {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            raise PathbuilderError(f"Failed to reach Pathbuilder: {exc}") from exc

    try:
        data = resp.json()
    except Exception as exc:
        raise PathbuilderError("Pathbuilder returned invalid JSON") from exc

    if not data.get("success"):
        raise PathbuilderError(
            "Pathbuilder returned success=false — character not found or private"
        )

    build = data.get("build")
    if not isinstance(build, dict):
        raise PathbuilderError("Pathbuilder response missing 'build' object")

    return _normalise_build(build, pathbuilder_id)


def _normalise_build(build: dict[str, Any], pathbuilder_id: int) -> dict[str, Any]:
    """Normalise a Pathbuilder build into a structure compatible with
    Grug's ``CharacterSheet`` type while preserving the full Pathbuilder data.

    The top-level keys match the Claude extraction schema so the web UI
    can render both Pathbuilder-sourced and upload-sourced characters with
    the same components.  The full Pathbuilder build is preserved under
    ``extra.pathbuilder_build`` for system-specific rendering.
    """
    abilities = build.get("abilities", {})
    # Pathbuilder stores raw ability scores (10-based)
    ability_scores = {
        "STR": abilities.get("str"),
        "DEX": abilities.get("dex"),
        "CON": abilities.get("con"),
        "INT": abilities.get("int"),
        "WIS": abilities.get("wis"),
        "CHA": abilities.get("cha"),
    }

    # HP — Pathbuilder doesn't track current HP, only build-time max
    # We'll leave current as None (mutable_state will handle it later)
    hp_val = build.get("hitPoints") or build.get("hp")
    hp = {
        "current": None,
        "max": hp_val if isinstance(hp_val, int) else None,
        "temp": None,
    }

    # Speed
    speed = build.get("speed")
    speed_str = (
        f"{speed} ft" if isinstance(speed, int) else str(speed) if speed else None
    )

    # AC — Pathbuilder may store a computed AC or not; check common locations
    ac = build.get("acTotal") or build.get("ac")

    # Feats — flatten Pathbuilder's nested feat arrays into simple strings
    feats_raw = build.get("feats", [])
    features: list[str] = []
    for feat in feats_raw:
        if isinstance(feat, list) and len(feat) >= 1:
            name = str(feat[0])
            feat_type = str(feat[3]) if len(feat) > 3 else ""
            if feat_type:
                features.append(f"{name} ({feat_type})")
            else:
                features.append(name)
        elif isinstance(feat, str):
            features.append(feat)

    # Specials (class features, heritage abilities, etc.)
    specials = build.get("specials", [])
    if isinstance(specials, list):
        features.extend(str(s) for s in specials if s)

    # Equipment
    equipment_raw = build.get("equipment", [])
    inventory: list[str] = []
    for item in equipment_raw:
        if isinstance(item, list) and len(item) >= 1:
            name = str(item[0])
            qty = item[1] if len(item) > 1 else 1
            if isinstance(qty, int) and qty > 1:
                inventory.append(f"{name} (x{qty})")
            else:
                inventory.append(name)
        elif isinstance(item, str):
            inventory.append(item)

    # Weapons
    weapons_raw = build.get("weapons", [])
    attacks: list[dict[str, Any]] = []
    for w in weapons_raw:
        if isinstance(w, dict):
            attacks.append(
                {
                    "name": w.get("display") or w.get("name", "Unknown"),
                    "die": w.get("die", ""),
                    "damage_type": w.get("damageType", ""),
                    "runes": w.get("runes", []),
                    "pot": w.get("pot", 0),
                    "str": w.get("str", 0),
                }
            )

    # Spellcasters
    spellcasters_raw = build.get("spellCasters", [])
    spells: list[dict[str, Any]] = []
    for caster in spellcasters_raw:
        if isinstance(caster, dict):
            spell_entry: dict[str, Any] = {
                "tradition": caster.get("magicTradition", ""),
                "type": caster.get("spellcastingType", ""),
                "ability": caster.get("ability", ""),
                "per_day": caster.get("perDay", []),
                "focus_points": caster.get("focusPoints", 0),
                "spells_by_level": [],
            }
            for spell_level_data in caster.get("spells", []):
                if isinstance(spell_level_data, dict):
                    spell_entry["spells_by_level"].append(
                        {
                            "level": spell_level_data.get("spellLevel", 0),
                            "spells": spell_level_data.get("list", []),
                        }
                    )
            spells.append(spell_entry)

    # Lore skills
    lores = build.get("lores", [])
    lore_skills: list[dict[str, Any]] = []
    for lore in lores:
        if isinstance(lore, list) and len(lore) >= 2:
            lore_skills.append({"name": str(lore[0]), "rank": lore[1]})

    # Currency
    money = build.get("money", {})
    currency = {}
    if isinstance(money, dict):
        currency = {
            "pp": money.get("pp", 0),
            "gp": money.get("gp", 0),
            "sp": money.get("sp", 0),
            "cp": money.get("cp", 0),
        }

    # Proficiencies
    profs = build.get("proficiencies", {})

    # Languages
    languages = build.get("languages", [])

    return {
        "_source": "pathbuilder",
        "_pathbuilder_id": pathbuilder_id,
        "system": "pf2e",
        "name": build.get("name"),
        "player_name": None,
        "level": build.get("level"),
        "class_and_subclass": build.get("class"),
        "dual_class": build.get("dualClass"),
        "race_or_ancestry": build.get("ancestry"),
        "heritage": build.get("heritage"),
        "background": build.get("background"),
        "alignment": build.get("alignment"),
        "deity": build.get("deity"),
        "size": build.get("size"),
        "key_ability": build.get("keyability"),
        "hp": hp,
        "ability_scores": ability_scores,
        "armor_class": ac if isinstance(ac, int) else None,
        "speed": speed_str,
        "initiative": None,  # Pathbuilder doesn't export a computed initiative
        "proficiency_bonus": None,  # PF2e doesn't use this concept
        "saving_throws": {
            "fortitude": profs.get("fortitude"),
            "reflex": profs.get("reflex"),
            "will": profs.get("will"),
        },
        "perception": profs.get("perception"),
        "skills": {},  # TODO: compute from proficiencies + ability mods + level
        "attacks": attacks,
        "spells": spells,
        "features_and_traits": features,
        "lore_skills": lore_skills,
        "inventory": inventory,
        "weapons": weapons_raw,
        "armor": build.get("armor", []),
        "currency": currency,
        "languages": languages if isinstance(languages, list) else [],
        "notes": None,
        "proficiencies": profs,
        "extra": {
            "pathbuilder_build": build,
            "age": build.get("age"),
            "gender": build.get("gender"),
            "focus": build.get("focus"),
            "formula": build.get("formula"),
            "rituals": build.get("rituals"),
        },
    }
