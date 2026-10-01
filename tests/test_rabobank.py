"""
Rabobank exports. All data is made up; the layout follows Rabobank's
documented 26-column CSV format.
"""

import pytest

from categorizer import DEFAULT_CATEGORY_RULES
from corrections import empty_corrections
from flows import default_settings
from parsers.rabobank import is_rabobank_export, join_notes
from pipeline import build_transactions
from statements import parse_statement
from tests.helpers import SAMPLE_DATA, load_sample

PAYMENT = "NL44RABO0123456789"
SAVINGS = "NL55RABO0987654321"

SAMPLE = (SAMPLE_DATA / "rabobank_sample.csv").read_bytes()


def by_description(df, column):
    return dict(zip(df["description"], df[column]))


def test_detected_as_rabobank():
    bank, _, df = load_sample("rabobank_sample.csv")

    assert bank == "rabobank"
    assert set(df["bank"]) == {"Rabobank"}


def test_signed_amounts_with_decimal_comma():
    _, _, df = load_sample("rabobank_sample.csv")

    amounts = by_description(df, "amount")

    assert amounts["Werkgever BV"] == pytest.approx(2600.00)
    assert amounts["Albert Heijn 1234 EINDHOVEN"] == pytest.approx(-42.35)


def test_balance_and_currency():
    _, _, df = load_sample("rabobank_sample.csv")

    assert by_description(df, "balance")["Werkgever BV"] == pytest.approx(2811.65)
    assert set(df["currency"]) == {"EUR"}


def test_foreign_card_payment_uses_the_euro_amount():
    # Paid 19.99 GBP; Rabobank books it in euros in "Bedrag".
    _, _, df = load_sample("rabobank_sample.csv")

    assert by_description(df, "amount")["Bookshop LONDON GBR"] == pytest.approx(-23.61)


def test_several_accounts_in_one_file():
    _, _, df = load_sample("rabobank_sample.csv")

    assert set(df["account"]) == {PAYMENT, SAVINGS}


def test_description_columns_are_joined_as_details():
    _, _, df = load_sample("rabobank_sample.csv")

    details = by_description(df, "details")

    assert details["Werkgever BV"] == "Salaris september 2026"
    assert details["Albert Heijn 1234 EINDHOVEN"] == (
        "Betaalautomaat 18:04 pasnr. 012 Apple Pay"
    )


def test_no_counterparty_name_falls_back_to_the_notes():
    _, _, df = load_sample("rabobank_sample.csv")

    assert "Creditrente over september" in df["description"].tolist()


def test_oldest_first_in_booking_order():
    _, _, df = load_sample("rabobank_sample.csv")

    assert df["date"].is_monotonic_increasing
    assert df["description"].iloc[0] == "Werkgever BV"


def test_join_notes_glues_a_full_column_to_the_next():
    full = "A" * 139 + "B"

    assert join_notes([full, "C rest", ""]) == full + "C rest"
    assert join_notes(["Factuur 123", "Klant 456", ""]) == "Factuur 123 Klant 456"
    assert join_notes(["", "", ""]) == ""


def test_windows_encoded_export():
    # The header itself has an ë ("Naam initiërende partij").
    text = SAMPLE.decode("utf-8").replace("Jumbo Eindhoven", "Café de Zwaan")

    bank, df = parse_statement(text.encode("cp1252"))

    assert bank == "rabobank"
    assert "Café de Zwaan" in df["description"].tolist()


def test_other_files_are_not_mistaken_for_rabobank():
    assert not is_rabobank_export(["Datum", "Bedrag", "Omschrijving"])
    assert not is_rabobank_export(["IBAN/BBAN", "Datum", "Bedrag"])


def test_pipeline_recognizes_transfers_and_categories():
    df, loaded, failed = build_transactions(
        [("rabobank_sample.csv", SAMPLE)],
        DEFAULT_CATEGORY_RULES,
        default_settings(),
        empty_corrections(),
    )

    assert failed == {}
    assert loaded == {"rabobank_sample.csv": "rabobank"}

    flows = dict(zip(zip(df["account"], df["amount"]), df["flow"]))
    categories = by_description(df, "category")

    # Payment account -> savings account, both in the same file.
    assert flows[(PAYMENT, -300.00)] == "transfer"
    assert flows[(SAVINGS, 300.00)] == "transfer"

    # Interest is real income.
    assert flows[(SAVINGS, 4.17)] == "income"

    assert categories["Albert Heijn 1234 EINDHOVEN"] == "Groceries"
    assert categories["Werkgever BV"] == "Income"
    assert categories["DUWO"] == "Housing"
    assert categories["NS Groep via Mollie"] == "Transport"
