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

from grug.character.models import (
    CharacterAbilityScores,
    CharacterHP,
    PF2eAttack,
    PF2eCurrency,
    PF2eCharacterSheet,
    PF2eLoreSkill,
    PF2eSavingThrows,
    PF2eSpellCaster,
    PF2eSpellLevel,
    sheet_to_dict,
)

logger = logging.getLogger(__name__)

_PATHBUILDER_URL = "https://pathbuilder2e.com/json.php"

_REQUEST_TIMEOUT = 15.0  # seconds


class PathbuilderError(Exception):
    """Raised when a Pathbuilder fetch fails."""


def parse_pathbuilder_response(
    data: dict[str, Any], pathbuilder_id: int
) -> dict[str, Any]:
    """Normalise a pre-fetched Pathbuilder JSON response.

    Accepts the raw response dict ``{"success": bool, "build": {...}}`` as
    returned by the Pathbuilder ``json.php`` endpoint and returns the
    normalised build dict ready for storage in ``Character.structured_data``.

    This is separated from :func:`fetch_pathbuilder_character` so that callers
    who already have the raw JSON (e.g. fetched client-side in the browser to
    bypass Cloudflare bot protection) can normalise it without a server-side
    HTTP request.

    Raises
    ------
    PathbuilderError
        If ``data`` is missing required fields or ``success`` is false.
    """
    if not data.get("success"):
        raise PathbuilderError(
            "Pathbuilder returned success=false — character not found or private"
        )

    build = data.get("build")
    if not isinstance(build, dict):
        raise PathbuilderError("Pathbuilder response missing 'build' object")

    return sheet_to_dict(_normalise_build(build, pathbuilder_id))


async def fetch_pathbuilder_character(pathbuilder_id: int) -> dict[str, Any]:
    """Fetch a character from Pathbuilder by ID and return the build dict.

    Returns the raw ``build`` object from the Pathbuilder response, serialised
    to a plain dict ready for storage in ``Character.structured_data``.

    .. note::
        The Pathbuilder ``json.php`` endpoint is behind Cloudflare bot
        protection that blocks server-side HTTP clients.  Prefer passing
        pre-fetched data (fetched client-side in the browser) via
        :func:`parse_pathbuilder_response` when possible.

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

    return parse_pathbuilder_response(data, pathbuilder_id)


def _normalise_build(build: dict[str, Any], pathbuilder_id: int) -> PF2eCharacterSheet:
    """Normalise a Pathbuilder build dict into a ``PF2eCharacterSheet``.

    The full Pathbuilder build is preserved under ``extra.pathbuilder_build``
    for system-specific rendering.  Top-level fields match the Claude
    extraction schema so both import paths render identically in the web UI.
    """
    abilities = build.get("abilities", {})
    ability_scores = CharacterAbilityScores(
        STR=abilities.get("str"),
        DEX=abilities.get("dex"),
        CON=abilities.get("con"),
        INT=abilities.get("int"),
        WIS=abilities.get("wis"),
        CHA=abilities.get("cha"),
    )

    # HP — Pathbuilder doesn't track current HP, only build-time max.
    hp_val = build.get("hitPoints") or build.get("hp")
    hp = CharacterHP(
        current=None,
        max=hp_val if isinstance(hp_val, int) else None,
        temp=None,
    )

    # Speed
    speed = build.get("speed")
    speed_str = (
        f"{speed} ft" if isinstance(speed, int) else str(speed) if speed else None
    )

    # AC
    ac_raw = build.get("acTotal") or build.get("ac")
    ac = ac_raw if isinstance(ac_raw, int) else None

    # Feats — flatten Pathbuilder's nested feat arrays into simple strings.
    feats_raw = build.get("feats", [])
    features: list[str] = []
    for feat in feats_raw:
        if isinstance(feat, list) and len(feat) >= 1:
            feat_name = str(feat[0])
            feat_type = str(feat[3]) if len(feat) > 3 else ""
            features.append(f"{feat_name} ({feat_type})" if feat_type else feat_name)
        elif isinstance(feat, str):
            features.append(feat)

    specials = build.get("specials", [])
    if isinstance(specials, list):
        features.extend(str(s) for s in specials if s)

    # Equipment
    equipment_raw = build.get("equipment", [])
    inventory: list[str] = []
    for item in equipment_raw:
        if isinstance(item, list) and len(item) >= 1:
            item_name = str(item[0])
            qty = item[1] if len(item) > 1 else 1
            inventory.append(
                f"{item_name} (x{qty})"
                if isinstance(qty, int) and qty > 1
                else item_name
            )
        elif isinstance(item, str):
            inventory.append(item)

    # Weapons
    weapons_raw = build.get("weapons", [])
    attacks: list[PF2eAttack] = []
    for w in weapons_raw:
        if isinstance(w, dict):
            # Pathbuilder may send striking rune as '' when unset — coerce to int.
            striking_raw = w.get("str", 0)
            try:
                striking_val = int(striking_raw) if striking_raw != "" else 0
            except (TypeError, ValueError):
                striking_val = 0
            attacks.append(
                PF2eAttack(
                    name=w.get("display") or w.get("name"),
                    display=w.get("display"),
                    die=str(w.get("die", "")) or None,
                    damage_type=w.get("damageType"),
                    runes=w.get("runes") or [],
                    pot=w.get("pot", 0),
                    striking=striking_val,
                )
            )

    # Spellcasters
    spellcasters_raw = build.get("spellCasters", [])
    spells: list[PF2eSpellCaster] = []
    for caster in spellcasters_raw:
        if isinstance(caster, dict):
            spells_by_level: list[PF2eSpellLevel] = []
            for spell_level_data in caster.get("spells", []):
                if isinstance(spell_level_data, dict):
                    spells_by_level.append(
                        PF2eSpellLevel(
                            level=spell_level_data.get("spellLevel", 0),
                            spells=spell_level_data.get("list", []),
                        )
                    )
            spells.append(
                PF2eSpellCaster(
                    tradition=caster.get("magicTradition"),
                    type=caster.get("spellcastingType"),
                    ability=caster.get("ability"),
                    per_day=caster.get("perDay") or [],
                    focus_points=caster.get("focusPoints", 0),
                    spells_by_level=spells_by_level,
                )
            )

    # Lore skills
    lores = build.get("lores", [])
    lore_skills: list[PF2eLoreSkill] = []
    for lore in lores:
        if isinstance(lore, list) and len(lore) >= 2:
            lore_skills.append(PF2eLoreSkill(name=str(lore[0]), rank=lore[1]))

    # Currency
    money = build.get("money") or {}
    currency = (
        PF2eCurrency(
            pp=money.get("pp", 0),
            gp=money.get("gp", 0),
            sp=money.get("sp", 0),
            cp=money.get("cp", 0),
        )
        if isinstance(money, dict)
        else PF2eCurrency()
    )

    # Proficiencies and saving throws
    profs: dict[str, Any] = build.get("proficiencies") or {}
    saving_throws = PF2eSavingThrows(
        fortitude=profs.get("fortitude"),
        reflex=profs.get("reflex"),
        will=profs.get("will"),
    )

    languages_raw = build.get("languages", [])
    languages: list[str] = (
        [str(lang) for lang in languages_raw] if isinstance(languages_raw, list) else []
    )

    # Size — Pathbuilder sends an integer (0=Tiny,1=Small,2=Medium,3=Large,
    # 4=Huge,5=Gargantuan).  The schema field is str|None so map it here.
    _PF2E_SIZE_NAMES: dict[int, str] = {
        0: "Tiny",
        1: "Small",
        2: "Medium",
        3: "Large",
        4: "Huge",
        5: "Gargantuan",
    }
    size_raw = build.get("size")
    if isinstance(size_raw, int):
        size_str_val: str | None = _PF2E_SIZE_NAMES.get(size_raw, str(size_raw))
    elif isinstance(size_raw, str):
        size_str_val = size_raw or None
    else:
        size_str_val = None

    return PF2eCharacterSheet(
        system="pf2e",
        name=build.get("name"),
        player_name=None,
        level=build.get("level"),
        class_and_subclass=build.get("class"),
        dual_class=build.get("dualClass"),
        race_or_ancestry=build.get("ancestry"),
        heritage=build.get("heritage"),
        background=build.get("background"),
        alignment=build.get("alignment"),
        deity=build.get("deity"),
        size=size_str_val,
        key_ability=build.get("keyability"),
        age=str(build.get("age")) if build.get("age") else None,
        gender=build.get("gender"),
        hp=hp,
        ability_scores=ability_scores,
        armor_class=ac,
        speed=speed_str,
        initiative=None,
        perception=profs.get("perception"),
        saving_throws=saving_throws,
        proficiencies={k: v for k, v in profs.items()},
        lore_skills=lore_skills,
        attacks=attacks,
        weapons=weapons_raw,
        armor=build.get("armor") or [],
        spells=spells,
        features_and_traits=features,
        inventory=inventory,
        currency=currency,
        languages=languages,
        notes=None,
        extra={
            "pathbuilder_build": build,
            "focus": build.get("focus"),
            "formula": build.get("formula"),
            "rituals": build.get("rituals"),
        },
    )
