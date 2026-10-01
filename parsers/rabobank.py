"""
Rabobank exports (Rabo Online Bankieren > Downloaden transacties > CSV).

Built from Rabobank's documented column list and open-source importers,
not yet verified against a real export: please report anything that
parses wrongly.

The file is comma-separated with 26 columns. What matters here:

- "IBAN/BBAN": your own account. One file can hold several of your
  accounts (payment and savings), each row with its own IBAN.
- "Bedrag": the amount with a sign and a decimal comma (+12,50 / -12,50).
- "Naam tegenpartij": who you paid or who paid you.
- "Omschrijving-1/2/3": one description, cut into three columns.
- "Volgnr": a running number per account, in booking order.

Credit card statements are a different export and are not handled here.
"""

import re

import pandas as pd

from parsers.dates import parse_dates
from parsers.numbers import parse_numbers
from parsers.schema import STANDARD_COLUMNS

# Field -> column name, in lower case.
COLUMNS = {
    "account": "iban/bban",
    "currency": "munt",
    "sequence": "volgnr",
    "date": "datum",
    "amount": "bedrag",
    "balance": "saldo na trn",
    "counterparty": "tegenrekening iban/bban",
    "name": "naam tegenpartij",
    "code": "code",
    "notes_1": "omschrijving-1",
    "notes_2": "omschrijving-2",
    "notes_3": "omschrijving-3",
    "return_reason": "reden retour",
}

REQUIRED = ["account", "date", "amount"]

# Column names only Rabobank uses.
RABOBANK_MARKERS = {"iban/bban", "saldo na trn", "naam tegenpartij"}

# Each description column holds at most this many characters (the
# maximum length of a SEPA payment description); a longer description
# continues in the next column.
NOTES_WIDTH = 140


def _normalize(name):
    return re.sub(r"\s+", " ", str(name)).strip().lower()


def find_columns(columns):
    """Map each field in COLUMNS to the column holding it, or None."""

    available = {_normalize(column): column for column in columns}

    return {field: available.get(name) for field, name in COLUMNS.items()}


def is_rabobank_export(columns):
    found = find_columns(columns)
    names = {_normalize(column) for column in columns}

    return (
        all(found[field] is not None for field in REQUIRED)
        and RABOBANK_MARKERS <= names
    )


def _raw_text(df, column):
    if column is None:
        return pd.Series("", index=df.index, dtype=object)

    return df[column].fillna("").astype(str)


def _text(df, column):
    return _raw_text(df, column).str.strip()


def join_notes(parts):
    """
    Put a description back together from its three columns.

    A column that is completely full was cut off mid-sentence (possibly
    mid-word), so the next one is glued on directly; otherwise the parts
    are separate pieces of text and get a space in between.
    """

    result = ""
    previous = ""

    for part in parts:
        if not part.strip():
            continue

        if result and len(previous) < NOTES_WIDTH:
            result += " "

        result += part
        previous = part

    return re.sub(r"\s+", " ", result).strip()


def parse_rabobank(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert a Rabobank export into Finsight's standard transaction format.
    """

    columns = find_columns(df.columns)

    missing = [COLUMNS[field] for field in REQUIRED if columns[field] is None]

    if missing:
        raise ValueError(
            "Rabobank CSV is missing required columns: " + ", ".join(missing)
        )

    df = df.copy()

    # Dates: 2026-09-10
    df["date"] = parse_dates(df[columns["date"]])

    notes = pd.Series(
        [
            join_notes(parts)
            for parts in zip(
                _raw_text(df, columns["notes_1"]),
                _raw_text(df, columns["notes_2"]),
                _raw_text(df, columns["notes_3"]),
            )
        ],
        index=df.index,
        dtype=object,
    )

    # A returned direct debit says why in its own column.
    return_reason = _text(df, columns["return_reason"])
    notes = (notes + " " + return_reason).str.strip()

    # Description: the counterparty, or the notes when there is none
    # (interest, bank costs).
    description = _text(df, columns["name"])
    description = description.where(description != "", notes)
    df["description"] = description.where(description != "", "Unknown transaction")

    # The notes often hold the useful text ("Salaris september"), so the
    # categorizer searches them too.
    df["details"] = notes

    # Signed, with a decimal comma: +2150,00 / -34,82
    df["amount"] = parse_numbers(df[columns["amount"]])

    if columns["balance"] is not None:
        df["balance"] = parse_numbers(df[columns["balance"]])
    else:
        df["balance"] = float("nan")

    currency = _text(df, columns["currency"]).str.upper()
    df["currency"] = currency.where(currency != "", "EUR")

    df["account"] = _text(df, columns["account"])
    df["counterparty_account"] = _text(df, columns["counterparty"])

    # Rabobank's short booking code: "ba" card payment, "id" iDEAL,
    # "ei" direct debit, ...
    df["transaction_type"] = _text(df, columns["code"])

    df["fee"] = 0.0
    df["bank"] = "Rabobank"
    df["category"] = "Uncategorized"

    df = df.dropna(subset=["date", "amount"])

    # Oldest first; same-day transactions in booking order per account.
    df["_sequence"] = pd.to_numeric(
        _text(df, columns["sequence"]), errors="coerce"
    )
    df = df.sort_values(["date", "account", "_sequence"], kind="stable")

    return df[STANDARD_COLUMNS].reset_index(drop=True)
