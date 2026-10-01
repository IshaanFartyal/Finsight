import pandas as pd

from flows import (
    EXPENSE,
    INCOME,
    REFUND,
    TRANSFER,
    classify_flows,
    default_settings,
    load_settings,
    normalize_account,
    save_settings,
)


def make_transactions(rows):
    """rows: list of dicts with at least date, description, amount."""

    defaults = {
        "details": "",
        "account": "NL12INGB0123456789",
        "counterparty_account": "",
        "currency": "EUR",
        "bank": "ING",
        "transaction_type": "",
        "fee": 0.0,
        "category": "Other",
        "source": "statement.csv",
    }

    df = pd.DataFrame([{**defaults, **row} for row in rows])
    df["date"] = pd.to_datetime(df["date"])

    return df


def flows_for(rows, settings=None):
    return classify_flows(make_transactions(rows), settings).tolist()


def test_plain_income_and_expense():
    assert flows_for(
        [
            {"date": "2026-09-01", "description": "Employer", "amount": 2500.0, "category": "Income"},
            {"date": "2026-09-02", "description": "Albert Heijn", "amount": -40.0},
        ]
    ) == [INCOME, EXPENSE]


def test_bank_transfer_types():
    assert flows_for(
        [
            {"date": "2026-09-01", "description": "Top-Up by *1234", "amount": 200.0, "transaction_type": "TOPUP", "bank": "Revolut"},
            {"date": "2026-09-01", "description": "Exchanged to USD", "amount": -50.0, "transaction_type": "EXCHANGE", "bank": "Revolut"},
            {"date": "2026-09-01", "description": "Converted EUR", "amount": -30.0, "transaction_type": "CONVERSION", "bank": "Wise"},
        ]
    ) == [TRANSFER, TRANSFER, TRANSFER]


def test_bank_refund_type():
    assert flows_for(
        [
            {"date": "2026-09-01", "description": "Zalando", "amount": 79.95, "transaction_type": "CARD_REFUND"},
        ]
    ) == [REFUND]


def test_own_account_numbers_ignore_spacing_and_case():
    settings = default_settings()
    settings["own_accounts"] = ["nl99 rabo 0123 4567 89"]

    assert flows_for(
        [
            {"date": "2026-09-01", "description": "To savings", "amount": -300.0, "counterparty_account": "NL99RABO0123456789"},
            {"date": "2026-09-02", "description": "Landlord", "amount": -650.0, "counterparty_account": "NL44DUWO0123456789"},
        ],
        settings,
    ) == [TRANSFER, EXPENSE]


def test_own_name():
    settings = default_settings()
    settings["own_names"] = ["J de Vries"]

    assert flows_for(
        [
            {"date": "2026-09-01", "description": "J de Vries", "amount": 500.0},
            {"date": "2026-09-02", "description": "A Jansen", "amount": 20.0},
        ],
        settings,
    ) == [TRANSFER, INCOME]


def test_transfer_keyword_in_details():
    assert flows_for(
        [
            {"date": "2026-09-01", "description": "V12345678", "details": "Naar Oranje Spaarrekening", "amount": -300.0},
        ]
    ) == [TRANSFER]


def test_matching_pair_across_accounts():
    assert flows_for(
        [
            {"date": "2026-09-05", "description": "Wise Europe", "amount": -150.0, "account": "NL12INGB0123456789"},
            {"date": "2026-09-06", "description": "Money received", "amount": 150.0, "account": "Wise EUR", "bank": "Wise"},
        ]
    ) == [TRANSFER, TRANSFER]


def test_no_pair_within_the_same_account():
    # Paying €150 and receiving €150 in the same account is not a
    # transfer between accounts.
    assert flows_for(
        [
            {"date": "2026-09-05", "description": "Concert tickets", "amount": -150.0},
            {"date": "2026-09-06", "description": "Friend pays back", "amount": 150.0},
        ]
    ) == [EXPENSE, INCOME]


def test_no_pair_when_too_far_apart_or_different_currency():
    assert flows_for(
        [
            {"date": "2026-09-01", "description": "Out", "amount": -150.0, "account": "A"},
            {"date": "2026-09-20", "description": "In", "amount": 150.0, "account": "B"},
            {"date": "2026-09-01", "description": "Out USD", "amount": -80.0, "account": "A"},
            {"date": "2026-09-01", "description": "In GBP", "amount": 80.0, "account": "B", "currency": "GBP"},
        ]
    ) == [EXPENSE, INCOME, EXPENSE, INCOME]


def test_each_transaction_pairs_at_most_once():
    # One €100 arrival can only cancel out one €100 departure.
    assert flows_for(
        [
            {"date": "2026-09-01", "description": "Out 1", "amount": -100.0, "account": "A"},
            {"date": "2026-09-02", "description": "Out 2", "amount": -100.0, "account": "A"},
            {"date": "2026-09-02", "description": "In", "amount": 100.0, "account": "B"},
        ]
    ) == [EXPENSE, TRANSFER, TRANSFER]


def test_bank_marked_topup_still_pairs_with_other_side():
    assert flows_for(
        [
            {"date": "2026-09-05", "description": "Revolut Bank UAB", "amount": -200.0},
            {"date": "2026-09-05", "description": "Top-Up by *1234", "amount": 200.0, "transaction_type": "TOPUP", "bank": "Revolut", "account": "Revolut Current EUR"},
        ]
    ) == [TRANSFER, TRANSFER]


def test_money_back_from_a_paid_merchant_is_a_refund():
    assert flows_for(
        [
            {"date": "2026-09-01", "description": "Bol.com", "amount": -54.95},
            {"date": "2026-09-08", "description": "BOL.COM 4401", "amount": 54.95},
        ]
    ) == [EXPENSE, REFUND]


def test_income_category_is_never_a_refund():
    assert flows_for(
        [
            {"date": "2026-09-01", "description": "Employer", "amount": -10.0},
            {"date": "2026-09-02", "description": "Employer", "amount": 2500.0, "category": "Income"},
        ]
    ) == [EXPENSE, INCOME]


def test_normalize_account():
    assert normalize_account(" nl12 INGB 0123-4567 89 ") == "NL12INGB0123456789"


def test_settings_round_trip(tmp_path):
    path = tmp_path / "settings.json"
    settings = {
        "own_accounts": ["NL12INGB0123456789"],
        "own_names": ["J de Vries"],
        "transfer_keywords": ["SPAARREKENING"],
        "exchange_rates": {"USD": 0.92},
    }

    save_settings(settings, path)

    assert load_settings(path) == settings


def test_missing_settings_fall_back_to_defaults(tmp_path):
    assert load_settings(tmp_path / "missing.json") == default_settings()


def test_normalize_merchant_drops_reference_codes():
    from flows import normalize_merchant

    assert normalize_merchant("Spotify P1A2B3") == normalize_merchant("SPOTIFY")
    assert normalize_merchant("ALBERT HEIJN 1234") == "ALBERT HEIJN"
    assert normalize_merchant("BOL.COM 4401") == normalize_merchant("Bol.com")
    # Nothing but a reference: keep it rather than returning nothing.
    assert normalize_merchant("12345") == "12345"
