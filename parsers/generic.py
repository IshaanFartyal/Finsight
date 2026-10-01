import pandas as pd

from parsers.dates import parse_dates
from parsers.numbers import parse_number as _parse_number
from parsers.schema import STANDARD_COLUMNS


def _find_column(columns, candidates):
    """
    Find a column by checking several common names.
    Matching is case-insensitive.
    """

    normalized = {
        str(column).strip().lower(): column
        for column in columns
    }

    for candidate in candidates:
        if candidate.lower() in normalized:
            return normalized[candidate.lower()]

    return None


def parse_generic(df: pd.DataFrame) -> pd.DataFrame:
    """
    Attempt to interpret an unknown bank CSV.

    The parser only continues if it can identify:
    - a transaction date
    - an amount OR debit/credit columns

    Results are explicitly marked as coming from an
    undetected bank.
    """

    df = df.copy()

    # --------------------------------------------------
    # POSSIBLE COLUMN NAMES
    # --------------------------------------------------

    date_column = _find_column(
        df.columns,
        [
            "date",
            "datum",
            "transaction date",
            "booking date",
            "book date",
            "completed date",
            "started date",
            "value date",
        ]
    )

    description_column = _find_column(
        df.columns,
        [
            "description",
            "omschrijving",
            "name / description",
            "naam / omschrijving",
            "counterparty",
            "merchant",
            "details",
            "mededelingen",
            "memo",
            "reference",
        ]
    )

    amount_column = _find_column(
        df.columns,
        [
            "amount",
            "bedrag",
            "amount (eur)",
            "transaction amount",
            "value",
        ]
    )

    debit_column = _find_column(
        df.columns,
        [
            "debit",
            "withdrawal",
            "debit amount",
        ]
    )

    credit_column = _find_column(
        df.columns,
        [
            "credit",
            "deposit",
            "credit amount",
        ]
    )

    direction_column = _find_column(
        df.columns,
        [
            "af bij",
            "debit/credit",
            "credit/debit",
            "direction",
        ]
    )

    currency_column = _find_column(
        df.columns,
        [
            "currency",
            "valuta",
            "ccy",
        ]
    )

    balance_column = _find_column(
        df.columns,
        [
            "balance",
            "running balance",
            "saldo",
            "saldo na mutatie",
        ]
    )

    account_column = _find_column(
        df.columns,
        [
            "account",
            "account number",
            "rekening",
            "own account",
        ]
    )

    counterparty_account_column = _find_column(
        df.columns,
        [
            "counterparty account",
            "counterparty iban",
            "contra account",
            "tegenrekening",
            "payee account number",
        ]
    )

    type_column = _find_column(
        df.columns,
        [
            "transaction type",
            "type",
            "mutatiesoort",
            "category",
        ]
    )

    # --------------------------------------------------
    # MINIMUM REQUIREMENTS
    # --------------------------------------------------

    if date_column is None:
        raise ValueError(
            "Could not identify a transaction date column."
        )

    if (
        amount_column is None
        and debit_column is None
        and credit_column is None
    ):
        raise ValueError(
            "Could not identify an amount column."
        )

    # --------------------------------------------------
    # DATE
    # --------------------------------------------------

    # Year-first (ISO) dates are never read day-first; see parsers/dates.py
    df["date"] = parse_dates(df[date_column])

    # --------------------------------------------------
    # DESCRIPTION
    # --------------------------------------------------

    if description_column is not None:

        df["description"] = (
            df[description_column]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    else:
        df["description"] = "Unknown transaction"

    df.loc[
        df["description"] == "",
        "description"
    ] = "Unknown transaction"

    # --------------------------------------------------
    # AMOUNT
    # --------------------------------------------------

    if amount_column is not None:

        df["amount"] = (
            df[amount_column]
            .apply(_parse_number)
        )

    else:

        # Some banks use separate debit and credit columns
        if debit_column is not None:
            debit = (
                df[debit_column]
                .apply(_parse_number)
                .fillna(0)
            )
        else:
            debit = 0

        if credit_column is not None:
            credit = (
                df[credit_column]
                .apply(_parse_number)
                .fillna(0)
            )
        else:
            credit = 0

        df["amount"] = credit - debit

    # --------------------------------------------------
    # DEBIT / CREDIT DIRECTION
    # --------------------------------------------------

    if direction_column is not None:

        direction = (
            df[direction_column]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.lower()
        )

        debit_values = {
            "af",
            "debit",
            "d",
            "out",
            "withdrawal",
        }

        credit_values = {
            "bij",
            "credit",
            "c",
            "in",
            "deposit",
        }

        for index in df.index:

            if direction.loc[index] in debit_values:
                df.loc[index, "amount"] = -abs(
                    df.loc[index, "amount"]
                )

            elif direction.loc[index] in credit_values:
                df.loc[index, "amount"] = abs(
                    df.loc[index, "amount"]
                )

    # --------------------------------------------------
    # CURRENCY
    # --------------------------------------------------

    if currency_column is not None:

        df["currency"] = (
            df[currency_column]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    else:
        df["currency"] = "Unknown"

    # --------------------------------------------------
    # BALANCE
    # --------------------------------------------------

    if balance_column is not None:

        df["balance"] = (
            df[balance_column]
            .apply(_parse_number)
        )

    else:
        df["balance"] = pd.NA

    # --------------------------------------------------
    # TRANSACTION TYPE
    # --------------------------------------------------

    if type_column is not None:

        df["transaction_type"] = (
            df[type_column]
            .fillna("")
            .astype(str)
        )

    else:
        df["transaction_type"] = "Unknown"

    # --------------------------------------------------
    # STANDARD FIELDS
    # --------------------------------------------------

    df["details"] = ""

    if account_column is not None:
        df["account"] = (
            df[account_column].fillna("").astype(str).str.strip()
        )
    else:
        df["account"] = ""

    if counterparty_account_column is not None:
        df["counterparty_account"] = (
            df[counterparty_account_column]
            .fillna("")
            .astype(str)
            .str.strip()
        )
    else:
        df["counterparty_account"] = ""

    df["bank"] = "Undetected bank"
    df["fee"] = 0.0
    df["category"] = "Uncategorized"

    # Remove rows where the essential data
    # could not actually be interpreted
    df = df.dropna(
        subset=["date", "amount"]
    )

    if df.empty:
        raise ValueError(
            "No valid transactions could be interpreted."
        )

    return (
        df[STANDARD_COLUMNS]
        .sort_values("date")
        .reset_index(drop=True)
    )