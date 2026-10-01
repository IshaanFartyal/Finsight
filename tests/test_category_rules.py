"""
The default category rules, based on the General Category Rules sheet.
"""

import pytest

from categorizer import DEFAULT_CATEGORY_RULES, categorize_transaction

# One example per keyword in the sheet (with a reference number added,
# as on real statements). Sheet names that differ in Finsight:
#   Dining & Coffee -> Restaurants, Salary / Income -> Income,
#   Fees & Charges -> Fees, Transfers (Tikkie) -> Payment Requests,
#   Savings / Investments -> Savings & Investments,
#   Tuition / Education -> Education.
SHEET_EXAMPLES = [
    ("UBER EATS PAYMENT 1234", "Restaurants"),
    ("ISSUED BY NS PAYMENT 1234", "Transport"),
    ("NEDERLANDSE SPOORWEGEN PAYMENT 1234", "Transport"),
    ("ALBERT HEIJN PAYMENT 1234", "Groceries"),
    ("AH TO GO PAYMENT 1234", "Groceries"),
    ("JUMBO PAYMENT 1234", "Groceries"),
    ("LIDL PAYMENT 1234", "Groceries"),
    ("ALDI PAYMENT 1234", "Groceries"),
    ("DIRK VAN DEN BROEK PAYMENT 1234", "Groceries"),
    ("PLUS SUPERMARKT PAYMENT 1234", "Groceries"),
    ("SPAR PAYMENT 1234", "Groceries"),
    ("PICNIC PAYMENT 1234", "Groceries"),
    ("CRISP PAYMENT 1234", "Groceries"),
    ("OVPAY PAYMENT 1234", "Transport"),
    ("GVB PAYMENT 1234", "Transport"),
    ("RET PAYMENT 1234", "Transport"),
    ("HTM PAYMENT 1234", "Transport"),
    ("ARRIVA PAYMENT 1234", "Transport"),
    ("UBER PAYMENT 1234", "Transport"),
    ("BOLT PAYMENT 1234", "Transport"),
    ("SHELL PAYMENT 1234", "Transport"),
    ("ESSO PAYMENT 1234", "Transport"),
    ("THUISBEZORGD PAYMENT 1234", "Restaurants"),
    ("MCDONALD PAYMENT 1234", "Restaurants"),
    ("STARBUCKS PAYMENT 1234", "Restaurants"),
    ("RESTAURANT PAYMENT 1234", "Restaurants"),
    ("CAFE PAYMENT 1234", "Restaurants"),
    ("SPOTIFY PAYMENT 1234", "Subscriptions"),
    ("NETFLIX PAYMENT 1234", "Subscriptions"),
    ("DISNEY PAYMENT 1234", "Subscriptions"),
    ("YOUTUBE PREMIUM PAYMENT 1234", "Subscriptions"),
    ("AMAZON PRIME PAYMENT 1234", "Subscriptions"),
    ("AMAZON PAYMENT 1234", "Shopping"),
    ("BOL.COM PAYMENT 1234", "Shopping"),
    ("COOLBLUE PAYMENT 1234", "Shopping"),
    ("MEDIAMARKT PAYMENT 1234", "Shopping"),
    ("IKEA PAYMENT 1234", "Shopping"),
    ("ACTION PAYMENT 1234", "Shopping"),
    ("H&M PAYMENT 1234", "Shopping"),
    ("ZARA PAYMENT 1234", "Shopping"),
    ("BOOKING.COM PAYMENT 1234", "Travel"),
    ("AIRBNB PAYMENT 1234", "Travel"),
    ("KLM PAYMENT 1234", "Travel"),
    ("TRANSAVIA PAYMENT 1234", "Travel"),
    ("RYANAIR PAYMENT 1234", "Travel"),
    ("EASYJET PAYMENT 1234", "Travel"),
    ("VATTENFALL PAYMENT 1234", "Utilities"),
    ("ENECO PAYMENT 1234", "Utilities"),
    ("ESSENT PAYMENT 1234", "Utilities"),
    ("ZIGGO PAYMENT 1234", "Utilities"),
    ("KPN PAYMENT 1234", "Utilities"),
    ("ODIDO PAYMENT 1234", "Utilities"),
    ("VODAFONE PAYMENT 1234", "Utilities"),
    ("VGZ PAYMENT 1234", "Insurance"),
    ("ZILVEREN KRUIS PAYMENT 1234", "Insurance"),
    ("MENZIS PAYMENT 1234", "Insurance"),
    ("ACHMEA PAYMENT 1234", "Insurance"),
    ("APOTHEEK PAYMENT 1234", "Healthcare"),
    ("PHARMACY PAYMENT 1234", "Healthcare"),
    ("TANDARTS PAYMENT 1234", "Healthcare"),
    ("DENTIST PAYMENT 1234", "Healthcare"),
    ("SALARIS PAYMENT 1234", "Income"),
    ("SALARY PAYMENT 1234", "Income"),
    ("PAYROLL PAYMENT 1234", "Income"),
    ("TIKKIE PAYMENT 1234", "Payment Requests"),
    ("GELDMAAT PAYMENT 1234", "Cash Withdrawal"),
    ("CASH WITHDRAWAL PAYMENT 1234", "Cash Withdrawal"),
    ("DEGIRO PAYMENT 1234", "Savings & Investments"),
    ("TRADE REPUBLIC PAYMENT 1234", "Savings & Investments"),
    ("BUX PAYMENT 1234", "Savings & Investments"),
    ("BANK FEE PAYMENT 1234", "Fees"),
    ("SERVICE FEE PAYMENT 1234", "Fees"),
    ("UNIVERSITY PAYMENT 1234", "Education"),
    ("TUITION PAYMENT 1234", "Education"),
    ("COLLEGE PAYMENT 1234", "Education"),
    ("COURSE FEE PAYMENT 1234", "Education"),
    ("COURSERA PAYMENT 1234", "Education"),
    ("UDEMY PAYMENT 1234", "Education"),
]


def category(text):
    return categorize_transaction(text, DEFAULT_CATEGORY_RULES)


@pytest.mark.parametrize("text, expected", SHEET_EXAMPLES)
def test_every_sheet_keyword(text, expected):
    assert category(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        # The more specific keyword wins.
        ("UBER EATS AMSTERDAM", "Restaurants"),
        ("UBER *TRIP HELP.UBER.COM", "Transport"),
        ("AMAZON PRIME NL", "Subscriptions"),
        ("AMAZON.NL MARKETPLACE", "Shopping"),
        ("AH TO GO EINDHOVEN", "Groceries"),
        # Real statement formats
        ("Albert Heijn 1234 Eindhoven", "Groceries"),
        ("NS GROEP IZ NS REIZIGERS", "Transport"),
        ("Bolt.eu/o/2603", "Transport"),
        ("H&M 0123 Amsterdam", "Shopping"),
        ("Booking.com BV", "Travel"),
        ("Tikkie ID 0001 Pizza avond", "Payment Requests"),
        ("Geldmaat 012 Eindhoven", "Cash Withdrawal"),
        ("flatexDEGIRO Bank Dutch Branch", "Savings & Investments"),
        ("DEGIRO storting", "Savings & Investments"),
        ("AON Nederland CV", "Insurance"),
        ("AON Student Insurance", "Insurance"),
    ],
)
def test_real_world_descriptions(text, expected):
    assert category(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "SPARKASSE KOELN",          # "SPAR" is a whole word only
        "Dirk Jansen",              # a friend called Dirk isn't a supermarket
        "TRANSACTION FEE REVERSAL", # "ACTION" must start a word
        "RETOUR BESTELLING 4401",   # "RET" (Rotterdam) is a whole word only
        "NSA MERCHANDISE",          # "NS" is a whole word only
        "KAON AUDIO",               # "AON" is a whole word only
    ],
)
def test_no_false_matches(text):
    assert category(text) == "Other"


def test_tie_goes_to_the_category_listed_first():
    rules = {"A": ["SHOP"], "B": ["SHOP"]}

    assert categorize_transaction("SHOP", rules) == "A"


def test_column_and_single_row_categorizing_agree():
    import pandas as pd

    from categorizer import categorize_dataframe

    texts = [text for text, _ in SHEET_EXAMPLES] + [
        "UBER EATS AMSTERDAM",
        "AMAZON PRIME NL",
        "Dirk Jansen",
        "Something unknown",
    ]
    df = pd.DataFrame({"description": texts, "details": ""})

    assert categorize_dataframe(df, DEFAULT_CATEGORY_RULES).tolist() == [
        category(text) for text in texts
    ]
