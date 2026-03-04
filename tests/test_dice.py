"""Tests for the dice rolling engine (grug/dice.py)."""

import pytest

from grug.dice import DiceError, DiceResult, DieResult, RollType, format_roll, roll


# ---------------------------------------------------------------------------
# Basic roll parsing
# ---------------------------------------------------------------------------


class TestBasicRolls:
    """Test basic dice expression parsing and rolling."""

    def test_simple_d20(self):
        result = roll("d20")
        assert 1 <= result.grand_total <= 20
        assert result.expression == "d20"
        assert len(result.components) == 1
        _, comp = result.components[0]
        assert isinstance(comp, DieResult)
        assert comp.sides == 20
        assert len(comp.rolls) == 1

    def test_1d20(self):
        result = roll("1d20")
        assert 1 <= result.grand_total <= 20

    def test_2d6(self):
        result = roll("2d6")
        assert 2 <= result.grand_total <= 12
        _, comp = result.components[0]
        assert isinstance(comp, DieResult)
        assert len(comp.rolls) == 2
        assert comp.sides == 6

    def test_d100(self):
        result = roll("d100")
        assert 1 <= result.grand_total <= 100

    def test_d_percent(self):
        result = roll("d%")
        assert 1 <= result.grand_total <= 100
        _, comp = result.components[0]
        assert comp.sides == 100

    def test_all_standard_dice(self):
        for sides in [4, 6, 8, 10, 12, 20, 100]:
            result = roll(f"d{sides}")
            assert 1 <= result.grand_total <= sides
            _, comp = result.components[0]
            assert comp.sides == sides


# ---------------------------------------------------------------------------
# Modifiers
# ---------------------------------------------------------------------------


class TestModifiers:
    """Test dice expressions with modifiers."""

    def test_d20_plus_5(self):
        result = roll("1d20+5")
        assert 6 <= result.grand_total <= 25
        assert len(result.components) == 2

    def test_d20_minus_2(self):
        result = roll("1d20-2")
        assert -1 <= result.grand_total <= 18

    def test_2d6_plus_3(self):
        result = roll("2d6+3")
        assert 5 <= result.grand_total <= 15


# ---------------------------------------------------------------------------
# Keep highest / lowest
# ---------------------------------------------------------------------------


class TestKeepModes:
    """Test kh (keep highest) and kl (keep lowest) modifiers."""

    def test_4d6kh3(self):
        """Standard stat generation: roll 4d6, keep highest 3."""
        result = roll("4d6kh3")
        _, comp = result.components[0]
        assert isinstance(comp, DieResult)
        assert len(comp.rolls) == 4
        assert len(comp.kept) == 3
        assert comp.total == sum(comp.kept)
        # Kept should be the 3 highest
        sorted_desc = sorted(comp.rolls, reverse=True)[:3]
        assert sorted(comp.kept, reverse=True) == sorted_desc

    def test_2d20kh1(self):
        """Advantage: roll 2d20, keep highest 1."""
        result = roll("2d20kh1")
        _, comp = result.components[0]
        assert len(comp.rolls) == 2
        assert len(comp.kept) == 1
        assert comp.kept[0] == max(comp.rolls)

    def test_2d20kl1(self):
        """Disadvantage: roll 2d20, keep lowest 1."""
        result = roll("2d20kl1")
        _, comp = result.components[0]
        assert len(comp.rolls) == 2
        assert len(comp.kept) == 1
        assert comp.kept[0] == min(comp.rolls)


# ---------------------------------------------------------------------------
# Compound expressions
# ---------------------------------------------------------------------------


class TestCompoundExpressions:
    """Test multi-dice expressions."""

    def test_2d6_plus_1d4_plus_3(self):
        result = roll("2d6+1d4+3")
        # 2d6: 2-12, 1d4: 1-4, +3 = 6-19
        assert 6 <= result.grand_total <= 19
        assert len(result.components) == 3

    def test_d20_plus_d6(self):
        result = roll("d20+d6")
        assert 2 <= result.grand_total <= 26
        assert len(result.components) == 2

    def test_d8_minus_d4(self):
        """Subtraction between dice groups."""
        result = roll("d8-d4")
        # d8: 1-8, d4: 1-4 → result: -3 to 7
        assert -3 <= result.grand_total <= 7


# ---------------------------------------------------------------------------
# Natural 1 / 20 detection
# ---------------------------------------------------------------------------


class TestNaturalRolls:
    """Test nat 1 / nat 20 detection."""

    def test_nat_detection_only_for_single_d20(self):
        """Nat 1/20 detection should not trigger for non-d20 or multi-dice."""
        result = roll("2d20")
        assert result.is_nat_1 is False
        assert result.is_nat_20 is False

    def test_nat_detection_not_for_d6(self):
        result = roll("1d6")
        assert result.is_nat_1 is False
        assert result.is_nat_20 is False

    def test_nat_20_possible(self):
        """Run enough rolls to verify nat 20 can be detected (statistical)."""
        found_nat_20 = False
        for _ in range(200):
            result = roll("d20")
            if result.is_nat_20:
                found_nat_20 = True
                assert result.grand_total == 20
                break
        # With 200 rolls, probability of never getting a 20 is (19/20)^200 ≈ 0.003%
        # This is a non-deterministic test but the failure rate is negligible.
        assert found_nat_20

    def test_nat_1_possible(self):
        found_nat_1 = False
        for _ in range(200):
            result = roll("d20")
            if result.is_nat_1:
                found_nat_1 = True
                assert result.grand_total == 1
                break
        assert found_nat_1


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrors:
    """Test error cases."""

    def test_empty_expression(self):
        with pytest.raises(DiceError):
            roll("")

    def test_whitespace_only(self):
        with pytest.raises(DiceError):
            roll("   ")

    def test_invalid_expression(self):
        with pytest.raises(DiceError):
            roll("abc")

    def test_too_many_dice(self):
        with pytest.raises(DiceError, match="100"):
            roll("101d6")

    def test_die_too_large(self):
        with pytest.raises(DiceError, match="1000"):
            roll("d1001")

    def test_keep_count_too_high(self):
        with pytest.raises(DiceError, match="Keep count"):
            roll("2d6kh5")

    def test_keep_count_zero(self):
        with pytest.raises(DiceError, match="Keep count"):
            roll("2d6kh0")


# ---------------------------------------------------------------------------
# Whitespace handling
# ---------------------------------------------------------------------------


class TestWhitespace:
    """Test that whitespace is properly handled."""

    def test_spaces_ignored(self):
        result = roll("2d6 + 3")
        assert 5 <= result.grand_total <= 15

    def test_leading_trailing_spaces(self):
        result = roll("  d20  ")
        assert 1 <= result.grand_total <= 20


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


class TestFormatting:
    """Test format_roll output."""

    def test_basic_format(self):
        result = roll("d20")
        formatted = format_roll(result)
        assert "d20" in formatted
        assert "**" in formatted  # bold total
        assert str(result.grand_total) in formatted

    def test_nat_20_format(self):
        """Craft a result that looks like nat 20 and verify the callout."""
        result = DiceResult(
            expression="d20",
            components=[(1, DieResult("1d20", 20, [20], [20], 20))],
            grand_total=20,
            is_nat_20=True,
        )
        formatted = format_roll(result)
        assert "Natural 20" in formatted
        assert "🎯" in formatted

    def test_nat_1_format(self):
        result = DiceResult(
            expression="d20",
            components=[(1, DieResult("1d20", 20, [1], [1], 1))],
            grand_total=1,
            is_nat_1=True,
        )
        formatted = format_roll(result)
        assert "Natural 1" in formatted
        assert "💀" in formatted


# ---------------------------------------------------------------------------
# RollType enum
# ---------------------------------------------------------------------------


class TestRollType:
    """Test the RollType enum values."""

    def test_all_types_are_strings(self):
        for rt in RollType:
            assert isinstance(rt.value, str)

    def test_expected_types_exist(self):
        expected = {
            "general",
            "attack",
            "damage",
            "saving_throw",
            "ability_check",
            "initiative",
            "death_save",
            "skill_check",
        }
        actual = {rt.value for rt in RollType}
        assert expected == actual


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Test unusual but valid edge cases."""

    def test_d1(self):
        """A d1 always returns 1."""
        result = roll("d1")
        assert result.grand_total == 1

    def test_large_quantity(self):
        """100 dice is the max allowed."""
        result = roll("100d6")
        assert 100 <= result.grand_total <= 600

    def test_case_insensitive(self):
        """dN, DN, Dn all work."""
        result = roll("1D20")
        assert 1 <= result.grand_total <= 20

    def test_kh_case_insensitive(self):
        result = roll("4D6KH3")
        _, comp = result.components[0]
        assert len(comp.kept) == 3

    def test_plain_number_expression(self):
        """Just a number should be valid (constant modifier)."""
        result = roll("5")
        assert result.grand_total == 5

    def test_dice_plus_dice(self):
        """Multiple dice groups added."""
        result = roll("1d6+1d8")
        assert 2 <= result.grand_total <= 14
