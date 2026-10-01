import pandas as pd

from flows import (
    accounts_to_remember,
    EXPENSE,
    INCOME,
    REFUND,
    TRANSFER,
    classify_flows,
    default_settings,
    is_account_number,
    load_settings,
    normalize_account,
    save_settings,
    suggest_own_accounts,
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


def test_accounts_of_uploaded_statements_are_own_accounts():
    # Money to the savings account is a transfer even when the savings
    # statement doesn't cover that day (no matching pair to find).
    assert flows_for(
        [
            {"date": "2026-08-01", "description": "To savings", "amount": -300.0, "counterparty_account": "NL55RABO0987654321"},
            {"date": "2026-09-30", "description": "Interest", "amount": 4.17, "account": "NL55RABO0987654321"},
            {"date": "2026-09-02", "description": "Landlord", "amount": -650.0, "counterparty_account": "NL44DUWO0123456789"},
        ]
    ) == [TRANSFER, INCOME, EXPENSE]


def test_accounts_of_unrecognized_files_are_not_own_accounts_automatically():
    # The generic parser guesses which column is the user's account, so
    # Finsight asks first (see the suggestions below).
    assert flows_for(
        [
            {"date": "2026-08-01", "description": "To savings", "amount": -300.0, "counterparty_account": "NL55RABO0987654321"},
            {"date": "2026-09-30", "description": "Interest", "amount": 4.17, "account": "NL55RABO0987654321", "bank": "Undetected bank"},
        ]
    ) == [EXPENSE, INCOME]


def test_account_labels_are_not_account_numbers():
    assert is_account_number("NL12 INGB 0123 4567 89")
    assert is_account_number("V12345678")
    assert not is_account_number("Revolut Current EUR")
    assert not is_account_number("Wise EUR")
    assert not is_account_number("")


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
        "not_own_accounts": ["NL20BANK0000000001"],
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


def test_investments_are_transfers_not_spending():
    assert flows_for(
        [
            {"date": "2026-09-01", "description": "DEGIRO storting", "amount": -500.0, "category": "Savings & Investments"},
            {"date": "2026-09-02", "description": "Tikkie pizza", "amount": -12.0, "category": "Payment Requests"},
        ]
    ) == [TRANSFER, EXPENSE]


# ------------------------------------------------------------
# Suggested own accounts
# ------------------------------------------------------------

SAVINGS = "NL55RABO0987654321"
FRIEND = "NL66BANK0111111111"


def suggestions_for(rows, settings=None):
    df = make_transactions(rows)
    df["flow"] = classify_flows(df, settings)

    return suggest_own_accounts(df, settings)


def test_suggests_account_of_an_unrecognized_statement():
    result = suggestions_for(
        [
            {"date": "2026-08-01", "description": "J Jansen", "amount": -300.0, "counterparty_account": SAVINGS},
            {"date": "2026-09-30", "description": "Interest", "amount": 4.17, "account": SAVINGS, "bank": "Undetected bank"},
        ]
    )

    assert result["account"].tolist() == [SAVINGS]
    assert result["reason"].tolist() == [
        "You uploaded a statement that seems to be for this account"
    ]
    assert result["sent"].tolist() == [300.0]
    assert result["transactions"].tolist() == [1]


def test_account_of_a_recognized_statement_needs_no_question():
    result = suggestions_for(
        [
            {"date": "2026-08-01", "description": "J Jansen", "amount": -300.0, "counterparty_account": SAVINGS},
            {"date": "2026-09-30", "description": "Interest", "amount": 4.17, "account": SAVINGS},
        ]
    )

    assert result.empty


def test_suggests_account_with_money_going_both_ways():
    result = suggestions_for(
        [
            {"date": "2026-06-01", "description": "J Jansen", "amount": -300.0, "counterparty_account": SAVINGS},
            {"date": "2026-07-01", "description": "J Jansen", "amount": -300.0, "counterparty_account": SAVINGS},
            {"date": "2026-08-15", "description": "J Jansen", "amount": 150.0, "counterparty_account": SAVINGS},
        ]
    )

    assert result["account"].tolist() == [SAVINGS]
    assert result["reason"].tolist() == ["Money goes both ways"]
    assert result["sent"].tolist() == [600.0]
    assert result["received"].tolist() == [150.0]


def test_one_way_payments_are_not_suggested():
    # A landlord is paid every month, but never pays back.
    result = suggestions_for(
        [
            {"date": f"2026-0{month}-01", "description": "Landlord", "amount": -650.0, "counterparty_account": FRIEND}
            for month in range(1, 7)
        ]
    )

    assert result.empty


def test_too_few_transactions_are_not_suggested():
    result = suggestions_for(
        [
            {"date": "2026-06-01", "description": "Sam", "amount": -20.0, "counterparty_account": FRIEND},
            {"date": "2026-06-20", "description": "Sam", "amount": 20.0, "counterparty_account": FRIEND},
        ]
    )

    assert result.empty


def test_shop_that_refunded_an_order_is_not_suggested():
    result = suggestions_for(
        [
            {"date": "2026-06-01", "description": "Bol.com", "amount": -54.95, "category": "Shopping", "counterparty_account": FRIEND},
            {"date": "2026-06-10", "description": "Bol.com", "amount": -20.00, "category": "Shopping", "counterparty_account": FRIEND},
            {"date": "2026-06-20", "description": "Bol.com", "amount": 54.95, "category": "Shopping", "counterparty_account": FRIEND},
        ]
    )

    assert result.empty


def test_payment_processor_shared_by_many_names_is_not_suggested():
    result = suggestions_for(
        [
            {"date": "2026-06-01", "description": "Bakery via Mollie", "amount": -5.0, "counterparty_account": FRIEND},
            {"date": "2026-06-02", "description": "Bike shop via Mollie", "amount": -80.0, "counterparty_account": FRIEND},
            {"date": "2026-06-03", "description": "Florist via Mollie", "amount": -15.0, "counterparty_account": FRIEND},
            {"date": "2026-06-09", "description": "Bike shop via Mollie", "amount": 80.0, "counterparty_account": FRIEND},
        ]
    )

    assert result.empty


def test_answered_accounts_are_not_suggested_again():
    rows = [
        {"date": "2026-06-01", "description": "J Jansen", "amount": -300.0, "counterparty_account": SAVINGS},
        {"date": "2026-07-01", "description": "J Jansen", "amount": -300.0, "counterparty_account": SAVINGS},
        {"date": "2026-08-15", "description": "J Jansen", "amount": 150.0, "counterparty_account": SAVINGS},
    ]

    declined = default_settings()
    declined["not_own_accounts"] = ["nl55 rabo 0987 6543 21"]

    confirmed = default_settings()
    confirmed["own_accounts"] = [SAVINGS]

    assert suggestions_for(rows, declined).empty
    assert suggestions_for(rows, confirmed).empty


def test_transfers_already_recognized_are_not_suggested():
    # Both halves uploaded and matched as a pair: nothing left to ask.
    result = suggestions_for(
        [
            {"date": "2026-09-10", "description": "J Jansen", "amount": -300.0, "counterparty_account": SAVINGS},
            {"date": "2026-09-10", "description": "J Jansen", "amount": 300.0, "account": SAVINGS, "counterparty_account": "NL12INGB0123456789"},
        ]
    )

    assert result.empty


def test_no_suggestions_without_transactions():
    assert suggest_own_accounts(None).empty


# ------------------------------------------------------------
# Remembering uploaded accounts (opt-in)
# ------------------------------------------------------------

def test_accounts_to_remember_are_the_recognized_statement_accounts():
    df = make_transactions(
        [
            {"date": "2026-09-01", "description": "Shop", "amount": -5.0},
            {"date": "2026-09-02", "description": "Interest", "amount": 4.17, "account": SAVINGS},
            {"date": "2026-09-03", "description": "Coffee", "amount": -3.0, "account": "Revolut Current EUR", "bank": "Revolut"},
            {"date": "2026-09-04", "description": "Other", "amount": -3.0, "account": FRIEND, "bank": "Undetected bank"},
        ]
    )

    assert accounts_to_remember(df, default_settings()) == [
        "NL12INGB0123456789",
        SAVINGS,
    ]


def test_saved_accounts_are_not_offered_again():
    df = make_transactions(
        [{"date": "2026-09-01", "description": "Shop", "amount": -5.0}]
    )

    settings = default_settings()
    settings["own_accounts"] = ["nl12 ingb 0123 4567 89"]

    assert accounts_to_remember(df, settings) == []
    assert accounts_to_remember(None, settings) == []
