"""
Export transactions: your categorized, corrected data, to take anywhere.
"""

import io

import pandas as pd

from analytics import calculate_monthly_finances, calculate_spending_by_category

EXPORT_COLUMNS = {
    "date": "Date",
    "description": "Description",
    "details": "Details",
    "category": "Category",
    "flow": "Type",
    "amount": "Amount (EUR)",
    "original_amount": "Original amount",
    "original_currency": "Original currency",
    "fee": "Fee (EUR)",
    "bank": "Bank",
    "account": "Account",
    "corrected": "Corrected",
}


def transactions_for_export(df):
    """The transaction table with readable column names, oldest first."""

    columns = [column for column in EXPORT_COLUMNS if column in df.columns]

    export = (
        df.sort_values("date", kind="stable")[columns]
        .rename(columns=EXPORT_COLUMNS)
        .reset_index(drop=True)
    )

    export["Date"] = pd.to_datetime(export["Date"]).dt.strftime("%Y-%m-%d")

    return export


def to_csv_bytes(df):
    """
    CSV with a UTF-8 marker, so Excel shows € and accented names
    correctly when opening it directly.
    """

    return transactions_for_export(df).to_csv(index=False).encode("utf-8-sig")


def monthly_summary(df):
    """Income, expenses, savings and savings rate per month."""

    summary = calculate_monthly_finances(df)

    summary["savings_rate"] = [
        savings / income if income > 0 else None
        for savings, income in zip(summary["savings"], summary["income"])
    ]

    summary["month"] = summary["month"].astype(str)

    return summary.rename(
        columns={
            "month": "Month",
            "income": "Income",
            "expenses": "Expenses",
            "savings": "Savings",
            "savings_rate": "Savings rate",
        }
    )


def spending_by_category_per_month(df):
    """Categories as rows, months as columns."""

    table = pd.DataFrame(
        {
            str(month): calculate_spending_by_category(df[df["month"] == month])
            for month in sorted(df["month"].dropna().unique())
        }
    ).fillna(0.0)

    table.index.name = "Category"

    return table.reset_index()


def excel_available():
    """Excel export needs the openpyxl package (in requirements.txt)."""

    try:
        import openpyxl  # noqa: F401
    except ImportError:
        return False

    return True


def to_excel_bytes(df):
    """Excel workbook: Transactions, Monthly summary, Spending by category."""

    buffer = io.BytesIO()

    sheets = {
        "Transactions": transactions_for_export(df),
        "Monthly summary": monthly_summary(df),
        "Spending by category": spending_by_category_per_month(df),
    }

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for name, table in sheets.items():
            table.to_excel(writer, sheet_name=name, index=False)

            sheet = writer.sheets[name]

            # Readable column widths
            for column_cells in sheet.columns:
                width = max(
                    len(str(cell.value)) if cell.value is not None else 0
                    for cell in column_cells
                )
                sheet.column_dimensions[column_cells[0].column_letter].width = min(
                    max(width + 2, 10), 50
                )

            sheet.freeze_panes = "A2"

    return buffer.getvalue()
