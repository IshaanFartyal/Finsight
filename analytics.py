"""
Financial metrics.

When a "flow" column is present (see flows.py):
- income   = transactions classified as income
- expenses = expenses minus refunds, plus fees
- transfers between the user's own accounts are left out of both

Without a "flow" column, positive amounts count as income and negative
amounts as expenses.
"""

import pandas as pd

from flows import EXPENSE, INCOME, REFUND, TRANSFER

FEES_CATEGORY = "Fees"


def _flow(df):
    if "flow" in df.columns:
        return df["flow"]

    return df["amount"].apply(lambda value: INCOME if value > 0 else EXPENSE)


def _fees(df):
    if "fee" not in df.columns:
        return 0.0

    return float(pd.to_numeric(df["fee"], errors="coerce").fillna(0).abs().sum())


def calculate_summary(df):
    """
    Calculate basic financial summary metrics.

    Returns:
        income
        expenses      (net of refunds, including fees)
        savings
        savings_rate
        refunds
        fees
        transfers_in  (money arriving from your own accounts)
        transfers_out (money sent to your own accounts)
    """

    flow = _flow(df)
    amount = df["amount"]

    income = float(amount[flow == INCOME].sum())
    spent = float(abs(amount[flow == EXPENSE].sum()))
    refunds = float(amount[flow == REFUND].sum())
    fees = _fees(df)

    expenses = spent - refunds + fees
    savings = income - expenses

    if income > 0:
        savings_rate = savings / income
    else:
        savings_rate = 0

    transfers = amount[flow == TRANSFER]

    return {
        "income": income,
        "expenses": expenses,
        "savings": savings,
        "savings_rate": savings_rate,
        "refunds": refunds,
        "fees": fees,
        "transfers_in": float(transfers[transfers > 0].sum()),
        "transfers_out": float(abs(transfers[transfers < 0].sum())),
    }


def calculate_spending_by_category(df):
    """
    Calculate net spending per category.

    Refunds reduce the category they belong to (a refund from Albert
    Heijn lowers Groceries). Fees appear as their own category.
    """

    flow = _flow(df)

    spending = (
        -df.loc[flow.isin([EXPENSE, REFUND]), "amount"]
        .groupby(df.loc[flow.isin([EXPENSE, REFUND]), "category"])
        .sum()
    )

    fees = _fees(df)

    if fees > 0:
        spending.loc[FEES_CATEGORY] = spending.get(FEES_CATEGORY, 0) + fees

    spending = spending[spending > 0]
    spending.name = "amount"

    return spending.sort_values(ascending=False)


def calculate_monthly_spending(df):
    """
    Calculate total spending per month (net of refunds, including fees).
    """

    return calculate_monthly_finances(df).set_index("month")["expenses"]


def calculate_monthly_finances(df):
    """
    Income, expenses and savings for every month in df.

    Requires a "month" column.
    """

    rows = []

    for month, month_df in df.groupby("month", sort=True):
        summary = calculate_summary(month_df)

        rows.append(
            {
                "month": month,
                "income": summary["income"],
                "expenses": summary["expenses"],
                "savings": summary["savings"],
            }
        )

    return pd.DataFrame(
        rows,
        columns=["month", "income", "expenses", "savings"],
    )
