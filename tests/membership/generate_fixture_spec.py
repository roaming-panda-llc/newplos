"""Tests for pure functions in scripts/generate_fixture.py.

These tests do NOT require Django -- all functions under test are pure Python.
"""

from __future__ import annotations

import importlib.util
import sys
from decimal import Decimal
from pathlib import Path

# ---------------------------------------------------------------------------
# Load generate_fixture module from scripts/ without requiring __init__.py
# ---------------------------------------------------------------------------

_script_path = Path(__file__).resolve().parent.parent.parent / "scripts" / "generate_fixture.py"
_spec = importlib.util.spec_from_file_location("generate_fixture", _script_path)
assert _spec is not None and _spec.loader is not None
_module = importlib.util.module_from_spec(_spec)
sys.modules["generate_fixture"] = _module
_spec.loader.exec_module(_module)

extract_space_id = _module.extract_space_id
classify_space_type = _module.classify_space_type
parse_currency = _module.parse_currency
parse_sqft = _module.parse_sqft
parse_dimensions = _module.parse_dimensions
parse_rate_per_sqft = _module.parse_rate_per_sqft
clean_member_name = _module.clean_member_name
decimal_to_str = _module.decimal_to_str

# ---------------------------------------------------------------------------
# extract_space_id - studios
# ---------------------------------------------------------------------------


def describe_extract_space_id_studios():
    """Extract space IDs from studio-style codes."""

    def it_extracts_simple_studio():
        assert extract_space_id("A1 Studio") == "A1"

    def it_extracts_studio_with_letter_suffix():
        assert extract_space_id("A14a Large Studio") == "A14a"

    def it_extracts_building_b_studio():
        assert extract_space_id("B3 Studio") == "B3"

    def it_extracts_building_c_studio():
        assert extract_space_id("C10 Studio") == "C10"

    def it_extracts_multidigit_space():
        assert extract_space_id("A51 Workshop") == "A51"

    def it_extracts_e_building():
        assert extract_space_id("E1 Corner Space") == "E1"


# ---------------------------------------------------------------------------
# extract_space_id - storage and parking
# ---------------------------------------------------------------------------


def describe_extract_space_id_storage_and_parking():
    """Extract space IDs from storage, wood storage, and parking codes."""

    def it_extracts_storage_space_basic():
        assert extract_space_id("S1 Storage - Space 5") == "S1-5"

    def it_extracts_storage_space_single_digit():
        assert extract_space_id("S1 Storage - Space 1") == "S1-1"

    def it_extracts_storage_space_double_digit_unit():
        assert extract_space_id("S2 Storage - Space 12") == "S2-12"

    def it_extracts_wood_storage():
        assert extract_space_id("W3 - Wood Storage") == "W3"

    def it_extracts_wood_storage_other_number():
        assert extract_space_id("W1 - Wood Storage") == "W1"

    def it_extracts_parking_space_default():
        assert extract_space_id("Parking Space") == "P1"

    def it_extracts_parking_space_numbered():
        assert extract_space_id("Parking Space #2") == "P2"

    def it_extracts_parking_space_higher_number():
        assert extract_space_id("Parking Space #5") == "P5"


# ---------------------------------------------------------------------------
# extract_space_id - special cases and fallback
# ---------------------------------------------------------------------------


def describe_extract_space_id_special_cases():
    """Extract space IDs for mezzanine, C30, whitespace, and fallback."""

    def it_extracts_mezzanine():
        assert extract_space_id("Mezzanine") == "Mezzanine"

    def it_extracts_mezzanine_case_insensitive():
        assert extract_space_id("mezzanine") == "Mezzanine"

    def it_extracts_mezzanine_with_suffix():
        assert extract_space_id("Mezzanine Level 2") == "Mezzanine"

    def it_extracts_c30_with_sub_units():
        assert extract_space_id("C30 (a,b,c,d)") == "C30"

    def it_strips_leading_whitespace():
        assert extract_space_id("  A1 Studio") == "A1"

    def it_strips_trailing_whitespace():
        assert extract_space_id("A1 Studio  ") == "A1"

    def it_falls_back_to_truncated_code_for_unrecognized():
        assert extract_space_id("some weird name") == "some weird name"

    def it_truncates_long_fallback_to_20_chars():
        long_code = "X" * 30
        assert extract_space_id(long_code) == "X" * 20


# ---------------------------------------------------------------------------
# classify_space_type
# ---------------------------------------------------------------------------


def describe_classify_space_type():
    """Determine space type from the space code and space ID."""

    def it_classifies_studio():
        assert classify_space_type("A1 Studio", "A1") == "studio"

    def it_classifies_studio_for_b_building():
        assert classify_space_type("B3 Studio", "B3") == "studio"

    def it_classifies_studio_for_c_building():
        assert classify_space_type("C10 Studio", "C10") == "studio"

    def it_classifies_storage_by_s_prefix():
        assert classify_space_type("S1 Storage - Space 5", "S1-5") == "storage"

    def it_classifies_storage_by_w_prefix():
        assert classify_space_type("W3 - Wood Storage", "W3") == "storage"

    def it_classifies_parking():
        assert classify_space_type("Parking Space", "P1") == "parking"

    def it_classifies_parking_numbered():
        assert classify_space_type("Parking Space #2", "P2") == "parking"

    def it_classifies_mezzanine_as_other():
        assert classify_space_type("Mezzanine", "Mezzanine") == "other"

    def it_classifies_unknown_as_studio():
        assert classify_space_type("E1 Corner Space", "E1") == "studio"


# ---------------------------------------------------------------------------
# parse_currency - valid amounts
# ---------------------------------------------------------------------------


def describe_parse_currency_valid_amounts():
    """Parse valid currency strings into Decimal values."""

    def it_parses_simple_dollar_amount():
        assert parse_currency("$255.00") == Decimal("255.00")

    def it_parses_amount_with_comma():
        assert parse_currency("$2,175.00") == Decimal("2175.00")

    def it_parses_zero():
        assert parse_currency("$0.00") == Decimal("0.00")

    def it_parses_amount_without_dollar_sign():
        assert parse_currency("100.50") == Decimal("100.50")

    def it_strips_whitespace():
        assert parse_currency("  $500.00  ") == Decimal("500.00")

    def it_parses_large_amounts():
        assert parse_currency("$10,000.00") == Decimal("10000.00")

    def it_parses_negative_amount():
        assert parse_currency("-$50.00") == Decimal("-50.00")

    def it_parses_amount_with_multiple_commas():
        assert parse_currency("$1,000,000.00") == Decimal("1000000.00")


# ---------------------------------------------------------------------------
# parse_currency - none cases
# ---------------------------------------------------------------------------


def describe_parse_currency_none_cases():
    """Return None for unparseable currency strings."""

    def it_returns_none_for_empty_string():
        assert parse_currency("") is None

    def it_returns_none_for_whitespace_only():
        assert parse_currency("   ") is None

    def it_returns_none_for_non_numeric():
        assert parse_currency("N/A") is None

    def it_returns_none_for_just_dollar_sign():
        assert parse_currency("$") is None


# ---------------------------------------------------------------------------
# parse_sqft
# ---------------------------------------------------------------------------


def describe_parse_sqft_valid_values():
    """Parse valid square footage values."""

    def it_parses_plain_integer():
        assert parse_sqft("68") == Decimal("68")

    def it_parses_asterisk_prefixed():
        assert parse_sqft("*83") == Decimal("83")

    def it_parses_tilde_prefixed():
        assert parse_sqft("~30.815") == Decimal("30.815")

    def it_parses_value_with_text_annotation():
        assert parse_sqft("55 (with 5sf for pipe subtracted)") == Decimal("55")

    def it_parses_decimal_value():
        assert parse_sqft("123.45") == Decimal("123.45")

    def it_strips_whitespace():
        assert parse_sqft("  100  ") == Decimal("100")

    def it_handles_asterisk_and_tilde_combined():
        assert parse_sqft("*~50") == Decimal("50")


def describe_parse_sqft_none_cases():
    """Return None for unparseable square footage values."""

    def it_returns_none_for_see_notes():
        assert parse_sqft("See Notes") is None

    def it_returns_none_for_empty_string():
        assert parse_sqft("") is None

    def it_returns_none_for_whitespace_only():
        assert parse_sqft("   ") is None

    def it_returns_none_for_non_numeric_text():
        assert parse_sqft("varies") is None


# ---------------------------------------------------------------------------
# parse_dimensions
# ---------------------------------------------------------------------------


def describe_parse_dimensions_valid():
    """Parse valid dimension strings into (width, depth) tuples."""

    def it_parses_standard_dimensions():
        assert parse_dimensions("8.5 x 8") == (Decimal("8.5"), Decimal("8"))

    def it_parses_no_spaces_around_x():
        assert parse_dimensions("8x8") == (Decimal("8"), Decimal("8"))

    def it_parses_uppercase_x():
        assert parse_dimensions("10 X 12") == (Decimal("10"), Decimal("12"))

    def it_parses_decimal_dimensions():
        assert parse_dimensions("12.5 x 15.3") == (Decimal("12.5"), Decimal("15.3"))

    def it_strips_leading_whitespace():
        assert parse_dimensions("  8 x 10  ") == (Decimal("8"), Decimal("10"))

    def it_strips_asterisk_prefix():
        assert parse_dimensions("*8 x 10") == (Decimal("8"), Decimal("10"))

    def it_strips_tilde_prefix():
        assert parse_dimensions("~8 x 10") == (Decimal("8"), Decimal("10"))


def describe_parse_dimensions_none_pair():
    """Return (None, None) for unparseable dimension strings."""

    def it_returns_none_pair_for_see_notes():
        assert parse_dimensions("See Notes") == (None, None)

    def it_returns_none_pair_for_bare_x():
        assert parse_dimensions("X") == (None, None)

    def it_returns_none_pair_for_empty_string():
        assert parse_dimensions("") == (None, None)

    def it_returns_none_pair_for_whitespace():
        assert parse_dimensions("   ") == (None, None)

    def it_returns_none_pair_for_single_number():
        assert parse_dimensions("8") == (None, None)

    def it_returns_none_pair_for_no_match():
        assert parse_dimensions("irregular shape") == (None, None)


# ---------------------------------------------------------------------------
# parse_rate_per_sqft
# ---------------------------------------------------------------------------


def describe_parse_rate_per_sqft():
    """Parse rate per square foot values."""

    def it_parses_decimal_rate():
        assert parse_rate_per_sqft("3.75") == Decimal("3.75")

    def it_parses_integer_rate():
        assert parse_rate_per_sqft("4") == Decimal("4")

    def it_returns_none_for_empty_string():
        assert parse_rate_per_sqft("") is None

    def it_returns_none_for_whitespace():
        assert parse_rate_per_sqft("   ") is None

    def it_returns_none_for_non_numeric():
        assert parse_rate_per_sqft("varies") is None

    def it_strips_whitespace():
        assert parse_rate_per_sqft("  3.50  ") == Decimal("3.50")

    def it_parses_zero():
        assert parse_rate_per_sqft("0") == Decimal("0")


# ---------------------------------------------------------------------------
# clean_member_name - suffix stripping
# ---------------------------------------------------------------------------


def describe_clean_member_name_suffix_stripping():
    """Strip Airtable numeric suffixes and trailing dashes from member names."""

    def it_strips_numeric_suffix():
        assert clean_member_name("Kate Reed - 78") == "Kate Reed"

    def it_strips_trailing_dash():
        assert clean_member_name("Kevin Parnow -") == "Kevin Parnow"

    def it_strips_longer_numeric_suffix():
        assert clean_member_name("Alexis Sterry - 345") == "Alexis Sterry"

    def it_strips_both_whitespace_and_suffix():
        assert clean_member_name("  Kate Reed - 78  ") == "Kate Reed"

    def it_preserves_hyphenated_names():
        assert clean_member_name("Mary-Jane Watson") == "Mary-Jane Watson"

    def it_preserves_name_with_internal_numbers():
        assert clean_member_name("Agent 47") == "Agent 47"


# ---------------------------------------------------------------------------
# clean_member_name - aliases and whitespace
# ---------------------------------------------------------------------------


def describe_clean_member_name_aliases_and_whitespace():
    """Apply name aliases and handle whitespace in member names."""

    def it_applies_ochen_alias():
        assert clean_member_name("Ochen") == "Ochen Kaylan"

    def it_applies_hane_alias():
        assert clean_member_name("Ha'Ne") == "Ha'ne"

    def it_returns_simple_name_unchanged():
        assert clean_member_name("John Smith") == "John Smith"

    def it_strips_leading_whitespace():
        assert clean_member_name("  Jane Doe") == "Jane Doe"

    def it_strips_trailing_whitespace():
        assert clean_member_name("Jane Doe  ") == "Jane Doe"


# ---------------------------------------------------------------------------
# decimal_to_str
# ---------------------------------------------------------------------------


def describe_decimal_to_str():
    """Convert Decimal values to string for JSON output."""

    def it_converts_decimal_to_string():
        assert decimal_to_str(Decimal("255.00")) == "255.00"

    def it_returns_none_for_none():
        assert decimal_to_str(None) is None

    def it_converts_zero():
        assert decimal_to_str(Decimal("0.00")) == "0.00"

    def it_converts_large_value():
        assert decimal_to_str(Decimal("10000.50")) == "10000.50"

    def it_preserves_decimal_precision():
        assert decimal_to_str(Decimal("3.14159")) == "3.14159"

    def it_converts_integer_decimal():
        assert decimal_to_str(Decimal("100")) == "100"
