"""
Manual corrections: the user's fixes to a transaction's category or type.

Automatic classification is rule-based, so real statements will produce
some mistakes. A correction can apply to:

- one transaction  ("this €50 Tikkie was a refund"), stored by its
                    transaction_id so it survives re-uploading the file;
- a merchant       ("Revolut Bank UAB is always a transfer"), applied to
                    every transaction from that merchant, now and later.

A correction for a single transaction wins over a merchant correction,
and both win over the automatic rules.

Corrections are saved locally in corrections.json (git-ignored, since it
contains merchant names and transaction details).
"""

import json
from pathlib import Path

import pandas as pd

from flows import normalize_merchant

CORRECTIONS_PATH = Path(__file__).parent / "corrections.json"

FIELDS = ("category", "flow")

SCOPE_TRANSACTION = "transaction"
SCOPE_MERCHANT = "merchant"


def empty_corrections():
    return {"transactions": {}, "merchants": {}}


def load_corrections(path=CORRECTIONS_PATH):
    """Load saved corrections, or none if the file is missing or unreadable."""

    path = Path(path)
    corrections = empty_corrections()

    if not path.exists():
        return corrections

    try:
        with open(path, encoding="utf-8") as corrections_file:
            saved = json.load(corrections_file)

    except (OSError, json.JSONDecodeError):
        return corrections

    for scope in ("transactions", "merchants"):
        entries = saved.get(scope, {})

        if not isinstance(entries, dict):
            continue

        for key, values in entries.items():
            if not isinstance(values, dict):
                continue

            cleaned = {
                field: str(values[field])
                for field in FIELDS
                if values.get(field)
            }

            if cleaned:
                corrections[scope][str(key)] = cleaned

    return corrections


def save_corrections(corrections, path=CORRECTIONS_PATH):
    with open(path, "w", encoding="utf-8") as corrections_file:
        json.dump(corrections, corrections_file, indent=2, ensure_ascii=False)


def add_correction(corrections, transaction, field, value, scope):
    """
    Record a correction (modifies corrections in place).

    transaction: a row with at least "transaction_id" and "description".
    field: "category" or "flow".
    scope: SCOPE_TRANSACTION or SCOPE_MERCHANT.
    """

    if field not in FIELDS:
        raise ValueError(f"Cannot correct field {field!r}")

    if scope == SCOPE_MERCHANT:
        key = normalize_merchant(transaction["description"])
        entries = corrections["merchants"]

        # A newer merchant-wide choice replaces older one-off fixes for
        # the same field on this exact transaction.
        single = corrections["transactions"].get(transaction["transaction_id"], {})
        single.pop(field, None)

        if not single:
            corrections["transactions"].pop(transaction["transaction_id"], None)

    else:
        key = transaction["transaction_id"]
        entries = corrections["transactions"]

    entries.setdefault(key, {})[field] = value

    return corrections


def remove_correction(corrections, scope, key):
    """Remove all corrections for one transaction or merchant."""

    corrections["transactions" if scope == SCOPE_TRANSACTION else "merchants"].pop(key, None)

    return corrections


def apply_corrections(df, corrections):
    """
    Return a copy of df with corrections applied, plus a "corrected"
    column: "" (automatic), "merchant" or "transaction".
    """

    df = df.copy()
    df["corrected"] = ""

    if df.empty:
        return df

    merchant = df["description"].apply(normalize_merchant)

    for merchant_key, values in corrections.get("merchants", {}).items():
        rows = merchant == merchant_key

        for field, value in values.items():
            df.loc[rows, field] = value

        df.loc[rows, "corrected"] = SCOPE_MERCHANT

    if "transaction_id" in df.columns:
        for transaction_id, values in corrections.get("transactions", {}).items():
            rows = df["transaction_id"] == transaction_id

            for field, value in values.items():
                df.loc[rows, field] = value

            df.loc[rows, "corrected"] = SCOPE_TRANSACTION

    return df


def corrections_table(corrections, df=None):
    """
    One row per saved correction, for showing and removing them in the
    app. Transaction corrections are described using df when available.
    """

    rows = []

    for key, values in corrections.get("merchants", {}).items():
        rows.append(
            {
                "scope": SCOPE_MERCHANT,
                "key": key,
                "applies_to": f"All transactions from {key.title()}",
                "category": values.get("category", ""),
                "flow": values.get("flow", ""),
            }
        )

    lookup = {}

    if df is not None and "transaction_id" in df.columns:
        lookup = {
            row["transaction_id"]: (
                f"{row['description']}, "
                f"{pd.Timestamp(row['date']).strftime('%d %b %Y')}, "
                f"€{row['amount']:,.2f}"
            )
            for _, row in df.iterrows()
            if row["transaction_id"] in corrections.get("transactions", {})
        }

    for key, values in corrections.get("transactions", {}).items():
        rows.append(
            {
                "scope": SCOPE_TRANSACTION,
                "key": key,
                "applies_to": lookup.get(key, "A transaction not in the current upload"),
                "category": values.get("category", ""),
                "flow": values.get("flow", ""),
            }
        )

    return pd.DataFrame(
        rows,
        columns=["scope", "key", "applies_to", "category", "flow"],
    )
