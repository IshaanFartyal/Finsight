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
from flows import (
    EXPENSE,
    INCOME,
    TRANSFER,
    TRANSFER_CATEGORIES,
    classify_flows,
)
from merchants import clean_merchant, normalize_merchant
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

    # Readable merchant names ("SumUp *Bakkerij Jansen" -> "Bakkerij Jansen")
    df["merchant"] = df["description"].apply(clean_merchant)

    df["category"] = categorize_dataframe(df, category_rules)
    df["flow"] = classify_flows(df, transfer_settings)

    df = apply_corrections(df, corrections)

    # A merchant corrected to e.g. "Savings & Investments" becomes a
    # transfer too, unless the user also chose its type explicitly.
    merchants_with_flow = {
        key
        for key, values in corrections.get("merchants", {}).items()
        if "flow" in values
    }

    explicit_flow = df["transaction_id"].map(
        lambda transaction_id: "flow"
        in corrections.get("transactions", {}).get(transaction_id, {})
    ) | df["description"].apply(normalize_merchant).isin(merchants_with_flow)

    df.loc[
        df["category"].isin(TRANSFER_CATEGORIES)
        & df["flow"].isin([INCOME, EXPENSE])
        & ~explicit_flow,
        "flow",
    ] = TRANSFER

    # Transfers aren't spending, so they get their own category, unless
    # the user explicitly chose a category for that transaction, or it
    # already has a transfer category (e.g. Savings & Investments).
    explicit_category = df["transaction_id"].map(
        lambda transaction_id: "category"
        in corrections.get("transactions", {}).get(transaction_id, {})
    )

    df.loc[
        (df["flow"] == TRANSFER)
        & ~explicit_category
        & ~df["category"].isin(TRANSFER_CATEGORIES),
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
