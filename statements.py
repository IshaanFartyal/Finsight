"""
Turn one or more uploaded bank statements into a single transaction table.
"""

import hashlib
import io

import pandas as pd

from parsers.detector import detect_bank
from parsers.generic import parse_generic
from parsers.ing import parse_ing
from parsers.loader import load_bank_csv
from parsers.revolut import parse_revolut
from parsers.wise import parse_wise

PARSERS = {
    "revolut": parse_revolut,
    "wise": parse_wise,
    "ing": parse_ing,
}

# Columns that identify the same transaction appearing in two exports.
DUPLICATE_KEY = [
    "date",
    "description",
    "amount",
    "currency",
    "bank",
    "account",
    "balance",
]


def parse_statement(file_bytes):
    """
    Detect the bank and parse one CSV file.

    Returns (bank, transactions). bank is "unknown" when the generic
    parser was used.
    """

    raw_df = load_bank_csv(io.BytesIO(file_bytes))

    bank = detect_bank(raw_df)
    parser = PARSERS.get(bank, parse_generic)

    return bank, parser(raw_df)


def combine_statements(statements):
    """
    Combine parsed statements into one table.

    statements: list of (source_name, transactions DataFrame).

    Adds a "source" column with the file each transaction came from, and
    a "transaction_id" that stays the same when the same transaction is
    uploaded again later (used to remember manual corrections).

    If two files contain the same transaction (e.g. overlapping exports
    from the same account) it is kept once. Identical transactions
    within one file (two €3.50 coffees on the same day) are all kept.
    """

    if not statements:
        return pd.DataFrame()

    frames = []

    for source, df in statements:
        df = df.copy()
        df["source"] = source

        key = df[DUPLICATE_KEY[0]].astype(str)

        for column in DUPLICATE_KEY[1:]:
            key = key + "|" + df[column].astype(str)

        # 1st, 2nd, 3rd... occurrence of this exact transaction
        # within this file.
        df["_occurrence"] = key.groupby(key).cumcount()
        df["_key"] = key

        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)

    combined = combined.drop_duplicates(
        subset=["_key", "_occurrence"],
        keep="first",
    )

    # The ID is based on what the transaction is (date, amount, account,
    # description...), not on which file it came from.
    combined["transaction_id"] = [
        hashlib.sha1(f"{key}|{occurrence}".encode("utf-8")).hexdigest()[:16]
        for key, occurrence in zip(combined["_key"], combined["_occurrence"])
    ]

    return (
        combined.drop(columns=["_key", "_occurrence"])
        .sort_values("date", kind="stable")
        .reset_index(drop=True)
    )
