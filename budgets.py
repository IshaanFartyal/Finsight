"""
Budgets and savings goals.

- A budget is a monthly limit per category ("Restaurants: €150").
- A savings goal is a target amount by a date ("€5,000 for travel by
  August"), turned into how much needs saving per month, compared with
  what the user actually saves.

Saved locally in budgets.json (git-ignored).
"""

import json
from pathlib import Path

import pandas as pd

from analytics import calculate_summary

BUDGETS_PATH = Path(__file__).parent / "budgets.json"

# Average savings are measured over this many complete months.
SAVINGS_LOOKBACK_MONTHS = 3

# A budget counts as "at risk" from this share used (or projected).
AT_RISK_SHARE = 0.9

OVER = "over"
AT_RISK = "at risk"
ON_TRACK = "on track"


# ============================================================
# STORAGE
# ============================================================

def empty_budgets():
    return {"budgets": {}, "goals": []}


def _positive_number(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None

    return value if value > 0 else None


def clean_goal(goal):
    """A goal with valid fields, or None if it's incomplete."""

    name = str(goal.get("name") or "").strip()
    target = _positive_number(goal.get("target"))
    deadline = pd.to_datetime(goal.get("deadline"), errors="coerce")

    if not name or target is None or pd.isna(deadline):
        return None

    saved = _positive_number(goal.get("saved")) or 0.0

    return {
        "name": name,
        "target": target,
        "deadline": deadline.strftime("%Y-%m-%d"),
        "saved": saved,
    }


def goals_table(goals):
    """
    Goals as a table for editing, with fixed column types.

    The types matter: with no goals yet, pandas would give the empty
    deadline column a number type, which a date picker can't edit.
    """

    return pd.DataFrame(
        {
            "name": [goal["name"] for goal in goals],
            "target": [goal["target"] for goal in goals],
            "deadline": pd.to_datetime(
                pd.Series([goal["deadline"] for goal in goals], dtype="object")
            ),
            "saved": [goal["saved"] for goal in goals],
        },
        columns=["name", "target", "deadline", "saved"],
    ).astype(
        {
            "name": "object",
            "target": "float",
            "deadline": "datetime64[ns]",
            "saved": "float",
        }
    )


def load_budgets(path=BUDGETS_PATH):
    path = Path(path)
    data = empty_budgets()

    if not path.exists():
        return data

    try:
        with open(path, encoding="utf-8") as budgets_file:
            saved = json.load(budgets_file)

    except (OSError, json.JSONDecodeError):
        return data

    for category, amount in (saved.get("budgets") or {}).items():
        amount = _positive_number(amount)

        if amount is not None:
            data["budgets"][str(category)] = amount

    for goal in saved.get("goals") or []:
        if isinstance(goal, dict):
            goal = clean_goal(goal)

            if goal is not None:
                data["goals"].append(goal)

    return data


def save_budgets(data, path=BUDGETS_PATH):
    with open(path, "w", encoding="utf-8") as budgets_file:
        json.dump(data, budgets_file, indent=2, ensure_ascii=False)


# ============================================================
# BUDGETS
# ============================================================

def budget_status(spending_by_category, budgets, projected_by_category=None):
    """
    Compare spending with each budget.

    spending_by_category: Series {category: amount spent this month}.
    budgets: {category: monthly budget}.
    projected_by_category: optional Series of projected month-end
        spending (for a month that isn't over yet).

    Returns a DataFrame, one row per budgeted category, most used first:
        category, budget, spent, remaining, share_used, projected, status
    """

    columns = [
        "category",
        "budget",
        "spent",
        "remaining",
        "share_used",
        "projected",
        "status",
    ]

    rows = []

    for category, budget in budgets.items():
        spent = float(spending_by_category.get(category, 0.0))

        projected = (
            float(projected_by_category.get(category, spent))
            if projected_by_category is not None
            else None
        )

        # Judge by the projection when there is one: €100 of €150 halfway
        # through the month is heading over budget.
        judged = max(spent, projected or 0)

        if spent > budget:
            status = OVER
        elif judged > budget or judged >= AT_RISK_SHARE * budget:
            status = AT_RISK
        else:
            status = ON_TRACK

        rows.append(
            {
                "category": category,
                "budget": budget,
                "spent": spent,
                "remaining": budget - spent,
                "share_used": spent / budget,
                "projected": projected,
                "status": status,
            }
        )

    if not rows:
        return pd.DataFrame(columns=columns)

    return (
        pd.DataFrame(rows, columns=columns)
        .sort_values("share_used", ascending=False)
        .reset_index(drop=True)
    )


# ============================================================
# SAVINGS GOALS
# ============================================================

def average_monthly_savings(df, months=SAVINGS_LOOKBACK_MONTHS):
    """
    Average income minus expenses over the last complete months.

    The latest month is left out when the statements end before it does,
    since a half month would understate spending.

    Returns (average, months_used). average is None without data.
    """

    if df is None or df.empty:
        return None, []

    all_months = sorted(df["month"].dropna().unique())
    latest = all_months[-1]

    if df["date"].max().normalize() < latest.end_time.normalize() - pd.Timedelta(days=2):
        all_months = all_months[:-1]

    used = all_months[-months:]

    if not used:
        return None, []

    savings = [
        calculate_summary(df[df["month"] == month])["savings"]
        for month in used
    ]

    return sum(savings) / len(savings), used


def goal_plan(goal, average_savings, today=None):
    """
    What it takes to reach a savings goal.

    Returns a dict:
        remaining         amount still to save
        months_left       months until the deadline (fractional)
        needed_per_month  remaining / months_left
        progress          share of the target already saved
        reached           the target is already saved
        deadline_passed   the deadline is today or earlier
        on_track          average savings cover what's needed
                          (None when there is no savings history)
        gap_per_month     needed_per_month - average savings (> 0 means short)
    """

    today = pd.Timestamp(today or pd.Timestamp.today()).normalize()
    deadline = pd.Timestamp(goal["deadline"]).normalize()

    remaining = max(goal["target"] - goal.get("saved", 0.0), 0.0)
    months_left = (deadline - today).days / 30.44
    reached = remaining == 0
    deadline_passed = months_left <= 0

    needed = (
        remaining / months_left
        if not reached and not deadline_passed
        else 0.0
    )

    on_track = None
    gap = None

    if average_savings is not None and not reached and not deadline_passed:
        gap = needed - average_savings
        on_track = gap <= 0

    return {
        "remaining": remaining,
        "months_left": max(months_left, 0.0),
        "needed_per_month": needed,
        "progress": min(goal.get("saved", 0.0) / goal["target"], 1.0),
        "reached": reached,
        "deadline_passed": deadline_passed and not reached,
        "on_track": on_track,
        "gap_per_month": gap,
    }
