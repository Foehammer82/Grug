"""Dice rolling engine — parse standard notation, roll cryptographically fair dice.

Supports:
- Basic:         ``d20``, ``1d6``, ``2d8``
- With modifier: ``1d20+5``, ``2d6-1``
- Keep highest:  ``4d6kh3`` (roll 4d6, keep highest 3)
- Keep lowest:   ``4d6kl1`` (roll 4d6, keep lowest 1)
- Compound:      ``2d6+1d4+3``
- Percentile:    ``d100``, ``d%``

All randomness uses :func:`secrets.randbelow` for cryptographic fairness.
"""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass, field
from enum import StrEnum


class RollType(StrEnum):
    """Categorises the purpose of a dice roll."""

    GENERAL = "general"
    ATTACK = "attack"
    DAMAGE = "damage"
    SAVING_THROW = "saving_throw"
    ABILITY_CHECK = "ability_check"
    INITIATIVE = "initiative"
    DEATH_SAVE = "death_save"
    SKILL_CHECK = "skill_check"


# Regex for a single dice term:  (count)d(sides)[kh|kl(keep)]
# Examples: d20, 2d6, 4d6kh3, 1d20kl1
_DICE_TERM_RE = re.compile(
    r"(?P<count>\d*)d(?P<sides>%|\d+)"
    r"(?:(?P<keep_mode>kh|kl)(?P<keep_count>\d+))?",
    re.IGNORECASE,
)

# Full expression tokeniser: dice terms, plain numbers, + or -
_TOKEN_RE = re.compile(
    r"(?P<dice>\d*d(?:%|\d+)(?:(?:kh|kl)\d+)?)"
    r"|(?P<number>\d+)"
    r"|(?P<op>[+\-])",
    re.IGNORECASE,
)


class DiceError(Exception):
    """Raised when a dice expression is invalid or contains illegal values."""


@dataclass
class DieResult:
    """Result of rolling a single die group (e.g. ``2d6``).

    Attributes:
        expression: The parsed dice expression string (e.g. ``"2d6kh1"``).
        sides: Number of sides per die.
        rolls: Every individual die roll, in order rolled.
        kept: Which rolls were kept (after kh/kl filtering).  Same as
              ``rolls`` when no keep filter is applied.
        total: Sum of kept rolls.
    """

    expression: str
    sides: int
    rolls: list[int]
    kept: list[int]
    total: int


@dataclass
class DiceResult:
    """Complete result of evaluating a dice expression.

    Attributes:
        expression: The original input expression string.
        components: Ordered list of ``(sign, DieResult | int)`` pairs.
            ``sign`` is ``1`` or ``-1``; the second element is either a
            :class:`DieResult` (for dice groups) or a plain ``int`` constant.
        grand_total: Final numeric result after summing all signed components.
        is_nat_1: True if the expression is a single d20 and the result is 1.
        is_nat_20: True if the expression is a single d20 and the result is 20.
    """

    expression: str
    components: list[tuple[int, DieResult | int]] = field(default_factory=list)
    grand_total: int = 0
    is_nat_1: bool = False
    is_nat_20: bool = False


# ---------------------------------------------------------------------------
# Core rolling
# ---------------------------------------------------------------------------


def _roll_die(sides: int) -> int:
    """Roll a single die with *sides* faces.  Returns 1-*sides* inclusive."""
    if sides < 1:
        raise DiceError(f"Die must have at least 1 side, got {sides}")
    return secrets.randbelow(sides) + 1


def _roll_dice_group(
    count: int,
    sides: int,
    keep_mode: str | None = None,
    keep_count: int | None = None,
) -> DieResult:
    """Roll *count* dice of *sides* faces and optionally keep highest/lowest."""
    if count < 1:
        raise DiceError(f"Must roll at least 1 die, got {count}")
    if count > 100:
        raise DiceError(f"Cannot roll more than 100 dice at once, got {count}")
    if sides > 1000:
        raise DiceError(f"Maximum die size is d1000, got d{sides}")

    rolls = [_roll_die(sides) for _ in range(count)]

    if keep_mode and keep_count is not None:
        if keep_count < 1 or keep_count > count:
            raise DiceError(
                f"Keep count must be between 1 and {count}, got {keep_count}"
            )
        sorted_rolls = sorted(rolls, reverse=(keep_mode.lower() == "kh"))
        kept = sorted_rolls[:keep_count]
    else:
        kept = list(rolls)

    expr_parts = [f"{count}d{sides}"]
    if keep_mode:
        expr_parts.append(f"{keep_mode}{keep_count}")

    return DieResult(
        expression="".join(expr_parts),
        sides=sides,
        rolls=rolls,
        kept=kept,
        total=sum(kept),
    )


# ---------------------------------------------------------------------------
# Expression parsing
# ---------------------------------------------------------------------------


def roll(expression: str) -> DiceResult:
    """Parse and evaluate a dice expression.

    Args:
        expression: A dice notation string, e.g. ``"2d6+1d4+3"``,
            ``"4d6kh3"``, ``"d20+5"``.

    Returns:
        A :class:`DiceResult` with the full breakdown.

    Raises:
        DiceError: If the expression is empty, malformed, or contains
            illegal values (too many dice, too many sides, etc.).
    """
    cleaned = expression.replace(" ", "").strip()
    if not cleaned:
        raise DiceError("Empty dice expression")

    # Tokenise
    tokens: list[tuple[str, str]] = []  # (type, value)
    pos = 0
    for m in _TOKEN_RE.finditer(cleaned):
        if m.start() != pos:
            bad = cleaned[pos : m.start()]
            raise DiceError(f"Unexpected characters in expression: '{bad}'")
        if m.group("dice"):
            tokens.append(("dice", m.group("dice")))
        elif m.group("number"):
            tokens.append(("number", m.group("number")))
        elif m.group("op"):
            tokens.append(("op", m.group("op")))
        pos = m.end()

    if pos != len(cleaned):
        raise DiceError(
            f"Unexpected characters at end of expression: '{cleaned[pos:]}'"
        )
    if not tokens:
        raise DiceError(f"Could not parse dice expression: '{expression}'")

    # Build signed component list
    components: list[tuple[int, DieResult | int]] = []
    sign = 1  # assume leading positive

    i = 0
    while i < len(tokens):
        tok_type, tok_val = tokens[i]

        if tok_type == "op":
            sign = 1 if tok_val == "+" else -1
            i += 1
            continue

        if tok_type == "number":
            components.append((sign, int(tok_val)))
            sign = 1  # reset
            i += 1
            continue

        if tok_type == "dice":
            dm = _DICE_TERM_RE.fullmatch(tok_val)
            if not dm:
                raise DiceError(f"Invalid dice term: '{tok_val}'")

            count_str = dm.group("count")
            count = int(count_str) if count_str else 1

            sides_str = dm.group("sides")
            sides = 100 if sides_str == "%" else int(sides_str)

            keep_mode = dm.group("keep_mode")
            keep_count_str = dm.group("keep_count")
            keep_count = int(keep_count_str) if keep_count_str else None

            die_result = _roll_dice_group(count, sides, keep_mode, keep_count)
            components.append((sign, die_result))
            sign = 1
            i += 1
            continue

        i += 1  # safety

    if not components:
        raise DiceError(f"No rollable components in expression: '{expression}'")

    # Compute grand total
    grand_total = 0
    for s, comp in components:
        if isinstance(comp, DieResult):
            grand_total += s * comp.total
        else:
            grand_total += s * comp

    # Check for natural 1/20 (only for lone d20 rolls)
    is_nat_1 = False
    is_nat_20 = False
    dice_components = [(s, c) for s, c in components if isinstance(c, DieResult)]
    if len(dice_components) == 1:
        _, die_comp = dice_components[0]
        if die_comp.sides == 20 and len(die_comp.kept) == 1:
            if die_comp.kept[0] == 1:
                is_nat_1 = True
            elif die_comp.kept[0] == 20:
                is_nat_20 = True

    return DiceResult(
        expression=expression,
        components=components,
        grand_total=grand_total,
        is_nat_1=is_nat_1,
        is_nat_20=is_nat_20,
    )


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def format_roll(result: DiceResult, *, show_individual: bool = True) -> str:
    """Format a :class:`DiceResult` into a human-readable string.

    Args:
        result: The dice result to format.
        show_individual: If True, show each individual die value.

    Returns:
        A formatted string like ``"2d6+3 → [4, 2]+3 = **9**"``.
    """
    parts: list[str] = []

    for i, (sign, comp) in enumerate(result.components):
        prefix = ""
        if i > 0:
            prefix = " + " if sign == 1 else " - "
        elif sign == -1:
            prefix = "-"

        if isinstance(comp, DieResult):
            if show_individual:
                kept_str = str(comp.kept)
                if comp.rolls != comp.kept:
                    # Show dropped dice struck through
                    all_str = ", ".join(
                        f"~~{r}~~" if r not in comp.kept else str(r) for r in comp.rolls
                    )
                    kept_str = f"[{all_str}]"
                else:
                    kept_str = str(comp.kept)
                parts.append(f"{prefix}{kept_str}")
            else:
                parts.append(f"{prefix}{comp.total}")
        else:
            parts.append(f"{prefix}{comp}")

    breakdown = "".join(parts)

    # Natural 1/20 callouts
    suffix = ""
    if result.is_nat_20:
        suffix = " 🎯 **Natural 20!**"
    elif result.is_nat_1:
        suffix = " 💀 **Natural 1!**"

    return f"{result.expression} → {breakdown} = **{result.grand_total}**{suffix}"


def roll_and_format(expression: str) -> tuple[DiceResult, str]:
    """Convenience: roll and format in one call."""
    result = roll(expression)
    return result, format_roll(result)
