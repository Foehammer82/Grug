"""Passive skill/perception score computation.

Computes the "passive score" for a given skill from a character's
``structured_data`` dict.  The formula differs by game system:

**D&D 5e**
    ``passive = 10 + skill_modifier``

    The modifier is read directly from ``skills.<skill_name>``
    (already the total modifier on the sheet).  For perception the
    pre-computed ``passive_perception`` field is preferred when present.

**Pathfinder 2e**
    ``passive (DC) = 10 + ability_mod + proficiency``

    where *proficiency* equals ``level + rank`` when trained (rank ≥ 2)
    and ``0`` when untrained (rank 0).  The ability that governs a skill
    is looked up from :data:`PF2E_SKILL_ABILITY`.
"""

from __future__ import annotations

import math
from typing import Any

# ── Ability mappings ──────────────────────────────────────────────────────

#: D&D 5e: skill name → governing ability (abbreviated).
DND5E_SKILL_ABILITY: dict[str, str] = {
    "acrobatics": "DEX",
    "animal_handling": "WIS",
    "animal": "WIS",  # alternate spelling in DnD5eSkills model
    "arcana": "INT",
    "athletics": "STR",
    "deception": "CHA",
    "history": "INT",
    "insight": "WIS",
    "intimidation": "CHA",
    "investigation": "INT",
    "medicine": "WIS",
    "nature": "INT",
    "perception": "WIS",
    "performance": "CHA",
    "persuasion": "CHA",
    "religion": "INT",
    "sleight_of_hand": "DEX",
    "sleightofhand": "DEX",  # alternate spelling
    "stealth": "DEX",
    "survival": "WIS",
}

#: PF2e: skill name → governing ability (abbreviated).
PF2E_SKILL_ABILITY: dict[str, str] = {
    "perception": "WIS",
    "acrobatics": "DEX",
    "arcana": "INT",
    "athletics": "STR",
    "crafting": "INT",
    "deception": "CHA",
    "diplomacy": "CHA",
    "intimidation": "CHA",
    "medicine": "WIS",
    "nature": "WIS",
    "occultism": "INT",
    "performance": "CHA",
    "religion": "WIS",
    "society": "INT",
    "stealth": "DEX",
    "survival": "WIS",
    "thievery": "DEX",
}


def _ability_mod(score: int | None) -> int | None:
    """Compute the ability modifier from a raw ability score."""
    if score is None:
        return None
    return math.floor((score - 10) / 2)


# ── Public API ────────────────────────────────────────────────────────────


def normalize_skill_key(skill: str) -> str:
    """Normalize a skill name for lookup: lowercase, strip, spaces → underscores."""
    return skill.strip().lower().replace(" ", "_")


def compute_passive_score(
    structured_data: dict[str, Any],
    skill: str = "perception",
) -> int | None:
    """Compute a passive score for *skill* from character structured data.

    Returns ``None`` when there is not enough data to calculate.

    Parameters
    ----------
    structured_data:
        The character's ``structured_data`` dict (as stored in the DB).
    skill:
        Skill name to compute the passive for (default ``"perception"``).
        Case-insensitive; spaces are converted to underscores.
    """
    if not structured_data:
        return None

    system = (structured_data.get("system") or "unknown").lower()
    skill_key = normalize_skill_key(skill)

    if system == "dnd5e":
        return _passive_dnd5e(structured_data, skill_key)
    if system == "pf2e":
        return _passive_pf2e(structured_data, skill_key)
    return None


# ── D&D 5e ────────────────────────────────────────────────────────────────


def _passive_dnd5e(data: dict[str, Any], skill: str) -> int | None:
    """D&D 5e passive = 10 + skill modifier."""
    # Prefer the pre-computed passive_perception when available.
    if skill == "perception":
        pp = data.get("passive_perception")
        if pp is not None and isinstance(pp, int):
            return pp

    # Try reading the modifier from the skills dict.
    skills = data.get("skills") or {}
    if isinstance(skills, dict):
        mod = skills.get(skill)
        if mod is not None and isinstance(mod, (int, float)):
            return 10 + int(mod)

    # Fallback: derive from ability score alone (no proficiency).
    ability_key = DND5E_SKILL_ABILITY.get(skill)
    if ability_key:
        scores = data.get("ability_scores") or {}
        if isinstance(scores, dict):
            score = scores.get(ability_key)
            mod = _ability_mod(score)
            if mod is not None:
                return 10 + mod

    return None


# ── Pathfinder 2e ─────────────────────────────────────────────────────────


def _passive_pf2e(data: dict[str, Any], skill: str) -> int | None:
    """PF2e passive DC = 10 + ability_mod + proficiency.

    Proficiency = level + rank when trained (rank ≥ 2), else 0.
    """
    level = data.get("level")
    if not isinstance(level, int):
        return None

    # Determine the governing ability.
    ability_key = PF2E_SKILL_ABILITY.get(skill)
    if ability_key is None:
        return None

    scores = data.get("ability_scores") or {}
    if isinstance(scores, dict):
        score_val = scores.get(ability_key)
    else:
        score_val = None
    ability_mod = _ability_mod(score_val) if score_val is not None else 0

    # Look up the proficiency rank.
    # Perception has a top-level field; other skills live in `proficiencies`.
    if skill == "perception":
        rank = data.get("perception")
        if rank is None:
            profs = data.get("proficiencies") or {}
            rank = profs.get("perception")
    else:
        profs = data.get("proficiencies") or {}
        rank = profs.get(skill)

    if rank is None or not isinstance(rank, (int, float)):
        # No rank data available.  If we at least have the governing
        # ability score, return a best-effort untrained estimate.
        if score_val is not None:
            return 10 + ability_mod
        return None

    rank = int(rank)
    # Untrained (rank 0): no level added.
    # Trained+ (rank ≥ 2): proficiency = level + rank.
    proficiency = (level + rank) if rank >= 2 else 0
    return 10 + ability_mod + proficiency
