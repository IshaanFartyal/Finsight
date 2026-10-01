"""
Merchants that still need a category.

Keyword rules catch the big chains, but everyone also pays local shops,
gyms and clubs no general rule knows. Instead of fixing transactions one
by one, the review screen lists each unrecognized merchant once, so a
single choice categorizes all its transactions, now and in future
uploads (saved as a merchant-wide correction).
"""

import pandas as pd

from flows import TRANSFER
from merchants import clean_merchant, normalize_merchant

UNCATEGORIZED = "Other"

REVIEW_COLUMNS = [
    "key",
    "merchant",
    "transactions",
    "total",
    "last_date",
    "example",
]


def _needs_review(df):
    """Transactions that count as income or spending but have no category."""

    is_transfer = df["flow"] == TRANSFER if "flow" in df.columns else False

    return (df["category"] == UNCATEGORIZED) & ~is_transfer


def uncategorized_merchants(df):
    """
    One row per merchant whose transactions are still "Other", most
    frequent first:
        key           merchant key, used for the merchant-wide correction
        merchant      readable name
        transactions  number of transactions
        total         sum of the amounts (negative = money spent)
        last_date     most recent transaction
        example       one original description, as on the statement
    """

    rows = df[_needs_review(df)]

    if rows.empty:
        return pd.DataFrame(columns=REVIEW_COLUMNS)

    rows = rows.assign(_key=rows["description"].apply(normalize_merchant))

    summary = []

    for key, group in rows.groupby("_key"):
        latest = group.sort_values("date").iloc[-1]

        summary.append(
            {
                "key": key,
                "merchant": clean_merchant(latest["description"]),
                "transactions": len(group),
                "total": round(float(group["amount"].sum()), 2),
                "last_date": latest["date"],
                "example": latest["description"],
            }
        )

    return (
        pd.DataFrame(summary, columns=REVIEW_COLUMNS)
        .sort_values(
            ["transactions", "total"],
            ascending=[False, True],
            kind="stable",
        )
        .reset_index(drop=True)
    )


def categorized_share(df):
    """
    Share of income and spending transactions that have a category
    (transfers between your own accounts don't count). 1.0 when there is
    nothing to categorize.
    """

    is_transfer = df["flow"] == TRANSFER if "flow" in df.columns else False
    relevant = df[~is_transfer]

    if relevant.empty:
        return 1.0

    return float((relevant["category"] != UNCATEGORIZED).mean())
