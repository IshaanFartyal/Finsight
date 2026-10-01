from parsers.bunq import is_bunq_export
from parsers.ing import is_ing_export
from parsers.rabobank import is_rabobank_export


def detect_bank(df):
    """
    Detect bank/export format based on CSV column names.

    Returns:
        "revolut"
        "wise"
        "ing"
        "rabobank"
        "bunq"
        "unknown"
    """

    columns = set(df.columns)

    revolut_columns = {
        "Type",
        "Product",
        "Started Date",
        "Completed Date",
        "Description",
        "Amount",
        "Fee",
        "Currency",
        "State",
        "Balance",
    }

    wise_columns = {
        "ID",
        "Date",
        "Date Time",
        "Amount",
        "Currency",
        "Description",
        "Payment Reference",
        "Running Balance",
        "Exchange From",
        "Exchange To",
        "Exchange Rate",
        "Total Fees",
        "Payer Name",
        "Payee Name",
        "Payee Account Number",
        "Merchant",
        "Card Last Four Digits",
        "Card Holder Full Name",
        "Attachment",
        "Note",
        "Exchange To Amount",
        "Transaction Type",
        "Transaction Details Type",
    }

    if revolut_columns.issubset(columns):
        return "revolut"

    elif wise_columns.issubset(columns):
        return "wise"

    elif is_ing_export(df.columns):
        return "ing"

    elif is_rabobank_export(df.columns):
        return "rabobank"

    elif is_bunq_export(df.columns):
        return "bunq"

    else:
        return "unknown"