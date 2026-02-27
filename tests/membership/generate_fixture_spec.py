"""Tests for pure functions in scripts/generate_fixture.py.

These tests do NOT require Django -- all functions under test are pure Python.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import textwrap
from decimal import Decimal
from pathlib import Path
from unittest import mock

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

# Additional imports for the newly-tested functions
FixtureAccumulator = _module.FixtureAccumulator
ParsedRow = _module.ParsedRow
_make_space_obj = _module._make_space_obj
_handle_non_tenant_row = _module._handle_non_tenant_row
_handle_guild_row = _module._handle_guild_row
_handle_tenant_row = _module._handle_tenant_row
_make_lease = _module._make_lease
_build_fixture_json = _module._build_fixture_json
_print_report = _module._print_report
read_csv_rows = _module.read_csv_rows
parse_row = _module.parse_row
generate_fixture = _module.generate_fixture
GUILD_SPACE_MAP = _module.GUILD_SPACE_MAP
PLM_SUB_UNITS = _module.PLM_SUB_UNITS
FACILITY_SPACES = _module.FACILITY_SPACES
BATTERY_STORAGE_SPACE_ID = _module.BATTERY_STORAGE_SPACE_ID
LEASE_OVERRIDES = _module.LEASE_OVERRIDES
CREATED_AT = _module.CREATED_AT
STANDARD_PLAN_PK = _module.STANDARD_PLAN_PK
STANDARD_PLAN_PRICE = _module.STANDARD_PLAN_PRICE

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


# ---------------------------------------------------------------------------
# Helper: build a minimal ParsedRow for testing
# ---------------------------------------------------------------------------


def _row(
    space_code="A1 Studio",
    label="",
    member_raw="",
    full_price=None,
    open_val=None,
    actual_paid=None,
    notes="",
    space_id=None,
    space_type="studio",
    sqft=None,
    width=None,
    depth=None,
    rate=None,
    deposit=None,
):
    """Convenience factory for ParsedRow test instances."""
    if space_id is None:
        space_id = extract_space_id(space_code)
    return ParsedRow(
        space_code=space_code,
        label=label,
        member_raw=member_raw,
        full_price=full_price,
        open_val=open_val,
        actual_paid=actual_paid,
        notes=notes,
        space_id=space_id,
        space_type=space_type,
        sqft=sqft,
        width=width,
        depth=depth,
        rate=rate,
        deposit=deposit,
    )


# ---------------------------------------------------------------------------
# extract_space_id - fallback regex (line 217)
# ---------------------------------------------------------------------------


def describe_extract_space_id_fallback_regex():
    """Cover the secondary alphanumeric fallback regex on line 215-217."""

    def it_matches_multi_letter_prefix_with_digits():
        # "AB12" does not start with a single [A-Z] then digits -- the first
        # regex on line 210 expects exactly one uppercase letter. But the
        # fallback on line 215 matches [A-Z]+\d+[a-z]? which captures "AB12".
        assert extract_space_id("AB12 something") == "AB12"

    def it_matches_multi_letter_prefix_with_digits_and_suffix():
        assert extract_space_id("XY99a units") == "XY99a"


# ---------------------------------------------------------------------------
# parse_sqft - InvalidOperation path (lines 256-257)
# ---------------------------------------------------------------------------


def describe_parse_sqft_invalid_operation():
    """Cover the InvalidOperation exception path in parse_sqft."""

    def it_returns_none_for_malformed_decimal_after_regex_match():
        # The regex r"([\d.]+)" can match "1.2.3" (it grabs "1.2.3"),
        # which then fails Decimal("1.2.3") -> InvalidOperation
        assert parse_sqft("1.2.3") is None


# ---------------------------------------------------------------------------
# parse_dimensions - InvalidOperation path (lines 272-273)
# ---------------------------------------------------------------------------


def describe_parse_dimensions_invalid_operation():
    """Cover the InvalidOperation exception path in parse_dimensions."""

    def it_returns_none_pair_for_malformed_decimal_in_dimensions():
        # "1.2.3 x 4.5.6" - regex matches but Decimal conversion fails
        assert parse_dimensions("1.2.3 x 4.5.6") == (None, None)


# ---------------------------------------------------------------------------
# FixtureAccumulator
# ---------------------------------------------------------------------------


def describe_fixture_accumulator():
    """Test FixtureAccumulator methods: get_or_create_guild, get_or_create_member, next_lease_pk."""

    def describe_get_or_create_guild():
        def it_creates_a_new_guild_with_incrementing_pk():
            acc = FixtureAccumulator()
            pk = acc.get_or_create_guild("Glass Guild")
            assert pk == 1
            assert acc.guilds == {"Glass Guild": 1}

        def it_returns_existing_guild_pk_on_second_call():
            acc = FixtureAccumulator()
            pk1 = acc.get_or_create_guild("Glass Guild")
            pk2 = acc.get_or_create_guild("Glass Guild")
            assert pk1 == pk2 == 1
            assert len(acc.guilds) == 1

        def it_assigns_incrementing_pks_to_different_guilds():
            acc = FixtureAccumulator()
            pk1 = acc.get_or_create_guild("Glass Guild")
            pk2 = acc.get_or_create_guild("Ceramics Guild")
            assert pk1 == 1
            assert pk2 == 2

    def describe_get_or_create_member():
        def it_creates_a_new_member_with_incrementing_pk():
            acc = FixtureAccumulator()
            pk = acc.get_or_create_member("Jane Doe")
            assert pk == 1
            assert acc.members == {"Jane Doe": 1}

        def it_returns_existing_member_pk_on_second_call():
            acc = FixtureAccumulator()
            pk1 = acc.get_or_create_member("Jane Doe")
            pk2 = acc.get_or_create_member("Jane Doe")
            assert pk1 == pk2 == 1

        def it_cleans_name_before_storing():
            acc = FixtureAccumulator()
            pk = acc.get_or_create_member("Kate Reed - 78")
            assert "Kate Reed" in acc.members
            assert pk == 1

        def it_sets_preferred_name_for_ochen():
            acc = FixtureAccumulator()
            acc.get_or_create_member("Ochen")
            assert acc.member_preferred["Ochen Kaylan"] == "Ochen"

        def it_does_not_set_preferred_name_for_other_members():
            acc = FixtureAccumulator()
            acc.get_or_create_member("Jane Doe")
            assert "Jane Doe" not in acc.member_preferred

    def describe_next_lease_pk():
        def it_increments_with_each_call():
            acc = FixtureAccumulator()
            assert acc.next_lease_pk() == 1
            assert acc.next_lease_pk() == 2
            assert acc.next_lease_pk() == 3


# ---------------------------------------------------------------------------
# _make_space_obj (lines 314-328)
# ---------------------------------------------------------------------------


def describe_make_space_obj():
    """Test _make_space_obj builds correct dict from ParsedRow."""

    def it_builds_space_dict_with_all_fields():
        row = _row(
            space_code="A1 Studio",
            sqft=Decimal("100"),
            width=Decimal("10"),
            depth=Decimal("10"),
            rate=Decimal("3.75"),
            notes="test note",
        )
        result = _make_space_obj(row, is_rentable=True, status="occupied", notes="custom note")
        assert result["space_id"] == "A1"
        assert result["name"] == "A1 Studio"
        assert result["space_type"] == "studio"
        assert result["size_sqft"] == "100"
        assert result["width"] == "10"
        assert result["depth"] == "10"
        assert result["rate_per_sqft"] == "3.75"
        assert result["is_rentable"] is True
        assert result["manual_price"] is None
        assert result["status"] == "occupied"
        assert result["notes"] == "custom note"
        assert result["sublet_guild"] is None

    def it_includes_manual_price_when_provided():
        row = _row()
        result = _make_space_obj(
            row, is_rentable=True, status="available", notes="", manual_price=Decimal("500.00")
        )
        assert result["manual_price"] == "500.00"

    def it_includes_guild_name_as_list_when_provided():
        row = _row()
        result = _make_space_obj(
            row, is_rentable=True, status="occupied", notes="", guild_name="Glass Guild"
        )
        assert result["sublet_guild"] == ["Glass Guild"]

    def it_sets_sublet_guild_to_none_when_no_guild():
        row = _row()
        result = _make_space_obj(row, is_rentable=True, status="occupied", notes="")
        assert result["sublet_guild"] is None

    def it_handles_none_dimensions():
        row = _row(sqft=None, width=None, depth=None, rate=None)
        result = _make_space_obj(row, is_rentable=False, status="maintenance", notes="")
        assert result["size_sqft"] is None
        assert result["width"] is None
        assert result["depth"] is None
        assert result["rate_per_sqft"] is None


# ---------------------------------------------------------------------------
# _make_lease (line 609)
# ---------------------------------------------------------------------------


def describe_make_lease():
    """Test _make_lease builds correct lease dict."""

    def it_builds_basic_lease_dict():
        result = _make_lease(
            1,
            content_type=["membership", "member"],
            object_id=5,
            space_id="A1",
            base_price=Decimal("300.00"),
            monthly_rent=Decimal("250.00"),
            deposit=Decimal("200.00"),
            notes="test note",
        )
        assert result["pk"] == 1
        assert result["content_type"] == ["membership", "member"]
        assert result["object_id"] == 5
        assert result["space"] == "A1"
        assert result["lease_type"] == "month_to_month"
        assert result["base_price"] == "300.00"
        assert result["monthly_rent"] == "250.00"
        assert result["start_date"] == "2025-01-01"
        assert result["end_date"] is None
        assert result["committed_until"] is None
        assert result["deposit_required"] == "200.00"
        assert result["deposit_paid_date"] is None
        assert result["deposit_paid_amount"] == "200.00"
        assert result["discount_reason"] == ""
        assert result["is_split"] is False
        assert result["prepaid_through"] is None
        assert result["notes"] == "test note"

    def it_accepts_optional_lease_type_and_discount():
        result = _make_lease(
            2,
            content_type=["membership", "member"],
            object_id=1,
            space_id="B1",
            base_price=Decimal("400.00"),
            monthly_rent=Decimal("360.00"),
            deposit=None,
            notes="",
            lease_type="annual",
            discount_reason="10% annual discount",
            is_split=True,
            prepaid_through="2026-07-01",
        )
        assert result["lease_type"] == "annual"
        assert result["discount_reason"] == "10% annual discount"
        assert result["is_split"] is True
        assert result["prepaid_through"] == "2026-07-01"
        assert result["deposit_required"] is None
        assert result["deposit_paid_amount"] is None


# ---------------------------------------------------------------------------
# read_csv_rows (lines 342-378)
# ---------------------------------------------------------------------------


def describe_read_csv_rows():
    """Test CSV reading with multiline handling and row filtering."""

    def it_reads_valid_rows_from_csv():
        csv_content = textwrap.dedent("""\
            Space Code,Label,Member,Full Price,Open,Actual Amount Paid,Dollar Loss,Dimensions,Sq Ft,Deviation,Earn Money,Paid Deposit,Notes,Accurate Complete,Rate Per Sq Ft
            A1 Studio,Occupied,Jane Doe,$255.00,,$255.00,,8 x 10,80,,,,test note,,3.19
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(csv_content)
            f.flush()
            try:
                rows = read_csv_rows(f.name)
                assert len(rows) == 1
                assert rows[0]["space_code"] == "A1 Studio"
                assert rows[0]["member"] == "Jane Doe"
                assert rows[0]["full_price"] == "$255.00"
            finally:
                os.unlink(f.name)

    def it_skips_rows_with_empty_space_code():
        csv_content = textwrap.dedent("""\
            Space Code,Label,Member,Full Price,Open,Actual Amount Paid,Dollar Loss,Dimensions,Sq Ft,Deviation,Earn Money,Paid Deposit,Notes,Accurate Complete,Rate Per Sq Ft
            A1 Studio,Occupied,Jane Doe,$255.00,,$255.00,,8 x 10,80,,,,,,3.19
            ,,,,,,,,,,,,,,,
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(csv_content)
            f.flush()
            try:
                rows = read_csv_rows(f.name)
                assert len(rows) == 1
            finally:
                os.unlink(f.name)

    def it_skips_rows_with_numeric_only_space_code():
        csv_content = textwrap.dedent("""\
            Space Code,Label,Member,Full Price,Open,Actual Amount Paid,Dollar Loss,Dimensions,Sq Ft,Deviation,Earn Money,Paid Deposit,Notes,Accurate Complete,Rate Per Sq Ft
            A1 Studio,Occupied,Jane Doe,$255.00,,$255.00,,8 x 10,80,,,,,,3.19
            42.5,,,,,,,,,,,,,,,
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(csv_content)
            f.flush()
            try:
                rows = read_csv_rows(f.name)
                assert len(rows) == 1
            finally:
                os.unlink(f.name)

    def it_pads_short_rows():
        csv_content = textwrap.dedent("""\
            Space Code,Label,Member,Full Price,Open,Actual Amount Paid,Dollar Loss,Dimensions,Sq Ft,Deviation,Earn Money,Paid Deposit,Notes,Accurate Complete,Rate Per Sq Ft
            A1 Studio,Occupied,Jane Doe
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(csv_content)
            f.flush()
            try:
                rows = read_csv_rows(f.name)
                assert len(rows) == 1
                assert rows[0]["full_price"] == ""
                assert rows[0]["notes"] == ""
            finally:
                os.unlink(f.name)


# ---------------------------------------------------------------------------
# parse_row (lines 383-388)
# ---------------------------------------------------------------------------


def describe_parse_row():
    """Test parse_row converts a dict row into a ParsedRow."""

    def it_parses_a_complete_row():
        raw = {
            "space_code": "A1 Studio",
            "label": "Occupied",
            "member": "Jane Doe - 42",
            "full_price": "$255.00",
            "open": "",
            "actual_amount_paid": "$255.00",
            "dollar_loss": "",
            "dimensions": "8 x 10",
            "sqft": "80",
            "deviation": "",
            "earn_money": "",
            "paid_deposit": "$200.00",
            "notes": "some note",
            "accurate_complete": "",
            "rate_per_sqft": "3.19",
        }
        result = parse_row(raw)
        assert result.space_code == "A1 Studio"
        assert result.space_id == "A1"
        assert result.space_type == "studio"
        assert result.label == "Occupied"
        assert result.member_raw == "Jane Doe - 42"
        assert result.full_price == Decimal("255.00")
        assert result.open_val is None
        assert result.actual_paid == Decimal("255.00")
        assert result.notes == "some note"
        assert result.sqft == Decimal("80")
        assert result.width == Decimal("8")
        assert result.depth == Decimal("10")
        assert result.rate == Decimal("3.19")
        assert result.deposit == Decimal("200.00")

    def it_handles_empty_fields():
        raw = {
            "space_code": "S1 Storage - Space 1",
            "label": "",
            "member": "",
            "full_price": "",
            "open": "",
            "actual_amount_paid": "",
            "dollar_loss": "",
            "dimensions": "",
            "sqft": "",
            "deviation": "",
            "earn_money": "",
            "paid_deposit": "",
            "notes": "",
            "accurate_complete": "",
            "rate_per_sqft": "",
        }
        result = parse_row(raw)
        assert result.space_id == "S1-1"
        assert result.space_type == "storage"
        assert result.full_price is None
        assert result.width is None
        assert result.depth is None
        assert result.sqft is None
        assert result.rate is None
        assert result.deposit is None


# ---------------------------------------------------------------------------
# _handle_non_tenant_row (lines 417-501)
# ---------------------------------------------------------------------------


def describe_handle_non_tenant_row():
    """Test all branches in _handle_non_tenant_row."""

    def it_handles_plm_shelf_row():
        row = _row(member_raw="PLM Shelf", space_id="A99", notes="shelf stuff")
        acc = FixtureAccumulator()
        result = _handle_non_tenant_row(row, acc)
        assert result is True
        assert len(acc.spaces) == 1
        assert acc.spaces[0]["status"] == "maintenance"
        assert acc.spaces[0]["is_rentable"] is False
        assert "PLM shelf" in acc.spaces[0]["notes"]

    def it_handles_battery_storage_by_space_id():
        row = _row(space_id=BATTERY_STORAGE_SPACE_ID, notes="lithium batteries")
        acc = FixtureAccumulator()
        result = _handle_non_tenant_row(row, acc)
        assert result is True
        assert len(acc.spaces) == 1
        assert acc.spaces[0]["status"] == "maintenance"
        assert "Battery storage" in acc.spaces[0]["notes"]

    def it_handles_facility_space_with_notes():
        facility_id = next(iter(FACILITY_SPACES))
        row = _row(space_id=facility_id, label="Workshop Area", notes="shared space", full_price=Decimal("100.00"))
        acc = FixtureAccumulator()
        result = _handle_non_tenant_row(row, acc)
        assert result is True
        assert len(acc.spaces) == 1
        assert acc.spaces[0]["status"] == "maintenance"
        assert acc.spaces[0]["is_rentable"] is False
        assert "Workshop Area" in acc.spaces[0]["notes"]
        assert acc.spaces[0]["manual_price"] == "100.00"

    def it_handles_facility_space_without_notes():
        facility_id = next(iter(FACILITY_SPACES))
        row = _row(space_id=facility_id, label="Storage Room", notes="")
        acc = FixtureAccumulator()
        result = _handle_non_tenant_row(row, acc)
        assert result is True
        assert acc.spaces[0]["notes"] == "Storage Room"

    def it_handles_plm_sub_units():
        sub_unit = next(iter(PLM_SUB_UNITS))
        row = _row(space_id=sub_unit, notes="glass area")
        acc = FixtureAccumulator()
        result = _handle_non_tenant_row(row, acc)
        assert result is True
        assert acc.spaces[0]["status"] == "occupied"
        assert "Sub-unit of A2b" in acc.spaces[0]["notes"]

    def it_handles_vacant_open_x_row():
        row = _row(label="Open", member_raw="X", full_price=Decimal("300.00"), open_val=Decimal("150.00"), notes="corner unit")
        acc = FixtureAccumulator()
        result = _handle_non_tenant_row(row, acc)
        assert result is True
        assert acc.spaces[0]["status"] == "available"
        assert acc.spaces[0]["is_rentable"] is True
        assert "$150" in acc.spaces[0]["notes"]
        assert "corner unit" in acc.spaces[0]["notes"]
        assert acc.spaces[0]["manual_price"] == "300.00"

    def it_handles_vacant_open_x_row_without_open_val():
        row = _row(label="Open", member_raw="X", full_price=Decimal("300.00"), open_val=None, notes="")
        acc = FixtureAccumulator()
        result = _handle_non_tenant_row(row, acc)
        assert result is True
        assert acc.spaces[0]["status"] == "available"
        assert acc.spaces[0]["notes"] == ""

    def it_handles_open_storage_member():
        row = _row(member_raw="Open", full_price=Decimal("50.00"), open_val=Decimal("25.00"), notes="")
        acc = FixtureAccumulator()
        result = _handle_non_tenant_row(row, acc)
        assert result is True
        assert acc.spaces[0]["status"] == "available"
        assert "$25" in acc.spaces[0]["notes"]

    def it_handles_open_storage_member_without_open_val():
        row = _row(member_raw="Open", full_price=Decimal("50.00"), open_val=None, notes="end unit")
        acc = FixtureAccumulator()
        result = _handle_non_tenant_row(row, acc)
        assert result is True
        assert acc.spaces[0]["notes"] == "end unit"

    def it_handles_unclassified_plm_row():
        # PLM member but space_id NOT in GUILD_SPACE_MAP
        row = _row(space_id="Z99", member_raw="PLM", label="Electrical Panel", notes="high voltage", full_price=Decimal("0.00"))
        acc = FixtureAccumulator()
        result = _handle_non_tenant_row(row, acc)
        assert result is True
        assert len(acc.warnings) == 1
        assert "Unclassified PLM" in acc.warnings[0]
        assert acc.spaces[0]["status"] == "maintenance"

    def it_handles_unclassified_plm_row_without_notes():
        row = _row(space_id="Z99", member_raw="PLM", label="Electrical Panel", notes="")
        acc = FixtureAccumulator()
        _handle_non_tenant_row(row, acc)
        assert acc.spaces[0]["notes"] == "Electrical Panel"

    def it_handles_battery_storage_by_member_name():
        row = _row(member_raw="Battery storage", space_id="X99", notes="extra batteries")
        acc = FixtureAccumulator()
        result = _handle_non_tenant_row(row, acc)
        assert result is True
        assert acc.spaces[0]["status"] == "maintenance"
        assert "Battery storage" in acc.spaces[0]["notes"]

    def it_returns_false_for_normal_tenant_row():
        row = _row(member_raw="Jane Doe", label="Occupied")
        acc = FixtureAccumulator()
        result = _handle_non_tenant_row(row, acc)
        assert result is False
        assert len(acc.spaces) == 0


# ---------------------------------------------------------------------------
# _handle_guild_row (lines 506-539)
# ---------------------------------------------------------------------------


def describe_handle_guild_row():
    """Test _handle_guild_row for guild space processing."""

    def it_returns_false_for_non_guild_space():
        row = _row(space_id="Z99", member_raw="PLM")
        acc = FixtureAccumulator()
        result = _handle_guild_row(row, acc)
        assert result is False

    def it_creates_space_and_lease_for_guild_with_actual_paid():
        guild_space_id = next(iter(GUILD_SPACE_MAP))
        guild_name = GUILD_SPACE_MAP[guild_space_id]
        row = _row(
            space_id=guild_space_id,
            space_code=f"{guild_space_id} Workshop",
            full_price=Decimal("500.00"),
            actual_paid=Decimal("450.00"),
            deposit=Decimal("100.00"),
            notes="guild space note",
        )
        acc = FixtureAccumulator()
        result = _handle_guild_row(row, acc)
        assert result is True
        assert len(acc.spaces) == 1
        assert acc.spaces[0]["status"] == "occupied"
        assert acc.spaces[0]["sublet_guild"] == [guild_name]
        assert acc.spaces[0]["manual_price"] == "500.00"
        assert len(acc.leases) == 1
        lease = acc.leases[0]
        assert lease["content_type"] == ["membership", "guild"]
        assert lease["base_price"] == "500.00"
        assert lease["monthly_rent"] == "450.00"
        assert lease["deposit_required"] == "100.00"

    def it_creates_space_without_lease_when_no_prices():
        guild_space_id = next(iter(GUILD_SPACE_MAP))
        row = _row(
            space_id=guild_space_id,
            full_price=None,
            actual_paid=None,
            notes="",
        )
        acc = FixtureAccumulator()
        result = _handle_guild_row(row, acc)
        assert result is True
        assert len(acc.spaces) == 1
        assert len(acc.leases) == 0

    def it_uses_full_price_as_base_when_actual_paid_is_none():
        guild_space_id = next(iter(GUILD_SPACE_MAP))
        row = _row(
            space_id=guild_space_id,
            full_price=Decimal("500.00"),
            actual_paid=None,
            notes="",
        )
        acc = FixtureAccumulator()
        _handle_guild_row(row, acc)
        assert len(acc.leases) == 1
        assert acc.leases[0]["base_price"] == "500.00"
        assert acc.leases[0]["monthly_rent"] == "0.00"

    def it_uses_zero_base_when_full_price_is_none_but_actual_paid_exists():
        guild_space_id = next(iter(GUILD_SPACE_MAP))
        row = _row(
            space_id=guild_space_id,
            full_price=None,
            actual_paid=Decimal("200.00"),
            notes="",
        )
        acc = FixtureAccumulator()
        _handle_guild_row(row, acc)
        assert len(acc.leases) == 1
        assert acc.leases[0]["base_price"] == "0.00"
        assert acc.leases[0]["monthly_rent"] == "200.00"

    def it_reuses_guild_pk_for_same_guild():
        # Find two spaces that belong to the same guild
        guild_spaces = list(GUILD_SPACE_MAP.items())
        guild_name_counts: dict[str, list[str]] = {}
        for sid, gn in guild_spaces:
            guild_name_counts.setdefault(gn, []).append(sid)
        # Find a guild with at least 2 spaces
        multi_spaces = [(gn, sids) for gn, sids in guild_name_counts.items() if len(sids) >= 2]
        if multi_spaces:
            guild_name, space_ids = multi_spaces[0]
            acc = FixtureAccumulator()
            for sid in space_ids[:2]:
                row = _row(space_id=sid, full_price=Decimal("100.00"), actual_paid=Decimal("100.00"), notes="")
                _handle_guild_row(row, acc)
            # Both leases reference the same guild PK
            assert acc.leases[0]["object_id"] == acc.leases[1]["object_id"]
            assert len(acc.guilds) == 1


# ---------------------------------------------------------------------------
# _handle_tenant_row (lines 544-575)
# ---------------------------------------------------------------------------


def describe_handle_tenant_row():
    """Test _handle_tenant_row for occupied tenant spaces."""

    def it_creates_space_and_lease_for_basic_tenant():
        row = _row(
            member_raw="Jane Doe",
            full_price=Decimal("300.00"),
            actual_paid=Decimal("300.00"),
            deposit=Decimal("200.00"),
            notes="good tenant",
        )
        acc = FixtureAccumulator()
        _handle_tenant_row(row, acc)
        assert len(acc.spaces) == 1
        assert acc.spaces[0]["status"] == "occupied"
        assert len(acc.leases) == 1
        lease = acc.leases[0]
        assert lease["content_type"] == ["membership", "member"]
        assert lease["monthly_rent"] == "300.00"
        assert lease["base_price"] == "300.00"
        assert lease["is_split"] is False
        assert lease["lease_type"] == "month_to_month"

    def it_detects_split_lease_when_open_val_and_actual_paid_present():
        row = _row(
            member_raw="John Smith",
            full_price=Decimal("400.00"),
            open_val=Decimal("200.00"),
            actual_paid=Decimal("200.00"),
            notes="",
        )
        acc = FixtureAccumulator()
        _handle_tenant_row(row, acc)
        assert acc.leases[0]["is_split"] is True

    def it_does_not_split_when_actual_paid_is_zero():
        row = _row(
            member_raw="John Smith",
            full_price=Decimal("400.00"),
            open_val=Decimal("200.00"),
            actual_paid=Decimal("0.00"),
            notes="",
        )
        acc = FixtureAccumulator()
        _handle_tenant_row(row, acc)
        assert acc.leases[0]["is_split"] is False

    def it_applies_lease_overrides_for_prepaid_through():
        # Use a known override: ("B1", "Francisco Salgado")
        row = _row(
            space_id="B1",
            space_code="B1 Studio",
            member_raw="Francisco Salgado",
            full_price=Decimal("500.00"),
            actual_paid=Decimal("500.00"),
            notes="",
        )
        acc = FixtureAccumulator()
        _handle_tenant_row(row, acc)
        lease = acc.leases[0]
        assert lease["lease_type"] == "annual"
        assert lease["prepaid_through"] == "2026-07-01"
        assert lease["discount_reason"] == "One year term prepaid"

    def it_applies_monthly_rent_override():
        # ("B16", "Sy Baskent") has monthly_rent_override=0.00
        row = _row(
            space_id="B16",
            space_code="B16 Studio",
            member_raw="Sy Baskent",
            full_price=Decimal("300.00"),
            actual_paid=Decimal("300.00"),
            notes="",
        )
        acc = FixtureAccumulator()
        _handle_tenant_row(row, acc)
        lease = acc.leases[0]
        assert lease["monthly_rent"] == "0.00"

    def it_applies_is_split_override():
        # ("A44", "Allyson Barlow") has is_split_override=True
        row = _row(
            space_id="A44",
            space_code="A44 Studio",
            member_raw="Allyson Barlow",
            full_price=Decimal("200.00"),
            actual_paid=Decimal("200.00"),
            notes="",
        )
        acc = FixtureAccumulator()
        _handle_tenant_row(row, acc)
        assert acc.leases[0]["is_split"] is True

    def it_warns_on_zero_rent_with_no_override():
        row = _row(
            space_id="Z99",
            member_raw="Free Rider",
            full_price=Decimal("300.00"),
            actual_paid=Decimal("0.00"),
            notes="",
        )
        acc = FixtureAccumulator()
        _handle_tenant_row(row, acc)
        assert len(acc.warnings) == 1
        assert "$0 rent" in acc.warnings[0]
        assert "Free Rider" in acc.warnings[0]

    def it_does_not_warn_on_zero_rent_with_monthly_rent_override():
        # ("B16", "Sy Baskent") has monthly_rent_override=0.00, so no warning
        row = _row(
            space_id="B16",
            member_raw="Sy Baskent",
            full_price=Decimal("300.00"),
            actual_paid=Decimal("0.00"),
            notes="",
        )
        acc = FixtureAccumulator()
        _handle_tenant_row(row, acc)
        assert len(acc.warnings) == 0

    def it_defaults_monthly_rent_to_zero_when_actual_paid_is_none():
        row = _row(
            member_raw="Jane Doe",
            full_price=Decimal("300.00"),
            actual_paid=None,
            notes="",
        )
        acc = FixtureAccumulator()
        _handle_tenant_row(row, acc)
        assert acc.leases[0]["monthly_rent"] == "0.00"

    def it_defaults_base_price_to_zero_when_full_price_is_none():
        row = _row(
            member_raw="Jane Doe",
            full_price=None,
            actual_paid=Decimal("200.00"),
            notes="",
        )
        acc = FixtureAccumulator()
        _handle_tenant_row(row, acc)
        assert acc.leases[0]["base_price"] == "0.00"


# ---------------------------------------------------------------------------
# _build_fixture_json (lines 637-747)
# ---------------------------------------------------------------------------


def describe_build_fixture_json():
    """Test _build_fixture_json assembles the final fixture list."""

    def it_builds_fixture_with_membership_plan():
        acc = FixtureAccumulator()
        fixture = _build_fixture_json(acc)
        assert len(fixture) >= 1
        plan_entry = fixture[0]
        assert plan_entry["model"] == "membership.membershipplan"
        assert plan_entry["pk"] == STANDARD_PLAN_PK
        assert plan_entry["fields"]["name"] == "Standard"
        assert plan_entry["fields"]["monthly_price"] == STANDARD_PLAN_PRICE
        assert plan_entry["fields"]["created_at"] == CREATED_AT

    def it_includes_guilds_sorted_by_pk():
        acc = FixtureAccumulator()
        acc.get_or_create_guild("Ceramics Guild")
        acc.get_or_create_guild("Glass Guild")
        fixture = _build_fixture_json(acc)
        guild_entries = [e for e in fixture if e["model"] == "membership.guild"]
        assert len(guild_entries) == 2
        assert guild_entries[0]["fields"]["name"] == "Ceramics Guild"
        assert guild_entries[0]["pk"] == 1
        assert guild_entries[1]["fields"]["name"] == "Glass Guild"
        assert guild_entries[1]["pk"] == 2

    def it_includes_members_sorted_by_pk():
        acc = FixtureAccumulator()
        acc.get_or_create_member("Alice Wonder")
        acc.get_or_create_member("Ochen")
        fixture = _build_fixture_json(acc)
        member_entries = [e for e in fixture if e["model"] == "membership.member"]
        assert len(member_entries) == 2
        alice = member_entries[0]
        assert alice["fields"]["full_legal_name"] == "Alice Wonder"
        assert alice["fields"]["preferred_name"] == ""
        assert alice["fields"]["membership_plan"] == STANDARD_PLAN_PK
        assert alice["fields"]["status"] == "active"
        ochen = member_entries[1]
        assert ochen["fields"]["full_legal_name"] == "Ochen Kaylan"
        assert ochen["fields"]["preferred_name"] == "Ochen"

    def it_includes_spaces_with_sequential_pks():
        acc = FixtureAccumulator()
        acc.spaces.append({
            "space_id": "A1",
            "name": "A1 Studio",
            "space_type": "studio",
            "size_sqft": "100",
            "width": "10",
            "depth": "10",
            "rate_per_sqft": "3.75",
            "is_rentable": True,
            "manual_price": "375.00",
            "status": "occupied",
            "sublet_guild": None,
            "notes": "test",
        })
        acc.spaces.append({
            "space_id": "B1",
            "name": "B1 Studio",
            "space_type": "studio",
            "size_sqft": "200",
            "width": "20",
            "depth": "10",
            "rate_per_sqft": "3.50",
            "is_rentable": True,
            "manual_price": None,
            "status": "available",
            "sublet_guild": ["Glass Guild"],
            "notes": "",
        })
        fixture = _build_fixture_json(acc)
        space_entries = [e for e in fixture if e["model"] == "membership.space"]
        assert len(space_entries) == 2
        assert space_entries[0]["pk"] == 1
        assert space_entries[0]["fields"]["space_id"] == "A1"
        assert space_entries[0]["fields"]["floorplan_ref"] == ""
        assert space_entries[1]["pk"] == 2
        assert space_entries[1]["fields"]["space_id"] == "B1"

    def it_resolves_lease_space_fk_to_integer_pk():
        acc = FixtureAccumulator()
        acc.spaces.append({
            "space_id": "A1",
            "name": "A1 Studio",
            "space_type": "studio",
            "size_sqft": None,
            "width": None,
            "depth": None,
            "rate_per_sqft": None,
            "is_rentable": True,
            "manual_price": None,
            "status": "occupied",
            "sublet_guild": None,
            "notes": "",
        })
        acc.leases.append(
            _make_lease(
                1,
                content_type=["membership", "member"],
                object_id=1,
                space_id="A1",
                base_price=Decimal("200.00"),
                monthly_rent=Decimal("200.00"),
                deposit=None,
                notes="",
            )
        )
        fixture = _build_fixture_json(acc)
        lease_entries = [e for e in fixture if e["model"] == "membership.lease"]
        assert len(lease_entries) == 1
        # Space "A1" is the first (and only) space, so its PK is 1
        assert lease_entries[0]["fields"]["space"] == 1
        assert lease_entries[0]["fields"]["content_type"] == ["membership", "member"]
        assert lease_entries[0]["fields"]["lease_type"] == "month_to_month"
        assert lease_entries[0]["fields"]["is_split"] is False

    def it_produces_all_model_types_in_correct_order():
        acc = FixtureAccumulator()
        acc.get_or_create_guild("Test Guild")
        acc.get_or_create_member("Jane Doe")
        acc.spaces.append({
            "space_id": "A1",
            "name": "A1",
            "space_type": "studio",
            "size_sqft": None,
            "width": None,
            "depth": None,
            "rate_per_sqft": None,
            "is_rentable": True,
            "manual_price": None,
            "status": "occupied",
            "sublet_guild": None,
            "notes": "",
        })
        acc.leases.append(
            _make_lease(
                1,
                content_type=["membership", "member"],
                object_id=1,
                space_id="A1",
                base_price=Decimal("200.00"),
                monthly_rent=Decimal("200.00"),
                deposit=None,
                notes="",
            )
        )
        fixture = _build_fixture_json(acc)
        models = [e["model"] for e in fixture]
        assert models[0] == "membership.membershipplan"
        assert models[1] == "membership.guild"
        assert models[2] == "membership.member"
        assert models[3] == "membership.space"
        assert models[4] == "membership.lease"


# ---------------------------------------------------------------------------
# _print_report (lines 757-798)
# ---------------------------------------------------------------------------


def describe_print_report():
    """Test _print_report outputs correct report to stderr."""

    def it_prints_basic_report_with_counts():
        acc = FixtureAccumulator()
        acc.get_or_create_guild("Test Guild")
        acc.get_or_create_member("Jane Doe")
        acc.spaces.append({"space_id": "A1"})
        acc.leases.append(
            _make_lease(
                1,
                content_type=["membership", "member"],
                object_id=1,
                space_id="A1",
                base_price=Decimal("200.00"),
                monthly_rent=Decimal("200.00"),
                deposit=None,
                notes="",
            )
        )
        captured = io.StringIO()
        with mock.patch("sys.stderr", captured):
            _print_report(acc)
        output = captured.getvalue()
        assert "FIXTURE GENERATION REPORT" in output
        assert "Guild:          1" in output
        assert "Member:         1" in output
        assert "Space:          1" in output
        assert "Lease:          1" in output
        assert "TOTAL:          5" in output
        assert "[1] Test Guild" in output
        assert "Jane Doe" in output

    def it_prints_preferred_name_for_ochen():
        acc = FixtureAccumulator()
        acc.get_or_create_member("Ochen")
        captured = io.StringIO()
        with mock.patch("sys.stderr", captured):
            _print_report(acc)
        output = captured.getvalue()
        assert 'preferred: "Ochen"' in output

    def it_prints_split_leases_section():
        acc = FixtureAccumulator()
        acc.spaces.append({"space_id": "A1"})
        acc.leases.append(
            _make_lease(
                1,
                content_type=["membership", "member"],
                object_id=1,
                space_id="A1",
                base_price=Decimal("400.00"),
                monthly_rent=Decimal("200.00"),
                deposit=None,
                notes="",
                is_split=True,
            )
        )
        captured = io.StringIO()
        with mock.patch("sys.stderr", captured):
            _print_report(acc)
        output = captured.getvalue()
        assert "Split spaces (1):" in output
        assert "A1: rent=200.00" in output

    def it_prints_zero_rent_leases_section():
        acc = FixtureAccumulator()
        acc.spaces.append({"space_id": "B1"})
        acc.leases.append(
            _make_lease(
                1,
                content_type=["membership", "member"],
                object_id=1,
                space_id="B1",
                base_price=Decimal("300.00"),
                monthly_rent=Decimal("0.00"),
                deposit=None,
                notes="",
            )
        )
        captured = io.StringIO()
        with mock.patch("sys.stderr", captured):
            _print_report(acc)
        output = captured.getvalue()
        assert "$0 rent leases (1):" in output
        assert "B1: member #1" in output

    def it_prints_warnings_section():
        acc = FixtureAccumulator()
        acc.warnings.append("Test warning message")
        captured = io.StringIO()
        with mock.patch("sys.stderr", captured):
            _print_report(acc)
        output = captured.getvalue()
        assert "Warnings (1):" in output
        assert "WARNING: Test warning message" in output

    def it_skips_split_section_when_no_splits():
        acc = FixtureAccumulator()
        captured = io.StringIO()
        with mock.patch("sys.stderr", captured):
            _print_report(acc)
        output = captured.getvalue()
        assert "Split spaces" not in output

    def it_skips_zero_rent_section_when_none():
        acc = FixtureAccumulator()
        captured = io.StringIO()
        with mock.patch("sys.stderr", captured):
            _print_report(acc)
        output = captured.getvalue()
        assert "$0 rent leases" not in output

    def it_skips_warnings_section_when_no_warnings():
        acc = FixtureAccumulator()
        captured = io.StringIO()
        with mock.patch("sys.stderr", captured):
            _print_report(acc)
        output = captured.getvalue()
        assert "Warnings" not in output

    def it_detects_zero_rent_with_string_zero():
        acc = FixtureAccumulator()
        acc.spaces.append({"space_id": "C1"})
        # _make_lease returns monthly_rent as string "0" when Decimal("0") is passed
        acc.leases.append(
            _make_lease(
                1,
                content_type=["membership", "guild"],
                object_id=1,
                space_id="C1",
                base_price=Decimal("100.00"),
                monthly_rent=Decimal("0"),
                deposit=None,
                notes="",
            )
        )
        captured = io.StringIO()
        with mock.patch("sys.stderr", captured):
            _print_report(acc)
        output = captured.getvalue()
        assert "$0 rent leases (1):" in output
        assert "C1: guild #1" in output


# ---------------------------------------------------------------------------
# generate_fixture (lines 808-822)
# ---------------------------------------------------------------------------


def describe_generate_fixture():
    """Test the top-level generate_fixture function end-to-end."""

    def _write_csv(rows_data):
        """Helper to write a CSV file and return its path."""
        header = "Space Code,Label,Member,Full Price,Open,Actual Amount Paid,Dollar Loss,Dimensions,Sq Ft,Deviation,Earn Money,Paid Deposit,Notes,Accurate Complete,Rate Per Sq Ft"
        lines = [header] + rows_data
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8")
        f.write("\n".join(lines) + "\n")
        f.flush()
        f.close()
        return f.name

    def it_generates_valid_json_for_a_simple_tenant():
        path = _write_csv([
            'A1 Studio,Occupied,Jane Doe,$255.00,,$255.00,,8 x 10,80,,,,some note,,3.19',
        ])
        try:
            captured = io.StringIO()
            with mock.patch("sys.stderr", captured):
                output = generate_fixture(path)
            fixture = json.loads(output)
            models = [e["model"] for e in fixture]
            assert "membership.membershipplan" in models
            assert "membership.member" in models
            assert "membership.space" in models
            assert "membership.lease" in models
        finally:
            os.unlink(path)

    def it_handles_guild_space_rows():
        guild_space_id = next(iter(GUILD_SPACE_MAP))
        path = _write_csv([
            f'{guild_space_id} Workshop,Guild,PLM,$500.00,,$450.00,,10 x 20,200,,,,guild note,,2.50',
        ])
        try:
            captured = io.StringIO()
            with mock.patch("sys.stderr", captured):
                output = generate_fixture(path)
            fixture = json.loads(output)
            guild_entries = [e for e in fixture if e["model"] == "membership.guild"]
            assert len(guild_entries) == 1
        finally:
            os.unlink(path)

    def it_handles_vacant_spaces():
        path = _write_csv([
            'A5 Studio,Open,X,$300.00,$150.00,,,8 x 10,80,,,,vacant,,3.75',
        ])
        try:
            captured = io.StringIO()
            with mock.patch("sys.stderr", captured):
                output = generate_fixture(path)
            fixture = json.loads(output)
            space_entries = [e for e in fixture if e["model"] == "membership.space"]
            assert len(space_entries) == 1
            assert space_entries[0]["fields"]["status"] == "available"
            # No leases for vacant spaces
            lease_entries = [e for e in fixture if e["model"] == "membership.lease"]
            assert len(lease_entries) == 0
        finally:
            os.unlink(path)

    def it_handles_multiple_row_types():
        guild_space_id = next(iter(GUILD_SPACE_MAP))
        facility_space_id = next(iter(FACILITY_SPACES))
        path = _write_csv([
            'A1 Studio,Occupied,Jane Doe,$255.00,,$255.00,,8 x 10,80,,,,note,,3.19',
            f'{guild_space_id} Workshop,Guild,PLM,$500.00,,$450.00,,,,,,,,,,',
            f'{facility_space_id},Facility,PLM,,,,,,,,,,,,,',
            'A5 Studio,Open,X,$300.00,$150.00,,,8 x 10,80,,,,,,3.75',
        ])
        try:
            captured = io.StringIO()
            with mock.patch("sys.stderr", captured):
                output = generate_fixture(path)
            fixture = json.loads(output)
            assert len(fixture) > 0
            # Should have at least plan, member, guild, spaces, leases
            models = {e["model"] for e in fixture}
            assert "membership.membershipplan" in models
            assert "membership.member" in models
            assert "membership.guild" in models
            assert "membership.space" in models
            assert "membership.lease" in models
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# __main__ block (lines 830-836)
# ---------------------------------------------------------------------------


def describe_main_block():
    """Test the __main__ entry point of the script."""

    def it_prints_usage_and_exits_with_wrong_arg_count():
        result = subprocess.run(
            [sys.executable, str(_script_path)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "Usage:" in result.stderr

    def it_prints_usage_when_too_many_args():
        result = subprocess.run(
            [sys.executable, str(_script_path), "arg1", "arg2"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert "Usage:" in result.stderr

    def it_generates_fixture_json_from_csv_file():
        csv_content = textwrap.dedent("""\
            Space Code,Label,Member,Full Price,Open,Actual Amount Paid,Dollar Loss,Dimensions,Sq Ft,Deviation,Earn Money,Paid Deposit,Notes,Accurate Complete,Rate Per Sq Ft
            A1 Studio,Occupied,Jane Doe,$255.00,,$255.00,,8 x 10,80,,,,test note,,3.19
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write(csv_content)
            f.flush()
            try:
                result = subprocess.run(
                    [sys.executable, str(_script_path), f.name],
                    capture_output=True,
                    text=True,
                )
                assert result.returncode == 0
                fixture = json.loads(result.stdout)
                assert len(fixture) > 0
                assert fixture[0]["model"] == "membership.membershipplan"
                # Report goes to stderr
                assert "FIXTURE GENERATION REPORT" in result.stderr
            finally:
                os.unlink(f.name)
