"""
ING exports in every layout Finsight knows about. All data is made up;
the layouts follow ING's documented column lists.
"""

import pytest

from categorizer import DEFAULT_CATEGORY_RULES
from corrections import empty_corrections
from flows import default_settings
from parsers.detector import detect_bank
from parsers.ing import is_ing_export
from parsers.loader import load_bank_csv
from pipeline import build_transactions
from statements import parse_statement
from tests.helpers import SAMPLE_DATA

PAYMENT_HEADER = (
    '"Datum";"Naam / Omschrijving";"Rekening";"Tegenrekening";"Code";'
    '"Af Bij";"Bedrag (EUR)";"Mutatiesoort";"Mededelingen";'
    '"Saldo na mutatie";"Tag"'
)

PAYMENT_ROWS = [
    '"20260912";"Albert Heijn 1234";"NL12INGB0123456789";"";"BA";"Af";'
    '"34,82";"Betaalautomaat";"Pasvolgnr: 001 12-09-2026 14:32 '
    'Transactie: 1A2B3C Term: AB123C Valutadatum: 12-09-2026";"3615,18";""',
    '"20260910";"Werkgever BV";"NL12INGB0123456789";"NL03BANK1234567890";'
    '"OV";"Bij";"2.150,00";"Overschrijving";"Naam: Werkgever BV '
    'Omschrijving: Salaris september";"3650,00";""',
]


def parse(text, encoding="utf-8"):
    return parse_statement(text.encode(encoding))


def amounts(df):
    return dict(zip(df["description"], df["amount"]))


def payment_csv(separator=";"):
    lines = [PAYMENT_HEADER] + PAYMENT_ROWS
    return "\n".join(line.replace('";"', f'"{separator}"') for line in lines)


# ------------------------------------------------------------
# Payment accounts
# ------------------------------------------------------------

@pytest.mark.parametrize("separator", [";", ","])
def test_payment_account_with_either_separator(separator):
    bank, df = parse(payment_csv(separator))

    assert bank == "ing"
    assert amounts(df) == {
        "Albert Heijn 1234": pytest.approx(-34.82),
        "Werkgever BV": pytest.approx(2150.00),
    }
    assert df["balance"].tolist() == pytest.approx([3650.00, 3615.18])
    assert set(df["currency"]) == {"EUR"}
    assert set(df["account"]) == {"NL12INGB0123456789"}


def test_oldest_transaction_first():
    _, df = parse(payment_csv())

    assert df["description"].tolist() == ["Werkgever BV", "Albert Heijn 1234"]


def test_mededelingen_kept_for_categorizing():
    _, df = parse(payment_csv())

    details = dict(zip(df["description"], df["details"]))

    assert "Salaris september" in details["Werkgever BV"]


def test_amounts_with_decimal_point():
    # In case the comma-separated export writes 34.82 instead of 34,82.
    csv = payment_csv(",").replace('"34,82"', '"34.82"').replace(
        '"2.150,00"', '"2150.00"'
    )

    _, df = parse(csv)

    assert amounts(df) == {
        "Albert Heijn 1234": pytest.approx(-34.82),
        "Werkgever BV": pytest.approx(2150.00),
    }


def test_older_export_without_balance_and_tag():
    csv = (
        '"Datum";"Naam / Omschrijving";"Rekening";"Tegenrekening";"Code";'
        '"Af Bij";"Bedrag (EUR)";"MutatieSoort";"Mededelingen"\n'
        '"20190312";"Jumbo Eindhoven";"NL12INGB0123456789";"";"BA";"Af";'
        '"12,50";"Betaalautomaat";"Pasvolgnr: 001"\n'
    )

    bank, df = parse(csv)

    assert bank == "ing"
    assert df["amount"].tolist() == pytest.approx([-12.50])
    assert df["transaction_type"].tolist() == ["Betaalautomaat"]
    assert df["balance"].isna().all()


def test_empty_name_falls_back_to_mededelingen():
    csv = PAYMENT_HEADER + (
        '\n"20260901";"";"NL12INGB0123456789";"";"DV";"Af";"2,95";'
        '"Diversen";"Kosten OranjePakket";"100,00";""'
    )

    _, df = parse(csv)

    assert df["description"].tolist() == ["Kosten OranjePakket"]


def test_english_export():
    csv = (
        '"Date";"Name / Description";"Account";"Counterparty";"Code";'
        '"Debit/credit";"Amount (EUR)";"Transaction type";"Notifications";'
        '"Resulting balance";"Tag"\n'
        '"20260912";"Albert Heijn 1234";"NL12INGB0123456789";"";"BA";'
        '"Debit";"34,82";"Payment terminal";"Card sequence no.: 001";'
        '"1465,18";""\n'
        '"20260910";"Employer BV";"NL12INGB0123456789";"NL03BANK1234567890";'
        '"OV";"Credit";"850,00";"Transfer";"Salary";"1500,00";""\n'
    )

    bank, df = parse(csv)

    assert bank == "ing"
    assert amounts(df) == {
        "Albert Heijn 1234": pytest.approx(-34.82),
        "Employer BV": pytest.approx(850.00),
    }
    assert set(df["currency"]) == {"EUR"}


def test_windows_encoded_export():
    csv = PAYMENT_HEADER + (
        '\n"20260901";"Café de Zwaan";"NL12INGB0123456789";"";"BA";"Af";'
        '"4,50";"Betaalautomaat";"";"100,00";""'
    )

    _, df = parse(csv, encoding="cp1252")

    assert df["description"].tolist() == ["Café de Zwaan"]


# ------------------------------------------------------------
# Savings accounts
# ------------------------------------------------------------

def test_savings_account_sample():
    bank, df = parse_statement((SAMPLE_DATA / "ing_savings_sample.csv").read_bytes())

    assert bank == "ing"
    assert df["date"].dt.strftime("%Y-%m-%d").tolist() == [
        "2026-09-10",
        "2026-09-20",
        "2026-09-30",
    ]
    assert df["amount"].tolist() == pytest.approx([300.00, -50.00, 4.17])
    assert set(df["account"]) == {"V12345678"}
    assert set(df["currency"]) == {"EUR"}
    assert df["transaction_type"].tolist() == ["Overschrijving", "Overschrijving", "Rente"]


def test_savings_and_payment_account_together():
    names = ["multi_account_ing.csv", "ing_savings_sample.csv"]

    df, loaded, failed = build_transactions(
        [(name, (SAMPLE_DATA / name).read_bytes()) for name in names],
        DEFAULT_CATEGORY_RULES,
        default_settings(),
        empty_corrections(),
    )

    assert failed == {}
    assert set(loaded.values()) == {"ing"}

    flows = dict(zip(zip(df["account"], df["amount"]), df["flow"]))

    # The €300 leaving the payment account and arriving in savings is a
    # transfer on both sides, and so is the €50 moved back.
    assert flows[("NL12INGB0123456789", -300.00)] == "transfer"
    assert flows[("V12345678", 300.00)] == "transfer"
    assert flows[("V12345678", -50.00)] == "transfer"

    # Interest is real income.
    assert flows[("V12345678", 4.17)] == "income"


# ------------------------------------------------------------
# Detection
# ------------------------------------------------------------

def test_generic_english_file_is_not_mistaken_for_ing():
    columns = ["Date", "Description", "Account", "Debit/credit", "Amount"]

    assert not is_ing_export(columns)


def test_detects_ing_with_extra_spaces_in_header():
    csv = PAYMENT_HEADER.replace('"Af Bij"', '" Af  Bij "') + "\n" + PAYMENT_ROWS[0]

    import io

    raw = load_bank_csv(io.BytesIO(csv.encode()))

    assert detect_bank(raw) == "ing"
