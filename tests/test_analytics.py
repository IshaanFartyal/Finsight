import pandas as pd
import pytest

from analytics import (
    calculate_monthly_spending,
    calculate_spending_by_category,
    calculate_summary,
)


@pytest.fixture
def transactions():
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2026-09-01", "2026-09-02", "2026-09-03", "2026-10-01"]
            ),
            "amount": [2000.0, -500.0, -100.0, -50.0],
            "category": ["Income", "Housing", "Groceries", "Groceries"],
        }
    )
    df["month"] = df["date"].dt.to_period("M")
    return df


def test_summary(transactions):
    summary = calculate_summary(transactions)

    assert summary["income"] == pytest.approx(2000)
    assert summary["expenses"] == pytest.approx(650)
    assert summary["savings"] == pytest.approx(1350)
    assert summary["savings_rate"] == pytest.approx(0.675)


def test_savings_rate_is_zero_without_income(transactions):
    summary = calculate_summary(transactions[transactions["amount"] < 0])

    assert summary["savings_rate"] == 0


def test_spending_by_category(transactions):
    spending = calculate_spending_by_category(transactions)

    assert spending.to_dict() == {"Housing": 500.0, "Groceries": 150.0}


def test_monthly_spending(transactions):
    spending = calculate_monthly_spending(transactions)

    assert spending.tolist() == [600.0, 50.0]
