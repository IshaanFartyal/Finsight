"""
bunq exports. All data is made up; the layout follows the six-column
CSV format bunq users have documented.
"""

import pytest

from categorizer import DEFAULT_CATEGORY_RULES
from corrections import empty_corrections
from flows import default_settings
from parsers.bunq import is_bunq_export
from pipeline import build_transactions
from statements import parse_statement
from tests.helpers import SAMPLE_DATA, load_sample

MAIN = "NL12BUNQ0123456789"
SAVINGS = "NL34BUNQ0987654321"

SAMPLE = (SAMPLE_DATA / "bunq_sample.csv").read_bytes()


def by_description(df, column):
    return dict(zip(df["description"], df[column]))


def test_detected_as_bunq():
    bank, _, df = load_sample("bunq_sample.csv")

    assert bank == "bunq"
    assert set(df["bank"]) == {"bunq"}


def test_signed_amounts_with_decimal_comma():
    _, _, df = load_sample("bunq_sample.csv")

    amounts = by_description(df, "amount")

    assert amounts["Werkgever BV"] == pytest.approx(2600.00)
    assert amounts["Albert Heijn 1234"] == pytest.approx(-42.35)


def test_sub_accounts_in_one_file():
    _, _, df = load_sample("bunq_sample.csv")

    assert set(df["account"]) == {MAIN, SAVINGS}
    assert by_description(df, "counterparty_account")["DUWO"] == "NL44DUWO0123456789"


def test_description_is_kept_as_details():
    _, _, df = load_sample("bunq_sample.csv")

    assert by_description(df, "details")["Werkgever BV"] == "Salaris september 2026"


def test_no_name_falls_back_to_the_description():
    _, _, df = load_sample("bunq_sample.csv")

    assert "Interest payment September" in df["description"].tolist()


def test_fields_bunq_does_not_export():
    _, _, df = load_sample("bunq_sample.csv")

    assert df["balance"].isna().all()
    assert set(df["currency"]) == {"EUR"}


def test_oldest_first():
    _, _, df = load_sample("bunq_sample.csv")

    assert df["date"].is_monotonic_increasing
    assert df["description"].iloc[0] == "Werkgever BV"


def test_older_export_without_interest_date():
    csv = (
        '"Date","Amount","Account","Counterparty","Name","Description"\n'
        '"2017-04-03","-13,00","NL12BUNQ0123456789","NL01BANK1234567890",'
        '"Bakkerij Jansen","Brood"\n'
    )

    bank, df = parse_statement(csv.encode())

    assert bank == "bunq"
    assert df["amount"].tolist() == pytest.approx([-13.00])


def test_dutch_export_with_semicolons():
    csv = (
        '"Datum";"Bedrag";"Rekening";"Tegenrekening";"Naam";"Omschrijving"\n'
        '"2026-09-03";"-42,35";"NL12BUNQ0123456789";"";"Albert Heijn 1234";'
        '"Albert Heijn 1234 Eindhoven, NL"\n'
    )

    bank, df = parse_statement(csv.encode())

    assert bank == "bunq"
    assert df["amount"].tolist() == pytest.approx([-42.35])
    assert df["description"].tolist() == ["Albert Heijn 1234"]


def test_identical_transactions_are_both_kept():
    # bunq exports no time or sequence number, so two equal payments on
    # one day are two identical lines.
    csv = (
        '"Date","Amount","Account","Counterparty","Name","Description"\n'
        '"2026-09-03","-3,50","NL12BUNQ0123456789","","Coffee Corner","Coffee"\n'
        '"2026-09-03","-3,50","NL12BUNQ0123456789","","Coffee Corner","Coffee"\n'
    )

    df, _, _ = build_transactions(
        [("bunq.csv", csv.encode())],
        DEFAULT_CATEGORY_RULES,
        default_settings(),
        empty_corrections(),
    )

    assert len(df) == 2
    assert df["transaction_id"].nunique() == 2


def test_files_with_other_columns_are_not_bunq():
    bunq = ["Date", "Amount", "Account", "Counterparty", "Name", "Description"]

    assert is_bunq_export(bunq)
    assert not is_bunq_export(bunq + ["Balance"])
    assert not is_bunq_export(["Date", "Amount", "Description"])


def test_pipeline_recognizes_transfers_and_categories():
    df, loaded, failed = build_transactions(
        [("bunq_sample.csv", SAMPLE)],
        DEFAULT_CATEGORY_RULES,
        default_settings(),
        empty_corrections(),
    )

    assert failed == {}
    assert loaded == {"bunq_sample.csv": "bunq"}

    flows = dict(zip(zip(df["account"], df["amount"]), df["flow"]))
    categories = by_description(df, "category")

    # Main account -> savings sub-account, both in the same file.
    assert flows[(MAIN, -250.00)] == "transfer"
    assert flows[(SAVINGS, 250.00)] == "transfer"

    # Interest is real income.
    assert flows[(SAVINGS, 0.42)] == "income"

    assert categories["Albert Heijn 1234"] == "Groceries"
    assert categories["Werkgever BV"] == "Income"
    assert categories["Spotify AB"] == "Subscriptions"
