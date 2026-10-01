import pytest

from analytics import calculate_spending_by_category, calculate_summary
from categorizer import DEFAULT_CATEGORY_RULES, categorize_dataframe
from flows import REFUND, TRANSFER, classify_flows
from statements import combine_statements, parse_statement
from tests.helpers import SAMPLE_DATA


def parse(file_name):
    with open(SAMPLE_DATA / file_name, "rb") as file:
        return parse_statement(file.read())


def test_parse_statement_detects_bank():
    bank, df = parse("multi_account_ing.csv")

    assert bank == "ing"
    assert len(df) == 8


def test_combine_adds_source_and_sorts_by_date():
    _, ing = parse("multi_account_ing.csv")
    _, revolut = parse("multi_account_revolut.csv")

    df = combine_statements([("ing.csv", ing), ("revolut.csv", revolut)])

    assert len(df) == 14
    assert set(df["source"]) == {"ing.csv", "revolut.csv"}
    assert df["date"].is_monotonic_increasing


def test_same_file_uploaded_twice_is_not_double_counted():
    _, ing = parse("multi_account_ing.csv")

    df = combine_statements([("ing.csv", ing), ("ing copy.csv", ing)])

    assert len(df) == 8


def test_overlapping_exports_keep_each_transaction_once():
    _, ing = parse("multi_account_ing.csv")

    first_half = ing[ing["date"] <= "2026-09-10"]
    second_half = ing[ing["date"] >= "2026-09-05"]

    df = combine_statements([("a.csv", first_half), ("b.csv", second_half)])

    assert len(df) == 8


def test_identical_transactions_within_one_file_are_kept():
    _, ing = parse("ing_sample.csv")

    doubled = ing.loc[[0, 0, 1]].reset_index(drop=True)

    df = combine_statements([("a.csv", doubled)])

    assert len(df) == 3


def combined_multi_account():
    _, ing = parse("multi_account_ing.csv")
    _, revolut = parse("multi_account_revolut.csv")

    df = combine_statements([("ing.csv", ing), ("revolut.csv", revolut)])
    df["category"] = categorize_dataframe(df, DEFAULT_CATEGORY_RULES)
    df["flow"] = classify_flows(df)

    return df


def test_multi_account_flows():
    df = combined_multi_account()

    flows = dict(zip(df["description"] + " " + df["amount"].astype(str), df["flow"]))

    # €200 from ING to Revolut: both halves are transfers.
    assert flows["Revolut Bank UAB -200.0"] == TRANSFER
    assert flows["Top-Up by *1234 200.0"] == TRANSFER

    # Savings account via keyword.
    assert flows["Oranje Spaarrekening V12345678 -300.0"] == TRANSFER

    # Refunds: Revolut marks one, the other is money back from Bol.com.
    assert flows["Zalando 79.95"] == REFUND
    assert flows["Bol.com 54.95"] == REFUND


def test_multi_account_summary():
    summary = calculate_summary(combined_multi_account())

    assert summary["income"] == pytest.approx(2600.00)
    assert summary["refunds"] == pytest.approx(134.90)
    assert summary["fees"] == pytest.approx(1.00)
    # 981.96 spent - 134.90 refunded + 1.00 fee
    assert summary["expenses"] == pytest.approx(848.06)
    assert summary["savings"] == pytest.approx(1751.94)
    assert summary["transfers_out"] == pytest.approx(500.00)
    assert summary["transfers_in"] == pytest.approx(200.00)


def test_refunds_reduce_their_category():
    spending = calculate_spending_by_category(combined_multi_account())

    # Zalando and Bol.com were both fully refunded.
    assert "Shopping" not in spending.index
    assert spending["Fees"] == pytest.approx(1.00)
    assert spending["Groceries"] == pytest.approx(73.57)


def test_transaction_ids_are_unique_and_stable():
    _, ing = parse("multi_account_ing.csv")
    _, revolut = parse("multi_account_revolut.csv")

    first = combine_statements([("ing.csv", ing), ("revolut.csv", revolut)])
    second = combine_statements([("other name.csv", revolut), ("x.csv", ing)])

    assert first["transaction_id"].is_unique
    assert set(first["transaction_id"]) == set(second["transaction_id"])


def test_identical_transactions_get_different_ids():
    _, ing = parse("ing_sample.csv")

    doubled = ing.loc[[0, 0]].reset_index(drop=True)
    df = combine_statements([("a.csv", doubled)])

    assert df["transaction_id"].is_unique
