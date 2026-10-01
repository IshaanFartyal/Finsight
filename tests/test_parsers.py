import pytest

from parsers.schema import STANDARD_COLUMNS
from tests.helpers import load_sample

# file name, expected bank, expected number of transactions
SAMPLES = [
    ("finsight_multi_month_sample.csv", "unknown", 103),
    ("generic_sample.csv", "unknown", 7),
    ("ing_sample.csv", "ing", 4),
    ("revolut_sample.csv", "revolut", 3),
    ("wise_sample.csv", "wise", 3),
    ("multi_account_ing.csv", "ing", 8),
    ("multi_account_revolut.csv", "revolut", 6),
    ("insights_demo.csv", "unknown", 107),
    ("demo_ing.csv", "ing", 123),
    ("demo_revolut.csv", "revolut", 9),
    ("ing_savings_sample.csv", "ing", 3),
]


@pytest.mark.parametrize("file_name, expected_bank, expected_rows", SAMPLES)
def test_sample_is_detected_and_fully_parsed(
    file_name,
    expected_bank,
    expected_rows,
):
    bank, raw_df, df = load_sample(file_name)

    assert bank == expected_bank

    # No transactions may be silently dropped.
    assert len(raw_df) == expected_rows
    assert len(df) == expected_rows

    assert list(df.columns) == STANDARD_COLUMNS
    assert df["date"].notna().all()
    assert df["amount"].notna().all()


@pytest.mark.parametrize("file_name, expected_bank, expected_rows", SAMPLES)
def test_transactions_are_sorted_by_date(
    file_name,
    expected_bank,
    expected_rows,
):
    _, _, df = load_sample(file_name)

    assert df["date"].is_monotonic_increasing


def test_multi_month_sample_covers_march_to_august():
    _, _, df = load_sample("finsight_multi_month_sample.csv")

    months = sorted(df["date"].dt.strftime("%Y-%m").unique())

    assert months == [
        "2026-03",
        "2026-04",
        "2026-05",
        "2026-06",
        "2026-07",
        "2026-08",
    ]


def test_multi_month_sample_has_one_salary_per_month():
    _, _, df = load_sample("finsight_multi_month_sample.csv")

    salaries = df[df["description"] == "Employer Salary"]

    assert len(salaries) == 6
    assert salaries["date"].dt.month.tolist() == [3, 4, 5, 6, 7, 8]


def test_ing_signs_and_decimal_commas():
    _, _, df = load_sample("ing_sample.csv")

    amounts = dict(zip(df["description"], df["amount"]))

    assert amounts["Albert Heijn"] == pytest.approx(-34.82)
    assert amounts["Employer"] == pytest.approx(850.00)


def test_ing_keeps_mededelingen_as_details():
    _, _, df = load_sample("ing_sample.csv")

    details = dict(zip(df["description"], df["details"]))

    assert details["Employer"] == "SALARY SEPTEMBER"


def test_wise_prefers_merchant_name():
    _, _, df = load_sample("wise_sample.csv")

    assert "Albert Heijn" in df["description"].tolist()


def test_revolut_keeps_completed_transactions_only():
    import io

    import pandas as pd

    from parsers.revolut import parse_revolut

    csv = (
        "Type,Product,Started Date,Completed Date,Description,"
        "Amount,Fee,Currency,State,Balance\n"
        "CARD_PAYMENT,Current,2026-09-02 08:10:00,2026-09-02 08:11:00,"
        "Albert Heijn,-48.25,0.00,EUR,COMPLETED,1451.75\n"
        "CARD_PAYMENT,Current,2026-09-03 10:00:00,,"
        "Spotify,-10.99,0.00,EUR,PENDING,\n"
    )

    df = parse_revolut(pd.read_csv(io.StringIO(csv), dtype=str))

    assert df["description"].tolist() == ["Albert Heijn"]


def test_account_columns():
    _, _, ing = load_sample("ing_sample.csv")
    _, _, revolut = load_sample("revolut_sample.csv")
    _, _, wise = load_sample("wise_sample.csv")

    assert set(ing["account"]) == {"NL12INGB0123456789"}
    assert ing["counterparty_account"].iloc[0] == "NL04BANK1234567890"
    assert set(revolut["account"]) == {"Revolut Current EUR"}
    assert set(wise["account"]) == {"Wise EUR"}


def test_revolut_fee_is_kept():
    _, _, df = load_sample("multi_account_revolut.csv")

    fees = dict(zip(df["description"], df["fee"]))

    assert fees["Cash withdrawal"] == pytest.approx(1.00)
