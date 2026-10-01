# ING Bank Statement currently unverified. From ING bank statement template available from website so should be right, but not verified. Bear in mind.

import pandas as pd

from parsers.dates import parse_dates
from parsers.schema import STANDARD_COLUMNS


def parse_ing(df: pd.DataFrame) -> pd.DataFrame:
    """
    Parse an ING Netherlands EUR CSV export and convert it into
    FinSight's standard transaction format.

    Expected columns:
    Datum
    Naam / Omschrijving
    Rekening
    Tegenrekening
    Code
    Af Bij
    Bedrag (EUR)
    Mutatiesoort
    Mededelingen
    Saldo na mutatie
    Tag
    """

    required_columns = {
        "Datum",
        "Naam / Omschrijving",
        "Rekening",
        "Tegenrekening",
        "Code",
        "Af Bij",
        "Bedrag (EUR)",
        "Mutatiesoort",
        "Mededelingen",
        "Saldo na mutatie",
        "Tag",
    }

    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"ING CSV is missing required columns: {missing_columns}"
        )

    df = df.copy()

    # ----------------------------
    # DATE
    # ING format: YYYYMMDD
    # ----------------------------

    df["date"] = parse_dates(df["Datum"])

    # ----------------------------
    # DESCRIPTION
    # ----------------------------

    df["description"] = (
        df["Naam / Omschrijving"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    # Use Mededelingen if description is empty
    messages = (
        df["Mededelingen"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    empty_description = df["description"] == ""

    df.loc[
        empty_description,
        "description"
    ] = messages[empty_description]

    df.loc[
        df["description"] == "",
        "description"
    ] = "Unknown transaction"

    # Mededelingen often holds the useful text
    # (e.g. "SALARY SEPTEMBER", "NS REIZEN"), so keep it
    # for the categorizer.
    df["details"] = messages

    # ----------------------------
    # AMOUNT
    # Dutch decimal comma -> decimal point
    # ----------------------------

    amount = (
        df["Bedrag (EUR)"]
        .fillna("")
        .astype(str)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.strip()
    )

    amount = pd.to_numeric(
        amount,
        errors="coerce"
    )

    direction = (
        df["Af Bij"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )

    df["amount"] = amount.abs()

    # "Af" = money going out
    df.loc[
        direction == "af",
        "amount"
    ] *= -1

    # "Bij" = money coming in
    df.loc[
        direction == "bij",
        "amount"
    ] = df.loc[
        direction == "bij",
        "amount"
    ].abs()

    # ----------------------------
    # BALANCE
    # ----------------------------

    balance = (
        df["Saldo na mutatie"]
        .fillna("")
        .astype(str)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.strip()
    )

    df["balance"] = pd.to_numeric(
        balance,
        errors="coerce"
    )

    # ----------------------------
    # STANDARD FIELDS
    # ----------------------------

    df["currency"] = "EUR"

    df["transaction_type"] = (
        df["Mutatiesoort"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df["account"] = (
        df["Rekening"].fillna("").astype(str).str.strip()
    )

    df["counterparty_account"] = (
        df["Tegenrekening"].fillna("").astype(str).str.strip()
    )

    df["fee"] = 0.0
    df["bank"] = "ING"
    df["category"] = "Uncategorized"

    # Remove invalid rows
    df = df.dropna(
        subset=["date", "amount"]
    )

    # Sort oldest -> newest
    df = df.sort_values("date")

    return df[STANDARD_COLUMNS].reset_index(drop=True)