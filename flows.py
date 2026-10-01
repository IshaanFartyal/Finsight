"""
Classify every transaction as income, expense, transfer or refund.

Without this, every positive amount counts as income and every negative
amount as an expense. Moving money to your own savings account or between
two banks would then look like spending, and a refund would look like
salary.

Classification runs in order; later steps only change transactions
that earlier steps left as plain income/expense:

1. Bank signals    the bank itself marks top-ups, currency exchanges
                   and refunds; money to your own investment or savings
                   accounts (category "Savings & Investments").
2. Own accounts    money sent to or received from one of the user's
                   own accounts: the accounts of the uploaded statements
                   (Finsight asks the user to upload only their own),
                   plus the account numbers listed in Settings.
                   Other accounts that look like the user's own are
                   only suggested (suggest_own_accounts).
3. Own names       payments to/from the account holder's own name.
4. Keywords        user-editable transfer keywords (e.g. SPAARREKENING).
5. Matching pairs  across uploaded statements: money leaving one account
                   and the same amount arriving in another within a few
                   days. (Steps 1-4 transfers can also be matched here,
                   so both halves of a transfer are recognized.)
6. Refunds         money back from a merchant the user has also paid.
"""

import json
import re
from pathlib import Path

import pandas as pd

from merchants import normalize_merchant as _normalize_merchant

INCOME = "income"
EXPENSE = "expense"
TRANSFER = "transfer"
REFUND = "refund"

# Local, per-user settings. Contains IBANs and names, so it is git-ignored.
SETTINGS_PATH = Path(__file__).parent / "settings.json"

DEFAULT_TRANSFER_SETTINGS = {
    # IBANs/account numbers that belong to the user.
    "own_accounts": [],
    # Suggested accounts the user said are not theirs: not asked again.
    "not_own_accounts": [],
    # Names the user's own accounts are held under.
    "own_names": [],
    # Text that marks a transfer between the user's own accounts.
    "transfer_keywords": [
        "SPAARREKENING",
        "EIGEN REKENING",
    ],
    # Exchange rates to euros, e.g. {"USD": 0.92} for 1 USD = €0.92.
    # Used by currency.py; stored here so all settings share one file.
    "exchange_rates": {},
}

# Bank transaction types that always mean money moving between the
# user's own accounts or currencies. Revolut: TOPUP, EXCHANGE.
# Wise: CONVERSION, MONEY_ADDED.
TRANSFER_TYPES = {
    "TOPUP",
    "EXCHANGE",
    "CONVERSION",
    "MONEY_ADDED",
}

# Bank transaction types that mean a refund (Revolut).
REFUND_TYPES = {
    "REFUND",
    "CARD_REFUND",
}

# Categories that are always money moving to or from your own accounts
# (e.g. a broker like DEGIRO), so never income or spending.
TRANSFER_CATEGORIES = {
    "Savings & Investments",
}

# How many days apart the two halves of a transfer may be booked.
TRANSFER_MATCH_DAYS = 3


# ============================================================
# SETTINGS
# ============================================================

def default_settings():
    return {
        key: dict(values) if isinstance(values, dict) else list(values)
        for key, values in DEFAULT_TRANSFER_SETTINGS.items()
    }


def load_settings(path=SETTINGS_PATH):
    """Load saved settings, falling back to the defaults."""

    path = Path(path)
    settings = default_settings()

    if not path.exists():
        return settings

    try:
        with open(path, encoding="utf-8") as settings_file:
            saved = json.load(settings_file)

    except (OSError, json.JSONDecodeError):
        return settings

    for key, default in settings.items():
        value = saved.get(key)

        if isinstance(default, list) and isinstance(value, list):
            settings[key] = [str(item) for item in value]

        elif isinstance(default, dict) and isinstance(value, dict):
            settings[key] = {str(name): item for name, item in value.items()}

    return settings


def save_settings(settings, path=SETTINGS_PATH):
    with open(path, "w", encoding="utf-8") as settings_file:
        json.dump(settings, settings_file, indent=2, ensure_ascii=False)


# ============================================================
# HELPERS
# ============================================================

def normalize_account(value):
    """'NL12 INGB 0123 4567 89' and 'nl12ingb0123456789' are the same."""

    return re.sub(r"[^A-Z0-9]", "", str(value).upper())


def is_account_number(value):
    """
    True for an IBAN or account number ("NL12INGB0123456789",
    "V12345678"), False for a label like "Revolut Current EUR".
    """

    value = normalize_account(value)

    return len(value) >= 6 and sum(character.isdigit() for character in value) >= 4


# The "bank" the generic parser gives to files it doesn't recognize.
UNDETECTED_BANK = "Undetected bank"


def statement_accounts(df, recognized=True):
    """
    The account numbers the uploaded statements belong to, normalized.

    recognized=True:  statements from a bank Finsight knows, where it is
                      certain which column holds the user's own account.
    recognized=False: files read by the generic parser, where "Account"
                      is a guess and could be the other party's.
    """

    accounts = _column(df, "account")
    known_bank = _column(df, "bank") != UNDETECTED_BANK

    return {
        normalize_account(account)
        for account in accounts[known_bank == recognized].unique()
        if is_account_number(account)
    }


def accounts_to_remember(df, settings):
    """
    Accounts of recognized statements that are not in the user's saved
    list of own accounts yet, as written in the statement. These are
    what "Remember these accounts" in Settings adds to that list.
    """

    if df is None or df.empty:
        return []

    saved = {
        normalize_account(account)
        for account in settings.get("own_accounts", [])
    }

    recognized = statement_accounts(df)

    remember = []

    for account in _column(df, "account").str.strip().unique():
        key = normalize_account(account)

        if key in recognized and key not in saved:
            remember.append(account)
            saved.add(key)

    return sorted(remember)


def _contains_any(text, phrases):
    """Case-insensitive whole-phrase search."""

    phrases = [phrase.strip().upper() for phrase in phrases if phrase.strip()]

    if not phrases:
        return pd.Series(False, index=text.index)

    pattern = "|".join(
        r"(?<![A-Z0-9])" + re.escape(phrase) + r"(?![A-Z0-9])"
        for phrase in phrases
    )

    return text.str.upper().str.contains(pattern, regex=True)


def _column(df, name):
    if name in df.columns:
        return df[name].fillna("").astype(str)

    return pd.Series("", index=df.index)


def account_key(df):
    """
    Identify which account each transaction belongs to.

    Uses the account number/name when the bank provides one, otherwise
    the file it came from.
    """

    account = _column(df, "account").str.strip()
    fallback = _column(df, "source")

    key = account.where(account != "", fallback)

    return _column(df, "bank") + "|" + key


# Defined in merchants.py; imported here so existing code that uses
# flows.normalize_merchant keeps working.
normalize_merchant = _normalize_merchant


# ============================================================
# SUGGESTIONS
# ============================================================

# How many transactions with money going both ways before Finsight asks
# whether an account is the user's own.
SUGGESTION_MIN_TRANSACTIONS = 3

# An own account is held under one name (or two: "J Jansen" and
# "J. Jansen e/o"). An account many names share is a payment processor.
SUGGESTION_MAX_NAMES = 2

# Categories that say nothing about what a payment was for.
UNCATEGORIZED = {"", "Other", "Uncategorized", "Transfer"}

REASON_UPLOADED = "You uploaded a statement that seems to be for this account"
REASON_BOTH_WAYS = "Money goes both ways"

SUGGESTION_COLUMNS = [
    "account",
    "name",
    "transactions",
    "sent",
    "received",
    "reason",
]


def suggest_own_accounts(df, settings=None, min_transactions=SUGGESTION_MIN_TRANSACTIONS):
    """
    Accounts that might be the user's own, for the user to confirm.

    Nothing is treated as a transfer because of this list: it only
    feeds the question "is this account yours?" in Settings.

    An account is suggested when money was sent to or received from it,
    those transactions are not transfers yet, and either:

    - a statement for that account was uploaded, but from a bank
      Finsight doesn't recognize, so it isn't sure which column holds
      the user's own account (recognized statements count as the
      user's own without asking), or
    - money went both ways at least min_transactions times in total
      (typical for a savings account; also for a friend, which is why
      the user decides). Shops are left out: accounts whose payments
      mostly have a spending category (a webshop that refunded an
      order) or that many different names share (a payment processor).

    Accounts already listed as the user's own, or declined before, are
    left out. Returns a DataFrame with SUGGESTION_COLUMNS.
    """

    if settings is None:
        settings = default_settings()

    empty = pd.DataFrame(columns=SUGGESTION_COLUMNS)

    if df is None or df.empty or "counterparty_account" not in df.columns:
        return empty

    answered = {
        normalize_account(account)
        for key in ("own_accounts", "not_own_accounts")
        for account in settings.get(key, [])
    }

    # Accounts of recognized statements are the user's own already;
    # only accounts from unrecognized files still need the question.
    uploaded = statement_accounts(df, recognized=False)

    rows = pd.DataFrame(
        {
            "shown": _column(df, "counterparty_account").str.strip(),
            "name": _column(df, "description").str.strip(),
            "amount": df["amount"],
            "flow": _column(df, "flow"),
            "category": _column(df, "category"),
        }
    )

    rows["key"] = rows["shown"].apply(normalize_account)

    rows = rows[
        rows["shown"].apply(is_account_number)
        & ~rows["key"].isin(answered)
        & (rows["flow"] != TRANSFER)
    ]

    suggestions = []

    for key, group in rows.groupby("key", sort=False):
        sent = float(-group.loc[group["amount"] < 0, "amount"].sum())
        received = float(group.loc[group["amount"] > 0, "amount"].sum())

        if key in uploaded:
            reason = REASON_UPLOADED

        elif (
            sent > 0
            and received > 0
            and len(group) >= min_transactions
            and group["name"].apply(normalize_merchant).nunique() <= SUGGESTION_MAX_NAMES
            and (group["category"].isin(UNCATEGORIZED)).mean() >= 0.5
        ):
            reason = REASON_BOTH_WAYS

        else:
            continue

        suggestions.append(
            {
                "account": group["shown"].mode().iloc[0],
                "name": group["name"].mode().iloc[0],
                "transactions": len(group),
                "sent": round(sent, 2),
                "received": round(received, 2),
                "reason": reason,
            }
        )

    if not suggestions:
        return empty

    result = pd.DataFrame(suggestions, columns=SUGGESTION_COLUMNS)

    # Uploaded statements first (the strongest sign), then the busiest.
    result["_uploaded"] = result["reason"] == REASON_UPLOADED

    return (
        result.sort_values(
            ["_uploaded", "transactions", "account"],
            ascending=[False, False, True],
            kind="stable",
        )
        .drop(columns="_uploaded")
        .reset_index(drop=True)
    )


# ============================================================
# CLASSIFICATION
# ============================================================

def match_transfer_pairs(df, open_mask, max_days=TRANSFER_MATCH_DAYS):
    """
    Find money leaving one account and the same amount arriving in a
    different account within max_days. Returns the index labels of both
    halves of every matched pair.

    Each transaction is used in at most one pair, and the closest dates
    are matched first.
    """

    candidates = df[open_mask].copy()
    candidates["_key"] = account_key(candidates)
    candidates["_currency"] = _column(candidates, "currency").str.upper()
    candidates["_cents"] = (candidates["amount"].abs() * 100).round().astype(int)

    fields = ["_key", "_currency", "_cents", "date"]

    outgoing = candidates.loc[candidates["amount"] < 0, fields]
    incoming = candidates.loc[candidates["amount"] > 0, fields]

    # Pair every outgoing transaction with every incoming one of the same
    # amount and currency in one step, instead of looping row by row.
    # Equal amounts are rare, so this stays small.
    pairs = outgoing.reset_index(names="out_index").merge(
        incoming.reset_index(names="in_index"),
        on=["_cents", "_currency"],
        suffixes=("_out", "_in"),
    )

    pairs["days"] = (pairs["date_in"] - pairs["date_out"]).abs().dt.days

    pairs = pairs[
        (pairs["_key_out"] != pairs["_key_in"])
        & (pairs["days"] <= max_days)
    ].sort_values(["days", "out_index", "in_index"], kind="stable")

    matched = set()

    for out_index, in_index in zip(pairs["out_index"], pairs["in_index"]):
        if out_index in matched or in_index in matched:
            continue

        matched.add(out_index)
        matched.add(in_index)

    return matched


def classify_flows(df, settings=None):
    """
    Return a Series with "income", "expense", "transfer" or "refund"
    for every transaction in df.
    """

    if settings is None:
        settings = default_settings()

    amount = df["amount"]

    flow = pd.Series(
        [INCOME if value > 0 else EXPENSE for value in amount],
        index=df.index,
        dtype=object,
    )

    def still_open():
        return flow.isin([INCOME, EXPENSE])

    transaction_type = _column(df, "transaction_type").str.strip().str.upper()
    text = _column(df, "description") + " " + _column(df, "details")

    # 1. Bank signals
    flow[transaction_type.isin(TRANSFER_TYPES)] = TRANSFER
    flow[still_open() & transaction_type.isin(REFUND_TYPES) & (amount > 0)] = REFUND

    # ...and categories that are always transfers (investments, savings)
    flow[still_open() & _column(df, "category").isin(TRANSFER_CATEGORIES)] = TRANSFER

    # 2. Own accounts
    own_accounts = {
        normalize_account(account)
        for account in settings.get("own_accounts", [])
        if normalize_account(account)
    }

    # ...plus the accounts the uploaded statements belong to. With a
    # payment and a savings account uploaded, money moved between them
    # is a transfer even if the other half falls outside the export.
    own_accounts |= statement_accounts(df)

    if own_accounts:
        counterparty = _column(df, "counterparty_account").apply(normalize_account)
        flow[still_open() & counterparty.isin(own_accounts)] = TRANSFER

    # 3. Own names
    own_names = settings.get("own_names", [])
    flow[still_open() & _contains_any(_column(df, "description"), own_names)] = TRANSFER

    # 4. Transfer keywords
    keywords = settings.get("transfer_keywords", [])
    flow[still_open() & _contains_any(text, keywords)] = TRANSFER

    # 5. Matching pairs across accounts. Transactions already marked as
    # transfers take part too, so the €200 leaving ING still pairs with
    # the Revolut top-up that the bank itself marked as a transfer.
    if "date" in df.columns and df["date"].notna().any():
        pair_candidates = flow.isin([INCOME, EXPENSE, TRANSFER])

        for index in match_transfer_pairs(df, pair_candidates):
            flow[index] = TRANSFER

    # 6. Refunds: money back from a merchant the user also paid.
    # Income-like descriptions (salary etc.) are never refunds.
    merchant = _column(df, "description").apply(normalize_merchant)
    paid_merchants = set(merchant[flow == EXPENSE]) - {""}

    is_income_category = _column(df, "category") == "Income"

    flow[
        (flow == INCOME)
        & merchant.isin(paid_merchants)
        & ~is_income_category
    ] = REFUND

    return flow
