import pandas as pd
import pytest

from categorizer import DEFAULT_CATEGORY_RULES
from corrections import empty_corrections
from currency import clean_rates, convert_to_home_currency, foreign_currencies
from flows import default_settings
from pipeline import build_transactions


def transactions():
    return pd.DataFrame(
        {
            "description": ["Albert Heijn", "Amazon US", "Tesco", "Cash"],
            "amount": [-40.0, -50.0, -20.0, -10.0],
            "fee": [0.0, 1.0, 0.0, 0.0],
            "currency": ["EUR", "USD", "GBP", "Unknown"],
        }
    )


def test_foreign_currencies_ignore_euros_and_unstated():
    assert foreign_currencies(transactions()) == ["GBP", "USD"]


def test_conversion_with_rates():
    df, missing = convert_to_home_currency(
        transactions(),
        {"USD": 0.9, "GBP": 1.2},
    )

    assert df["amount"].tolist() == [-40.0, -45.0, -24.0, -10.0]
    assert df["fee"].tolist() == [0.0, 0.9, 0.0, 0.0]
    assert set(df["currency"]) == {"EUR", "Unknown"}
    assert missing == []


def test_original_amount_and_currency_are_kept():
    df, _ = convert_to_home_currency(transactions(), {"USD": 0.9})

    assert df["original_amount"].tolist() == [-40.0, -50.0, -20.0, -10.0]
    # Unstated currency counts as the home currency.
    assert df["original_currency"].tolist() == ["EUR", "USD", "GBP", "EUR"]


def test_currencies_without_a_rate_are_left_and_reported():
    df, missing = convert_to_home_currency(transactions(), {"USD": 0.9})

    assert missing == ["GBP"]
    assert df.loc[2, "amount"] == pytest.approx(-20.0)
    assert df.loc[2, "currency"] == "GBP"


def test_invalid_rates_are_ignored():
    assert clean_rates({"usd": "0.9", "GBP": 0, "JPY": "abc", "CHF": None}) == {"USD": 0.9}


def test_exchange_between_own_currencies_stays_a_transfer():
    # Revolut: €50 exchanged to $54.20. Both halves are transfers; after
    # conversion they must still not count as income or spending.
    csv = (
        "Type,Product,Started Date,Completed Date,Description,"
        "Amount,Fee,Currency,State,Balance\n"
        "EXCHANGE,Current,2026-09-14 10:00:00,2026-09-14 10:00:00,"
        "Exchanged to USD,-50.00,0.50,EUR,COMPLETED,100.00\n"
        "EXCHANGE,Current,2026-09-14 10:00:00,2026-09-14 10:00:00,"
        "Exchanged from EUR,54.20,0.00,USD,COMPLETED,54.20\n"
        "CARD_PAYMENT,Current,2026-09-15 12:00:00,2026-09-15 12:00:00,"
        "Diner NYC,-30.00,0.00,USD,COMPLETED,24.20\n"
    )

    settings = default_settings()
    settings["exchange_rates"] = {"USD": 0.92}

    df, _, _ = build_transactions(
        [("revolut.csv", csv.encode())],
        DEFAULT_CATEGORY_RULES,
        settings,
        empty_corrections(),
    )

    flows = dict(zip(df["description"], df["flow"]))

    assert flows["Exchanged to USD"] == "transfer"
    assert flows["Exchanged from EUR"] == "transfer"

    diner = df[df["description"] == "Diner NYC"].iloc[0]

    assert diner["amount"] == pytest.approx(-27.60)
    assert diner["currency"] == "EUR"
    assert diner["original_amount"] == pytest.approx(-30.00)
    assert diner["original_currency"] == "USD"
