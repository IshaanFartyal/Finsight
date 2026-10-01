import io

import pandas as pd

from categorizer import DEFAULT_CATEGORY_RULES
from corrections import empty_corrections
from export import (
    monthly_summary,
    spending_by_category_per_month,
    to_csv_bytes,
    to_excel_bytes,
    transactions_for_export,
)
from flows import default_settings
from pipeline import build_transactions
from tests.helpers import SAMPLE_DATA


def transactions():
    files = [
        (name, (SAMPLE_DATA / name).read_bytes())
        for name in ("multi_account_ing.csv", "multi_account_revolut.csv")
    ]

    df, _, _ = build_transactions(
        files,
        DEFAULT_CATEGORY_RULES,
        default_settings(),
        empty_corrections(),
    )

    return df


def test_export_has_every_transaction_with_readable_columns():
    export = transactions_for_export(transactions())

    assert len(export) == 14
    assert list(export.columns[:6]) == [
        "Date",
        "Description",
        "Details",
        "Category",
        "Type",
        "Amount (EUR)",
    ]
    assert export["Date"].iloc[0] == "2026-09-01"


def test_csv_round_trip():
    data = to_csv_bytes(transactions())

    # Starts with a UTF-8 marker so Excel reads € correctly.
    assert data.startswith(b"\xef\xbb\xbf")

    back = pd.read_csv(io.BytesIO(data), encoding="utf-8-sig")

    assert len(back) == 14
    assert back["Amount (EUR)"].sum() == transactions()["amount"].sum()


def test_excel_has_three_sheets():
    workbook = pd.read_excel(io.BytesIO(to_excel_bytes(transactions())), sheet_name=None)

    assert list(workbook) == ["Transactions", "Monthly summary", "Spending by category"]
    assert len(workbook["Transactions"]) == 14

    summary = workbook["Monthly summary"].iloc[0]

    assert summary["Income"] == 2600.0
    assert round(summary["Expenses"], 2) == 848.06


def test_monthly_summary_savings_rate():
    summary = monthly_summary(transactions()).iloc[0]

    assert round(summary["Savings rate"], 3) == round(1751.94 / 2600, 3)


def test_spending_by_category_per_month():
    table = spending_by_category_per_month(transactions()).set_index("Category")

    assert round(table.loc["Groceries", "2026-09"], 2) == 73.57
