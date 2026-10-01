"""
bunq exports (bunq app > Profile > Export statements > CSV).

Built from the format bunq users have documented and open-source
importers, not yet verified against a real export: please report
anything that parses wrongly.

The file has six columns, plus "Interest Date" in newer exports:

    "Date","Amount","Account","Counterparty","Name","Description"
    "2026-09-12","-34,82","NL12BUNQ0123456789","NL01BANK...","Albert Heijn","..."

- "Amount": signed, with a decimal comma.
- "Account": your own account; one file can hold several sub-accounts.
- "Counterparty" / "Name": the other side's IBAN and name.

With the app set to Dutch, the same columns have Dutch names.
"""

import re

import pandas as pd

from parsers.dates import parse_dates
from parsers.numbers import parse_numbers
from parsers.schema import STANDARD_COLUMNS

# Possible column names per field, in lower case: English, then Dutch.
COLUMNS = {
    "date": ["date", "datum"],
    "interest_date": ["interest date", "rentedatum"],
    "amount": ["amount", "bedrag"],
    "account": ["account", "rekening"],
    "counterparty": ["counterparty", "tegenrekening"],
    "name": ["name", "naam"],
    "notes": ["description", "omschrijving"],
}

REQUIRED = ["date", "amount", "account", "counterparty", "name", "notes"]


def _normalize(name):
    return re.sub(r"\s+", " ", str(name)).strip().lower()


def find_columns(columns):
    """Map each field in COLUMNS to the column holding it, or None."""

    available = {_normalize(column): column for column in columns}

    found = {}

    for field, names in COLUMNS.items():
        found[field] = next(
            (available[name] for name in names if name in available),
            None,
        )

    return found


def is_bunq_export(columns):
    """
    True when the file has exactly bunq's columns and nothing else.

    bunq's column names are ordinary words ("Date", "Amount", "Name"), so
    a file with any extra column is left to the other parsers.
    """

    found = find_columns(columns)
    known = {name for names in COLUMNS.values() for name in names}

    return (
        all(found[field] is not None for field in REQUIRED)
        and all(_normalize(column) in known for column in columns)
    )


def _text(df, column):
    if column is None:
        return pd.Series("", index=df.index, dtype=object)

    return df[column].fillna("").astype(str).str.strip()


def parse_bunq(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert a bunq export into Finsight's standard transaction format.
    """

    columns = find_columns(df.columns)

    missing = [field for field in REQUIRED if columns[field] is None]

    if missing:
        raise ValueError(
            "bunq CSV is missing required columns: " + ", ".join(missing)
        )

    df = df.copy()

    # Dates: 2026-09-12
    df["date"] = parse_dates(df[columns["date"]])

    # Description: the counterparty's name, or the payment description
    # when there is none (interest, bunq's own charges).
    notes = _text(df, columns["notes"])
    description = _text(df, columns["name"])
    description = description.where(description != "", notes)
    df["description"] = description.where(description != "", "Unknown transaction")

    # The payment description often holds the useful text, so the
    # categorizer searches it too.
    df["details"] = notes

    # Signed, with a decimal comma: -34,82 / 2.600,00
    df["amount"] = parse_numbers(df[columns["amount"]])

    # The export has no balance, currency or transaction type columns.
    df["balance"] = float("nan")
    df["currency"] = "EUR"
    df["transaction_type"] = ""

    df["account"] = _text(df, columns["account"])
    df["counterparty_account"] = _text(df, columns["counterparty"])

    df["fee"] = 0.0
    df["bank"] = "bunq"
    df["category"] = "Uncategorized"

    df = df.dropna(subset=["date", "amount"])

    # Oldest first. bunq lists newest first; "stable" keeps the order of
    # same-day transactions as bunq wrote them (reversed).
    df = df.iloc[::-1].sort_values("date", kind="stable")

    return df[STANDARD_COLUMNS].reset_index(drop=True)
