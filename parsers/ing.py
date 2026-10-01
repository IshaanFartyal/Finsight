"""
ING Netherlands exports (Mijn ING > Af- en bijschrijvingen downloaden).

Built from ING's documented column list and open-source importers, not
yet verified against a real export: please report anything that parses
wrongly.

Handles:

- payment accounts, semicolon- or comma-separated, with or without the
  newer "Saldo na mutatie" and "Tag" columns;
- savings accounts (e.g. Oranje Spaarrekening), which have their own
  layout: "Omschrijving", "Rekening naam", "Valuta", dates as 2026-09-10;
- Mijn ING set to English, which exports English column names
  ("Debit/credit", "Amount (EUR)", ...).

All layouts have an "Af Bij" (or "Debit/credit") column and amounts
without a sign: "Af" is money going out, "Bij" money coming in.
"""

import re

import pandas as pd

from parsers.dates import parse_dates
from parsers.numbers import parse_numbers
from parsers.schema import STANDARD_COLUMNS

# Possible column names per field, in lower case. The first name is
# the Dutch one; the others are the English export or older spellings
# (older exports wrote "MutatieSoort").
COLUMNS = {
    "date": ["datum", "date"],
    "name": ["naam / omschrijving", "omschrijving", "name / description", "description"],
    "account": ["rekening", "account"],
    "account_name": ["rekening naam", "account name"],
    "counterparty": ["tegenrekening", "counterparty"],
    "code": ["code"],
    "direction": ["af bij", "debit/credit"],
    "amount": ["bedrag (eur)", "bedrag", "amount (eur)", "amount"],
    "currency": ["valuta", "currency"],
    "type": ["mutatiesoort", "transaction type"],
    "notes": ["mededelingen", "notifications"],
    "balance": ["saldo na mutatie", "resulting balance"],
    "tag": ["tag"],
}

REQUIRED = ["date", "name", "account", "direction", "amount"]

OUTGOING = {"af", "debit"}
INCOMING = {"bij", "credit"}


def _normalize(name):
    """'Naam / Omschrijving ' -> 'naam / omschrijving'."""

    return re.sub(r"\s+", " ", str(name)).strip().lower()


def find_columns(columns):
    """
    Map each field in COLUMNS to the column holding it, or None.
    """

    available = {_normalize(column): column for column in columns}

    found = {}

    for field, names in COLUMNS.items():
        found[field] = next(
            (available[name] for name in names if name in available),
            None,
        )

    return found


# Column names only ING uses, so a generic English export with "Date",
# "Description" and "Debit/credit" isn't mistaken for ING.
ING_MARKERS = {"af bij", "name / description", "notifications", "resulting balance"}


def is_ing_export(columns):
    """
    True when the columns look like an ING export: all required fields
    plus at least one column name that is typical for ING.
    """

    found = find_columns(columns)
    names = {_normalize(column) for column in columns}

    return (
        all(found[field] is not None for field in REQUIRED)
        and bool(names & ING_MARKERS)
    )


def _text(df, column):
    if column is None:
        return pd.Series("", index=df.index, dtype=object)

    return df[column].fillna("").astype(str).str.strip()


def parse_ing(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert an ING export (payment or savings account) into Finsight's
    standard transaction format.
    """

    columns = find_columns(df.columns)

    missing = [field for field in REQUIRED if columns[field] is None]

    if missing:
        raise ValueError(
            "ING CSV is missing required columns: " + ", ".join(missing)
        )

    df = df.copy()

    # Dates: 20260910 (payment accounts) or 2026-09-10 (savings).
    df["date"] = parse_dates(df[columns["date"]])

    # Description: the counterparty name, or the notes when it's empty.
    notes = _text(df, columns["notes"])
    description = _text(df, columns["name"])
    description = description.where(description != "", notes)
    df["description"] = description.where(description != "", "Unknown transaction")

    # Mededelingen often holds the useful text ("SALARIS SEPTEMBER",
    # "NS REIZEN"), so the categorizer searches it too.
    df["details"] = notes

    # Amounts have no sign; "Af"/"Debit" means money going out. Rows with
    # an unknown direction keep whatever sign the amount itself has.
    amount = parse_numbers(df[columns["amount"]])
    direction = _text(df, columns["direction"]).str.lower()

    df["amount"] = amount
    df.loc[direction.isin(OUTGOING), "amount"] = -amount.abs()
    df.loc[direction.isin(INCOMING), "amount"] = amount.abs()

    if columns["balance"] is not None:
        df["balance"] = parse_numbers(df[columns["balance"]])
    else:
        df["balance"] = float("nan")

    # Payment accounts are always in euros ("Bedrag (EUR)"); savings
    # exports have a "Valuta" column.
    currency = _text(df, columns["currency"]).str.upper()
    df["currency"] = currency.where(currency != "", "EUR")

    df["transaction_type"] = _text(df, columns["type"])
    df["account"] = _text(df, columns["account"])
    df["counterparty_account"] = _text(df, columns["counterparty"])

    df["fee"] = 0.0
    df["bank"] = "ING"
    df["category"] = "Uncategorized"

    df = df.dropna(subset=["date", "amount"])

    # Oldest first. ING lists newest first; "stable" keeps the order of
    # same-day transactions as ING wrote them (reversed).
    df = df.iloc[::-1].sort_values("date", kind="stable")

    return df[STANDARD_COLUMNS].reset_index(drop=True)
