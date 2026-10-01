"""
From uploaded files to a finished transaction table.

Kept separate from the Streamlit app so it can be tested on its own and
cached as one unit: the app only re-runs it when the files, rules,
settings or corrections change, not on every click.
"""

from pandas.errors import ParserError

from analytics import calculate_monthly_finances
from categorizer import categorize_dataframe
from corrections import apply_corrections
from currency import convert_to_home_currency
from flows import TRANSFER, classify_flows
from statements import combine_statements, parse_statement


def build_transactions(files, category_rules, transfer_settings, corrections):
    """
    files: list of (file_name, file_bytes).

    Returns (df, loaded_files, failed_files):
        df            all transactions, or None if no file could be read
        loaded_files  {file_name: detected bank}
        failed_files  {file_name: reason}

    df.attrs["missing_rates"] lists foreign currencies that have no
    exchange rate yet (those amounts are left unconverted).

    Steps:
        parse each file -> combine and remove duplicates -> categorize
        -> classify income/expense/transfer/refund -> apply the user's
        manual corrections -> convert foreign currencies to euros
    """

    loaded_files = {}
    failed_files = {}
    statements = []

    for file_name, file_bytes in files:
        try:
            bank, parsed = parse_statement(file_bytes)

        except (ValueError, UnicodeDecodeError, ParserError) as error:
            failed_files[file_name] = str(error)
            continue

        loaded_files[file_name] = bank
        statements.append((file_name, parsed))

    if not statements:
        return None, loaded_files, failed_files

    df = combine_statements(statements)

    df["category"] = categorize_dataframe(df, category_rules)
    df["flow"] = classify_flows(df, transfer_settings)

    df = apply_corrections(df, corrections)

    # Transfers aren't spending, so they get their own category,
    # unless the user explicitly chose a category for that transaction.
    explicit_category = df["transaction_id"].map(
        lambda transaction_id: "category"
        in corrections.get("transactions", {}).get(transaction_id, {})
    )

    df.loc[
        (df["flow"] == TRANSFER) & ~explicit_category,
        "category",
    ] = "Transfer"

    # After transfer matching, which compares original-currency amounts.
    df, missing_rates = convert_to_home_currency(
        df,
        transfer_settings.get("exchange_rates", {}),
    )

    df["month"] = df["date"].dt.to_period("M")
    df.attrs["missing_rates"] = missing_rates

    return df, loaded_files, failed_files


def build_monthly_finances(df):
    """Monthly income/expenses/savings with month as text, for charts."""

    monthly = calculate_monthly_finances(df)
    monthly["month"] = monthly["month"].astype(str)

    return monthly
