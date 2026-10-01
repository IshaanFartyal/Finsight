"""
Deterministic insights: what changed, what recurs, what is unusual.

Everything here is calculated, not guessed. These results are also what
a future AI layer would explain: Python calculates the facts, the AI
puts them into words.

All functions expect the combined transaction table from the app, with
"date", "description", "amount", "category", "flow" and "month" columns.
"""

import re

import numpy as np
import pandas as pd

from analytics import (
    FEES_CATEGORY,
    calculate_spending_by_category,
    calculate_summary,
)
from flows import EXPENSE, normalize_merchant as _merchant

# Category changes
LOOKBACK_MONTHS = 3
MIN_CHANGE_EUR = 25.0          # ignore tiny swings (€5 -> €10 is +100%)
NOTABLE_CHANGE_PCT = 0.25      # +-25% vs average is worth mentioning

# Recurring payments: (name, min days apart, max days apart, per month)
FREQUENCIES = [
    ("weekly", 5, 9, 52 / 12),
    ("monthly", 25, 35, 1.0),
    ("quarterly", 80, 100, 1 / 3),
    ("yearly", 350, 380, 1 / 12),
]
MIN_OCCURRENCES = 3
MAX_AMOUNT_VARIATION = 0.15    # variable bills: within +-15% of the typical amount

# A fixed price "changes" when it moves by at least 2% and €0.50.
# Bigger than x2 or smaller than /2 is not a price change but a
# different product.
PRICE_CHANGE_MIN_PCT = 0.02
PRICE_CHANGE_MIN_EUR = 0.50
PRICE_CHANGE_MAX_RATIO = 2.0

# New recurring payments: first paid within this many days before the
# end of the selected month, and not simply where the statement starts.
NEW_RECURRING_DAYS = 92
STATEMENT_START_MARGIN_DAYS = 31

# Month-end forecast: with this few days left, the month counts as done.
FORECAST_MIN_DAYS_REMAINING = 3

# Possible duplicate charges
DUPLICATE_MAX_DAYS = 2
DUPLICATE_MIN_EUR = 15.0

# Unusual transactions
MIN_HISTORY = 5                # need this many earlier transactions in a category
UNUSUAL_MULTIPLE = 2.5         # at least 2.5x the category's typical amount
UNUSUAL_MIN_EUR = 50.0


def _expenses(df):
    if "flow" in df.columns:
        return df[df["flow"] == EXPENSE]

    return df[df["amount"] < 0]


def data_until(df, month):
    """Transactions up to and including month (nothing from later months)."""

    return df[df["month"] <= month]


def _previous_months(df, month, lookback=LOOKBACK_MONTHS):
    months = sorted(m for m in df["month"].dropna().unique() if m < month)

    return months[-lookback:]


# ============================================================
# 1. CATEGORY CHANGES
# ============================================================

def category_changes(df, month, lookback=LOOKBACK_MONTHS):
    """
    Compare each category's spending in month with its average over the
    previous `lookback` months that are in the data.

    Returns a DataFrame sorted by absolute euro change:
        category, this_month, average, change, change_pct, notable

    Empty if there is no earlier month to compare with.
    """

    columns = [
        "category",
        "this_month",
        "average",
        "change",
        "change_pct",
        "notable",
    ]

    previous = _previous_months(df, month, lookback)

    if not previous:
        return pd.DataFrame(columns=columns)

    current = calculate_spending_by_category(df[df["month"] == month])

    history = pd.DataFrame(
        {
            str(m): calculate_spending_by_category(df[df["month"] == m])
            for m in previous
        }
    ).fillna(0)

    # Months without any spending in a category count as €0.
    average = history.sum(axis=1) / len(previous)

    table = pd.DataFrame(
        {"this_month": current, "average": average}
    ).fillna(0)

    table["change"] = table["this_month"] - table["average"]
    table["change_pct"] = [
        change / avg if avg > 0 else None
        for change, avg in zip(table["change"], table["average"])
    ]
    table["notable"] = [
        abs(change) >= MIN_CHANGE_EUR
        and (pct is None or abs(pct) >= NOTABLE_CHANGE_PCT)
        for change, pct in zip(table["change"], table["change_pct"])
    ]

    table = table.reset_index(names="category")

    return (
        table.reindex(table["change"].abs().sort_values(ascending=False).index)
        .reset_index(drop=True)[columns]
    )


# ============================================================
# 2. RECURRING PAYMENTS
# ============================================================

def _frequency(days_between):
    """Match the typical gap between payments to a frequency, or None."""

    median_gap = days_between.median()

    for name, low, high, per_month in FREQUENCIES:
        if low <= median_gap <= high:
            # Most gaps must fit, so one late payment is tolerated but
            # an irregular habit (groceries every few days) is not.
            fitting = days_between.between(low * 0.8, high * 1.2).mean()

            if fitting >= 0.75:
                return name, high, per_month

    return None


def _price_pattern(amounts):
    """
    Look at a merchant's payment amounts, oldest first.

    Returns (current_amount, changes) when the amounts look recurring,
    or None when they vary too much:

    - fixed price, possibly with price changes: stable stretches of equal
      amounts (every stretch but the newest at least 2 payments), e.g.
      13.99, 13.99, 13.99, 15.99. changes lists (position, old, new)
      for every price change.
    - variable bill: all amounts within +-15% of the typical amount
      (energy, phone usage). No price changes are reported.
    """

    amounts = [float(amount) for amount in amounts]

    jumps = [
        position
        for position in range(1, len(amounts))
        if abs(amounts[position] - amounts[position - 1])
        >= max(PRICE_CHANGE_MIN_EUR, PRICE_CHANGE_MIN_PCT * amounts[position - 1])
    ]

    stretches = []
    begin = 0

    for position in jumps + [len(amounts)]:
        stretches.append(amounts[begin:position])
        begin = position

    is_fixed_price = (
        all(len(stretch) >= 2 for stretch in stretches[:-1])
        and all(
            1 / PRICE_CHANGE_MAX_RATIO
            <= amounts[position] / amounts[position - 1]
            <= PRICE_CHANGE_MAX_RATIO
            for position in jumps
        )
    )

    if is_fixed_price:
        changes = [
            (position, amounts[position - 1], amounts[position])
            for position in jumps
        ]
        return amounts[-1], changes

    typical = float(np.median(amounts))

    if typical > 0 and all(
        abs(amount - typical) / typical <= MAX_AMOUNT_VARIATION
        for amount in amounts
    ):
        return typical, []

    return None


def _recurring_series(df):
    """
    Every recurring payment in df, with its individual payments.

    Returns a list of dicts: the fields of detect_recurring() plus
    "payments" (that merchant's transactions, oldest first) and
    "price_changes" [(date, old, new)].
    """

    expenses = _expenses(df).copy()

    if expenses.empty:
        return []

    expenses["_merchant"] = expenses["description"].apply(_merchant)
    data_end = df["date"].max()

    series = []

    for _, payments in expenses.groupby("_merchant"):
        if len(payments) < MIN_OCCURRENCES:
            continue

        payments = payments.sort_values("date")

        pattern = _price_pattern(payments["amount"].abs())

        if pattern is None:
            continue

        current_amount, changes = pattern

        if current_amount <= 0:
            continue

        days_between = payments["date"].diff().dt.days.dropna()

        match = _frequency(days_between)

        if match is None:
            continue

        frequency, max_gap, per_month = match

        last_date = payments["date"].iloc[-1]

        series.append(
            {
                # Show the name as it appears on the statement.
                "merchant": payments["description"].iloc[-1],
                "category": payments["category"].mode().iloc[0],
                "amount": round(current_amount, 2),
                "frequency": frequency,
                "monthly_cost": round(current_amount * per_month, 2),
                "occurrences": len(payments),
                "first_date": payments["date"].iloc[0],
                "last_date": last_date,
                "next_expected": last_date
                + pd.Timedelta(days=round(days_between.median())),
                "active": (data_end - last_date).days <= max_gap * 1.5,
                "interval_days": max(1, round(days_between.median())),
                "payments": payments,
                "price_changes": [
                    (payments["date"].iloc[position], old, new)
                    for position, old, new in changes
                ],
            }
        )

    return series


RECURRING_COLUMNS = [
    "merchant",
    "category",
    "amount",
    "frequency",
    "monthly_cost",
    "occurrences",
    "first_date",
    "last_date",
    "next_expected",
    "active",
]


def detect_recurring(df):
    """
    Find expenses that repeat at a regular interval for a similar amount:
    subscriptions, rent, insurance, gym.

    Returns a DataFrame sorted by monthly cost:
        merchant, category, amount (the current price), frequency,
        monthly_cost, occurrences, first_date, last_date, next_expected,
        active

    active is False when a payment has stopped appearing (its last
    payment is overdue by more than one interval at the end of the data).
    """

    series = _recurring_series(df)

    if not series:
        return pd.DataFrame(columns=RECURRING_COLUMNS)

    return (
        pd.DataFrame(series)[RECURRING_COLUMNS]
        .sort_values("monthly_cost", ascending=False)
        .reset_index(drop=True)
    )


def price_changes(df, month):
    """
    Recurring payments whose price changed in month, e.g. Netflix going
    from €13.99 to €15.99.

    Returns: merchant, category, date, old_amount, new_amount, change,
    change_pct.
    """

    columns = [
        "merchant",
        "category",
        "date",
        "old_amount",
        "new_amount",
        "change",
        "change_pct",
    ]

    rows = [
        {
            "merchant": item["merchant"],
            "category": item["category"],
            "date": date,
            "old_amount": round(old, 2),
            "new_amount": round(new, 2),
            "change": round(new - old, 2),
            "change_pct": (new - old) / old,
        }
        for item in _recurring_series(data_until(df, month))
        for date, old, new in item["price_changes"]
        if date.to_period("M") == month
    ]

    return pd.DataFrame(rows, columns=columns)


def new_recurring(df, month):
    """
    Recurring payments that started recently: first paid within the
    three months up to the end of month.

    A payment needs three occurrences to be recognized, so a subscription
    shows up here two payments after it started. Payments that simply
    begin where the statement begins are not counted as new.
    """

    data = data_until(df, month)

    if data.empty:
        return pd.DataFrame(columns=RECURRING_COLUMNS)

    month_end = month.end_time
    data_start = df["date"].min()

    recurring = detect_recurring(data)

    if recurring.empty:
        return recurring

    is_new = (
        recurring["active"]
        & (recurring["first_date"] >= month_end - pd.Timedelta(days=NEW_RECURRING_DAYS))
        & (
            recurring["first_date"]
            > data_start + pd.Timedelta(days=STATEMENT_START_MARGIN_DAYS)
        )
    )

    return recurring[is_new].reset_index(drop=True)


def duplicate_charges(df, month):
    """
    Possible double charges in month: the same merchant charging exactly
    the same amount (at least €15) twice within two days.

    Returns one row per pair: merchant, amount, first_date, second_date,
    first_id, second_id.
    """

    columns = [
        "merchant",
        "amount",
        "first_date",
        "second_date",
        "first_id",
        "second_id",
    ]

    expenses = _expenses(df).copy()
    expenses = expenses[expenses["amount"].abs() >= DUPLICATE_MIN_EUR]

    if expenses.empty:
        return pd.DataFrame(columns=columns)

    expenses["_merchant"] = expenses["description"].apply(_merchant)
    expenses["_cents"] = (expenses["amount"].abs() * 100).round().astype(int)

    if "transaction_id" not in expenses.columns:
        expenses["transaction_id"] = expenses.index.astype(str)

    rows = []

    for _, group in expenses.groupby(["_merchant", "_cents"]):
        if len(group) < 2:
            continue

        group = group.sort_values("date")
        previous = None

        for _, charge in group.iterrows():
            if (
                previous is not None
                and (charge["date"] - previous["date"]).days <= DUPLICATE_MAX_DAYS
                and charge["date"].to_period("M") == month
            ):
                rows.append(
                    {
                        "merchant": charge["description"],
                        "amount": abs(charge["amount"]),
                        "first_date": previous["date"],
                        "second_date": charge["date"],
                        "first_id": previous["transaction_id"],
                        "second_id": charge["transaction_id"],
                    }
                )
                # Don't pair the second charge again with a third.
                previous = None
                continue

            previous = charge

    return pd.DataFrame(rows, columns=columns)


# ============================================================
# MONTH-END FORECAST
# ============================================================

def month_end_forecast(df, month):
    """
    Projected spending for month, if month is the latest month in the
    data and the statements end before the month does.

    forecast = spent so far
             + recurring payments still due this month
             + everyday (non-recurring) spending at the pace so far

    Splitting it this way keeps rent paid on the 2nd from being
    projected as if it happened every day.

    Returns None for complete months (or with fewer than 3 days left),
    otherwise a dict:
        as_of, days_elapsed, days_in_month, spent_so_far, recurring_due,
        variable_remaining, forecast, usual, by_category (Series)
    usual is the average spending of up to 3 earlier months (None if
    there are no earlier months).
    """

    if df.empty or month != df["month"].max():
        return None

    as_of = df["date"].max().normalize()
    month_end = month.end_time.normalize()

    days_in_month = month.days_in_month
    days_elapsed = as_of.day
    days_remaining = days_in_month - days_elapsed

    if as_of >= month_end or days_remaining < FORECAST_MIN_DAYS_REMAINING:
        return None

    month_df = df[df["month"] == month]

    spent_by_category = calculate_spending_by_category(month_df)
    spent_so_far = calculate_summary(month_df)["expenses"]

    # Recurring payments still to come before the month ends.
    series = [
        item
        for item in _recurring_series(data_until(df, month))
        if item["active"]
    ]

    due_by_category = {}

    for item in series:
        next_date = item["next_expected"]

        while next_date <= month_end:
            if next_date > as_of:
                due_by_category[item["category"]] = (
                    due_by_category.get(item["category"], 0) + item["amount"]
                )

            next_date += pd.Timedelta(days=item["interval_days"])

    # Everyday spending so far, without recurring payments.
    recurring_merchants = {_merchant(item["merchant"]) for item in series}

    expenses = _expenses(month_df)
    everyday = expenses[
        ~expenses["description"].apply(_merchant).isin(recurring_merchants)
    ]

    pace_by_category = (
        everyday["amount"].abs().groupby(everyday["category"]).sum()
        / days_elapsed
    )

    variable_by_category = pace_by_category * days_remaining

    by_category = (
        spent_by_category.add(pd.Series(due_by_category, dtype=float), fill_value=0)
        .add(variable_by_category, fill_value=0)
        .sort_values(ascending=False)
    )

    recurring_due = float(sum(due_by_category.values()))
    variable_remaining = float(variable_by_category.sum())

    previous = _previous_months(df, month)
    usual = (
        float(np.mean([
            calculate_summary(df[df["month"] == m])["expenses"]
            for m in previous
        ]))
        if previous
        else None
    )

    return {
        "as_of": as_of,
        "days_elapsed": days_elapsed,
        "days_in_month": days_in_month,
        "spent_so_far": spent_so_far,
        "recurring_due": recurring_due,
        "variable_remaining": variable_remaining,
        "forecast": spent_so_far + recurring_due + variable_remaining,
        "usual": usual,
        "by_category": by_category,
    }


# ============================================================
# 3. UNUSUAL TRANSACTIONS
# ============================================================

def unusual_transactions(df, month):
    """
    Expenses in month that are far larger than usual.

    "Usual" is judged against earlier, non-recurring expenses (rent and
    subscriptions say nothing about what a normal purchase costs):

    - a merchant seen before is compared with what you usually spend
      there (€150 at Albert Heijn vs a usual €45);
    - a new merchant is compared with its category, or with all your
      spending if the category has too little history, and must also be
      larger than 90% of those earlier purchases.

    Returns the flagged transactions with extra columns:
        typical, multiple, compared_with
    """

    expenses = _expenses(df).copy()
    expenses["_abs"] = expenses["amount"].abs()
    expenses["_merchant"] = expenses["description"].apply(_merchant)

    recurring = detect_recurring(df)
    recurring_merchants = (
        set(recurring["merchant"].apply(_merchant))
        if not recurring.empty
        else set()
    )

    pool = expenses[
        ~expenses["_merchant"].isin(recurring_merchants)
    ].sort_values("date", kind="stable")

    # Plain arrays, sorted by date: "everything before this purchase" is
    # then simply the first n entries, which keeps this fast on years of
    # transactions.
    dates = pool["date"].to_numpy()
    amounts = pool["_abs"].to_numpy()
    merchants = pool["_merchant"].to_numpy()
    categories = pool["category"].to_numpy()

    flagged = []

    for index, row in pool[pool["month"] == month].iterrows():
        n_earlier = np.searchsorted(dates, row["date"].to_datetime64(), side="left")

        earlier_amounts = amounts[:n_earlier]
        same_merchant = earlier_amounts[merchants[:n_earlier] == row["_merchant"]]

        if same_merchant.size:
            typical = float(np.median(same_merchant))
            threshold = typical * UNUSUAL_MULTIPLE
            compared_with = f"your usual spend at {row['description']}"

        else:
            history = earlier_amounts[categories[:n_earlier] == row["category"]]
            compared_with = f"your typical {row['category']} purchase"

            if history.size < MIN_HISTORY:
                history = earlier_amounts
                compared_with = "your typical purchase"

            if history.size < MIN_HISTORY:
                continue

            typical = float(np.median(history))
            threshold = max(
                typical * UNUSUAL_MULTIPLE,
                float(np.quantile(history, 0.9)),
            )

        if typical <= 0:
            continue

        if row["_abs"] >= threshold and row["_abs"] >= UNUSUAL_MIN_EUR:
            flagged.append(
                (index, typical, row["_abs"] / typical, compared_with)
            )

    result = df.loc[[item[0] for item in flagged]].copy()
    result["typical"] = [round(item[1], 2) for item in flagged]
    result["multiple"] = [round(item[2], 1) for item in flagged]
    result["compared_with"] = [item[3] for item in flagged]

    return result.sort_values("multiple", ascending=False)


# ============================================================
# 4. KEY INSIGHTS
# ============================================================

def key_insights(df, month):
    """
    The most notable findings for month, most important first, as dicts:
        topic  "increase", "unusual", "forecast", "duplicate", "price_change",
               "savings", "new_recurring", "decrease" or "recurring"
        kind   "warning", "positive" or "info"
        text   Markdown
    """

    insights = []

    # Spending changes
    changes = category_changes(df, month)
    notable = changes[changes["notable"].astype(bool)]

    increases = notable[notable["change"] > 0]
    decreases = notable[notable["change"] < 0]

    if not increases.empty:
        top = increases.iloc[0]
        insights.append(
            {
                "topic": "increase",
                "kind": "warning",
                "text": (
                    f"📈 **{top['category']}** spending is "
                    f"**€{top['this_month']:,.2f}**, "
                    + (
                        f"{top['change_pct']:.0%} above"
                        if top["change_pct"] is not None
                        else "up from nothing in"
                    )
                    + f" your recent average of €{top['average']:,.2f}."
                ),
            }
        )

    # Unusual transactions
    unusual = unusual_transactions(df, month)

    if not unusual.empty:
        top = unusual.iloc[0]
        insights.append(
            {
                "topic": "unusual",
                "kind": "warning",
                "text": (
                    f"🔎 **{top['description']}** "
                    f"(€{abs(top['amount']):,.2f}) is "
                    f"{top['multiple']:.1f}x "
                    f"{top['compared_with']}."
                ),
            }
        )

    # Month-end forecast (only for the latest, unfinished month)
    forecast = month_end_forecast(df, month)

    if forecast and forecast["usual"]:
        difference = forecast["forecast"] - forecast["usual"]

        if difference >= max(50, 0.10 * forecast["usual"]):
            insights.append(
                {
                    "topic": "forecast",
                    "kind": "warning",
                    "text": (
                        f"🔮 At your current pace you'll spend about "
                        f"**€{forecast['forecast']:,.0f}** this month, "
                        f"€{difference:,.0f} more than usual."
                    ),
                }
            )

        elif difference <= -max(50, 0.10 * forecast["usual"]):
            insights.append(
                {
                    "topic": "forecast",
                    "kind": "positive",
                    "text": (
                        f"🔮 You're on course to spend about "
                        f"**€{forecast['forecast']:,.0f}** this month, "
                        f"€{-difference:,.0f} less than usual."
                    ),
                }
            )

    # Possible double charges
    duplicates = duplicate_charges(df, month)

    if not duplicates.empty:
        top = duplicates.iloc[0]
        insights.append(
            {
                "topic": "duplicate",
                "kind": "warning",
                "text": (
                    f"⚠️ **{top['merchant']}** charged "
                    f"**€{top['amount']:,.2f} twice** "
                    + (
                        f"on {top['second_date'].strftime('%d %B')}"
                        if top["first_date"] == top["second_date"]
                        else f"within {(top['second_date'] - top['first_date']).days} days"
                    )
                    + ". Check whether this was a double charge."
                ),
            }
        )

    # Subscription price changes
    for _, change in price_changes(df, month).iterrows():
        went_up = change["change"] > 0
        insights.append(
            {
                "topic": "price_change",
                "kind": "warning" if went_up else "positive",
                "text": (
                    f"🏷️ **{change['merchant']}** "
                    f"{'went up' if went_up else 'went down'} from "
                    f"€{change['old_amount']:,.2f} to "
                    f"**€{change['new_amount']:,.2f}** "
                    f"({change['change_pct']:+.0%})."
                ),
            }
        )

    # Savings rate vs previous month
    previous = _previous_months(df, month, lookback=1)

    if previous:
        now = calculate_summary(df[df["month"] == month])
        before = calculate_summary(df[df["month"] == previous[0]])

        if now["income"] > 0 and before["income"] > 0:
            difference = now["savings_rate"] - before["savings_rate"]

            if abs(difference) >= 0.05:
                insights.append(
                    {
                        "topic": "savings",
                        "kind": "positive" if difference > 0 else "warning",
                        "text": (
                            f"💰 Your savings rate "
                            f"{'rose' if difference > 0 else 'fell'} to "
                            f"**{now['savings_rate']:.0%}**, from "
                            f"{before['savings_rate']:.0%} last month."
                        ),
                    }
                )

    # New recurring payments
    for _, payment in new_recurring(df, month).iterrows():
        insights.append(
            {
                "topic": "new_recurring",
                "kind": "info",
                "text": (
                    f"🆕 New recurring payment: **{payment['merchant']}**, "
                    f"€{payment['amount']:,.2f} {payment['frequency']}, "
                    f"since {payment['first_date'].strftime('%B')}."
                ),
            }
        )

    if not decreases.empty:
        top = decreases.iloc[0]
        insights.append(
            {
                "topic": "decrease",
                "kind": "positive",
                "text": (
                    f"📉 **{top['category']}** spending is down "
                    f"**€{abs(top['change']):,.2f}** compared with "
                    f"your recent average."
                ),
            }
        )

    # Recurring payments
    recurring = detect_recurring(data_until(df, month))
    active = recurring[recurring["active"]] if not recurring.empty else recurring

    if not active.empty:
        insights.append(
            {
                "topic": "recurring",
                "kind": "info",
                "text": (
                    f"🔁 You have **{len(active)} recurring payments** "
                    f"totalling about **€{active['monthly_cost'].sum():,.2f}"
                    f"/month**."
                ),
            }
        )

    return insights
