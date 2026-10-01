"""
Convert foreign-currency transactions to euros.

Revolut and Wise users often hold several currencies. Without conversion,
$50 and €50 would simply be added up as 100.

Exchange rates are set by the user in Settings, so Finsight never needs a
network connection. Conversion runs after transfer matching (which
compares amounts in their original currency) and keeps the original
amount and currency next to the converted one.
"""

import pandas as pd

HOME_CURRENCY = "EUR"

# Values that mean "currency not stated": treated as home currency.
UNSTATED = {"", "UNKNOWN", "NAN", "NONE"}


def _currency(df):
    return df["currency"].fillna("").astype(str).str.strip().str.upper()


def foreign_currencies(df):
    """Currencies other than the home currency that appear in df."""

    currency = _currency(df)

    return sorted(
        set(currency) - UNSTATED - {HOME_CURRENCY}
    )


def clean_rates(rates):
    """Keep only positive numeric rates, keyed by upper-case currency."""

    cleaned = {}

    for currency, rate in (rates or {}).items():
        try:
            rate = float(rate)
        except (TypeError, ValueError):
            continue

        if rate > 0:
            cleaned[str(currency).strip().upper()] = rate

    return cleaned


def convert_to_home_currency(df, rates):
    """
    Return (converted_df, missing_currencies).

    rates: {"USD": 0.92} meaning 1 USD = 0.92 EUR.

    Converted rows get amount and fee in euros and currency "EUR".
    Every row keeps "original_amount" and "original_currency".
    Currencies without a rate are left unconverted and returned in
    missing_currencies, so the app can ask for a rate.
    """

    df = df.copy()
    rates = clean_rates(rates)
    currency = _currency(df)

    df["original_amount"] = df["amount"]
    df["original_currency"] = currency.where(~currency.isin(UNSTATED), HOME_CURRENCY)

    missing = []

    for code in foreign_currencies(df):
        rows = currency == code

        if code not in rates:
            missing.append(code)
            continue

        df.loc[rows, "amount"] = (df.loc[rows, "amount"] * rates[code]).round(2)

        if "fee" in df.columns:
            df.loc[rows, "fee"] = (
                pd.to_numeric(df.loc[rows, "fee"], errors="coerce").fillna(0)
                * rates[code]
            ).round(2)

        df.loc[rows, "currency"] = HOME_CURRENCY

    return df, missing
