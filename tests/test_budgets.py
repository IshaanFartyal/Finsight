import pandas as pd
import pytest

from budgets import (
    AT_RISK,
    OVER,
    ON_TRACK,
    average_monthly_savings,
    budget_status,
    clean_goal,
    empty_budgets,
    goal_plan,
    goals_table,
    load_budgets,
    save_budgets,
)


# ------------------------------------------------------------
# Budgets
# ------------------------------------------------------------

def test_budget_status():
    spending = pd.Series({"Restaurants": 95.0, "Groceries": 190.0, "Shopping": 140.0})
    budgets = {"Restaurants": 150.0, "Groceries": 180.0, "Shopping": 150.0, "Transport": 60.0}

    status = budget_status(spending, budgets).set_index("category")

    assert status.loc["Restaurants", "status"] == ON_TRACK
    assert status.loc["Restaurants", "remaining"] == pytest.approx(55.0)
    assert status.loc["Groceries", "status"] == OVER
    # 140 of 150 is more than 90% used.
    assert status.loc["Shopping", "status"] == AT_RISK
    # Nothing spent yet in a budgeted category.
    assert status.loc["Transport", "spent"] == 0
    assert status.loc["Transport", "status"] == ON_TRACK


def test_projection_flags_budget_heading_over():
    spending = pd.Series({"Restaurants": 100.0})
    projected = pd.Series({"Restaurants": 210.0})

    status = budget_status(spending, {"Restaurants": 150.0}, projected)

    assert status.iloc[0]["status"] == AT_RISK
    assert status.iloc[0]["projected"] == pytest.approx(210.0)


def test_most_used_budget_first():
    spending = pd.Series({"A": 10.0, "B": 90.0})

    status = budget_status(spending, {"A": 100.0, "B": 100.0})

    assert status["category"].tolist() == ["B", "A"]


def test_no_budgets():
    assert budget_status(pd.Series(dtype=float), {}).empty


# ------------------------------------------------------------
# Savings goals
# ------------------------------------------------------------

def goal(**changes):
    base = {"name": "Travel", "target": 5000, "deadline": "2027-04-01", "saved": 1000}
    return clean_goal({**base, **changes})


def test_goal_plan_on_track():
    plan = goal_plan(goal(), average_savings=900, today="2026-10-01")

    assert plan["remaining"] == pytest.approx(4000)
    assert plan["months_left"] == pytest.approx(182 / 30.44)
    assert plan["needed_per_month"] == pytest.approx(4000 / (182 / 30.44))
    assert plan["progress"] == pytest.approx(0.2)
    assert plan["on_track"] is True


def test_goal_plan_short():
    plan = goal_plan(goal(), average_savings=400, today="2026-10-01")

    assert plan["on_track"] is False
    assert plan["gap_per_month"] == pytest.approx(plan["needed_per_month"] - 400)


def test_goal_reached_and_deadline_passed():
    assert goal_plan(goal(saved=5000), 500, today="2026-10-01")["reached"]

    late = goal_plan(goal(deadline="2026-09-01"), 500, today="2026-10-01")

    assert late["deadline_passed"]
    assert late["on_track"] is None


def test_goal_without_savings_history():
    plan = goal_plan(goal(), average_savings=None, today="2026-10-01")

    assert plan["on_track"] is None
    assert plan["needed_per_month"] > 0


def test_incomplete_goals_are_rejected():
    assert clean_goal({"name": "", "target": 100, "deadline": "2027-01-01"}) is None
    assert clean_goal({"name": "Car", "target": None, "deadline": "2027-01-01"}) is None
    assert clean_goal({"name": "Car", "target": 100, "deadline": None}) is None
    assert clean_goal({"name": "Car", "target": 100, "deadline": "2027-01-01"})["saved"] == 0.0


def test_average_monthly_savings_skips_unfinished_month():
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2026-07-01", "2026-07-15", "2026-08-01", "2026-08-15", "2026-09-01"]
            ),
            "amount": [2000.0, -1500.0, 2000.0, -1000.0, 2000.0],
        }
    )
    df["month"] = df["date"].dt.to_period("M")

    average, used = average_monthly_savings(df)

    # September only has its first day: left out.
    assert [str(month) for month in used] == ["2026-07", "2026-08"]
    assert average == pytest.approx((500 + 1000) / 2)


def test_round_trip(tmp_path):
    path = tmp_path / "budgets.json"
    data = {"budgets": {"Restaurants": 150.0}, "goals": [goal()]}

    save_budgets(data, path)

    assert load_budgets(path) == data


def test_missing_or_corrupt_file(tmp_path):
    assert load_budgets(tmp_path / "missing.json") == empty_budgets()

    path = tmp_path / "budgets.json"
    path.write_text("not json", encoding="utf-8")

    assert load_budgets(path) == empty_budgets()


def test_goals_table_has_date_column_even_when_empty():
    # Regression: an empty deadline column used to become a number
    # column, which made the goals editor crash.
    for goals in ([], [goal()]):
        table = goals_table(goals)

        assert str(table["deadline"].dtype).startswith("datetime64")
        assert table["target"].dtype == "float64"


def test_goals_table_round_trips_through_clean_goal():
    table = goals_table([goal()])

    assert [clean_goal(row.to_dict()) for _, row in table.iterrows()] == [goal()]
