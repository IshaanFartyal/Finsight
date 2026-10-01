import pandas as pd
import pytest

from categorizer import DEFAULT_CATEGORY_RULES
from corrections import SCOPE_MERCHANT, add_correction, empty_corrections
from flows import default_settings
from merchants import normalize_merchant
from pipeline import build_transactions
from review import categorized_share, uncategorized_merchants

# A made-up ING statement with the kind of descriptions keyword rules
# can't know: local shops behind payment processors, a sports club and
# a broker that isn't in the default rules.
MESSY_ING = (
    '"Datum";"Naam / Omschrijving";"Rekening";"Tegenrekening";"Code";"Af Bij";'
    '"Bedrag (EUR)";"Mutatiesoort";"Mededelingen";"Saldo na mutatie";"Tag"\n'
    '"20260901";"Employer";"NL12INGB0123456789";"NL03BANK1234567890";"OV";"Bij";"2000,00";"Overschrijving";"SALARY SEPTEMBER";"2000,00";""\n'
    '"20260902";"SumUp  *Bakkerij Jansen";"NL12INGB0123456789";"";"BA";"Af";"4,50";"Betaalautomaat";"";"1995,50";""\n'
    '"20260905";"SUMUP  *BAKKERIJ JANSEN";"NL12INGB0123456789";"";"BA";"Af";"6,20";"Betaalautomaat";"";"1989,30";""\n'
    '"20260909";"SumUp *Bakkerij Jansen B.V.";"NL12INGB0123456789";"";"BA";"Af";"3,80";"Betaalautomaat";"";"1985,50";""\n'
    '"20260903";"Zettle_*Kapsalon Mooi";"NL12INGB0123456789";"";"BA";"Af";"28,00";"Betaalautomaat";"";"1957,50";""\n'
    '"20260904";"Hockeyclub Oranje";"NL12INGB0123456789";"NL91RABO0000000001";"IC";"Af";"35,00";"Incasso";"CONTRIBUTIE 2026";"1922,50";""\n'
    '"20260906";"Albert Heijn 1234";"NL12INGB0123456789";"";"BA";"Af";"40,00";"Betaalautomaat";"";"1882,50";""\n'
    '"20260910";"Meesman Indexbeleggen";"NL12INGB0123456789";"NL40INGB0000000002";"OV";"Af";"300,00";"Overschrijving";"INLEG";"1582,50";""\n'
)


def build(corrections=None):
    df, _, failed = build_transactions(
        [("ing.csv", MESSY_ING.encode())],
        DEFAULT_CATEGORY_RULES,
        default_settings(),
        corrections or empty_corrections(),
    )

    assert failed == {}

    return df


def test_each_unknown_merchant_is_listed_once():
    merchants = uncategorized_merchants(build())

    # Most transactions first; ties: the largest amount spent first.
    assert merchants["merchant"].tolist() == [
        "Bakkerij Jansen",
        "Meesman Indexbeleggen",
        "Hockeyclub Oranje",
        "Kapsalon Mooi",
    ]
    assert merchants.iloc[0]["transactions"] == 3
    assert merchants.iloc[0]["total"] == pytest.approx(-14.50)


def test_categorized_merchants_and_income_are_not_listed():
    merchants = set(uncategorized_merchants(build())["merchant"])

    assert "Albert Heijn 1234" not in merchants
    assert "Employer" not in merchants


def test_categorized_share():
    # 8 transactions, 4 merchants (6 transactions) without a category.
    assert categorized_share(build()) == pytest.approx(2 / 8)


def test_reviewing_each_merchant_once_categorizes_everything():
    df = build()
    corrections = empty_corrections()

    choices = {
        "Bakkerij Jansen": "Groceries",
        "Kapsalon Mooi": "Shopping",
        "Hockeyclub Oranje": "Subscriptions",
        "Meesman Indexbeleggen": "Savings & Investments",
    }

    for _, row in uncategorized_merchants(df).iterrows():
        add_correction(
            corrections,
            {"transaction_id": "", "description": row["example"]},
            "category",
            choices[row["merchant"]],
            SCOPE_MERCHANT,
        )

    # Uploading the same statement again: everything is remembered.
    reviewed = build(corrections)

    assert uncategorized_merchants(reviewed).empty
    assert categorized_share(reviewed) == 1.0

    # All three spellings of the bakery were covered by one choice.
    bakery = reviewed[
        reviewed["description"].apply(normalize_merchant) == "BAKKERIJ JANSEN"
    ]

    assert len(bakery) == 3
    assert set(bakery["category"]) == {"Groceries"}

    # Choosing Savings & Investments makes it a transfer, not spending.
    meesman = reviewed[reviewed["merchant"] == "Meesman Indexbeleggen"].iloc[0]

    assert meesman["flow"] == "transfer"
    assert meesman["category"] == "Savings & Investments"


def test_transfers_are_never_listed_for_review():
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-09-01", "2026-09-02"]),
            "description": ["Oranje Spaarrekening", "Unknown Shop"],
            "amount": [-100.0, -10.0],
            "category": ["Other", "Other"],
            "flow": ["transfer", "expense"],
        }
    )

    assert uncategorized_merchants(df)["merchant"].tolist() == ["Unknown Shop"]
    assert categorized_share(df) == 0.0
