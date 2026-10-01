import pandas as pd
import pytest

from categorizer import DEFAULT_CATEGORY_RULES, categorize_dataframe
from flows import classify_flows
from insights import (
    category_changes,
    data_until,
    detect_recurring,
    duplicate_charges,
    key_insights,
    new_recurring,
    price_changes,
    unusual_transactions,
)
from statements import combine_statements, parse_statement
from tests.helpers import SAMPLE_DATA


def month(text):
    return pd.Period(text, "M")


@pytest.fixture
def sample():
    """The multi-month sample, prepared the same way as in the app."""

    with open(SAMPLE_DATA / "finsight_multi_month_sample.csv", "rb") as file:
        _, parsed = parse_statement(file.read())

    df = combine_statements([("sample.csv", parsed)])
    df["category"] = categorize_dataframe(df, DEFAULT_CATEGORY_RULES)
    df["flow"] = classify_flows(df)
    df["month"] = df["date"].dt.to_period("M")

    return df


def make_expenses(rows):
    """rows: (date, description, amount, category)"""

    df = pd.DataFrame(rows, columns=["date", "description", "amount", "category"])
    df["date"] = pd.to_datetime(df["date"])
    df["flow"] = ["income" if amount > 0 else "expense" for amount in df["amount"]]
    df["month"] = df["date"].dt.to_period("M")

    return df


# ------------------------------------------------------------
# Category changes
# ------------------------------------------------------------

def test_august_shopping_spike(sample):
    changes = category_changes(sample, month("2026-08"))

    top = changes.iloc[0]

    assert top["category"] == "Shopping"
    assert top["this_month"] == pytest.approx(389.48)
    # Average of May, June and July
    assert top["average"] == pytest.approx((114.45 + 215.00 + 77.49) / 3, abs=0.01)
    assert top["notable"]


def test_stable_categories_are_not_notable(sample):
    changes = category_changes(sample, month("2026-08")).set_index("category")

    assert not changes.loc["Housing", "notable"]
    assert not changes.loc["Subscriptions", "notable"]


def test_first_month_has_nothing_to_compare(sample):
    assert category_changes(sample, month("2026-03")).empty


def test_small_changes_are_ignored():
    df = make_expenses(
        [
            ("2026-01-05", "Cafe", -5.0, "Restaurants"),
            ("2026-02-05", "Cafe", -10.0, "Restaurants"),
        ]
    )

    # +100%, but only €5: not worth mentioning.
    changes = category_changes(df, month("2026-02"))

    assert not changes.iloc[0]["notable"]


# ------------------------------------------------------------
# Recurring payments
# ------------------------------------------------------------

def test_recurring_payments_in_sample(sample):
    recurring = detect_recurring(sample)

    assert set(recurring["merchant"]) == {
        "DUWO Rent",
        "Health Insurance",
        "Basic Fit",
        "Netflix",
        "Spotify",
    }
    assert set(recurring["frequency"]) == {"monthly"}
    assert recurring["active"].all()

    spotify = recurring.set_index("merchant").loc["Spotify"]

    assert spotify["monthly_cost"] == pytest.approx(10.99)
    assert spotify["next_expected"] == pd.Timestamp("2026-09-05")


def test_frequent_but_irregular_spending_is_not_recurring(sample):
    # Groceries three times a month and train trips are habits,
    # not subscriptions.
    merchants = set(detect_recurring(sample)["merchant"])

    assert "Albert Heijn" not in merchants
    assert "NS Reizen" not in merchants


def test_varying_amounts_are_not_recurring():
    df = make_expenses(
        [
            ("2026-01-10", "Shell", -40.0, "Transport"),
            ("2026-02-10", "Shell", -75.0, "Transport"),
            ("2026-03-10", "Shell", -20.0, "Transport"),
        ]
    )

    assert detect_recurring(df).empty


def test_weekly_payment_is_converted_to_monthly():
    df = make_expenses(
        [
            ("2026-01-05", "Gym class", -10.0, "Other"),
            ("2026-01-12", "Gym class", -10.0, "Other"),
            ("2026-01-19", "Gym class", -10.0, "Other"),
            ("2026-01-26", "Gym class", -10.0, "Other"),
        ]
    )

    recurring = detect_recurring(df)

    assert recurring.iloc[0]["frequency"] == "weekly"
    assert recurring.iloc[0]["monthly_cost"] == pytest.approx(10.0 * 52 / 12, abs=0.01)


def test_stopped_subscription_is_not_active():
    df = make_expenses(
        [
            ("2026-01-01", "Disney Plus", -9.99, "Subscriptions"),
            ("2026-02-01", "Disney Plus", -9.99, "Subscriptions"),
            ("2026-03-01", "Disney Plus", -9.99, "Subscriptions"),
            # Statement continues for months without another payment.
            ("2026-07-15", "Albert Heijn", -40.0, "Groceries"),
        ]
    )

    recurring = detect_recurring(df)

    assert not recurring.iloc[0]["active"]


def test_data_until_excludes_later_months(sample):
    assert data_until(sample, month("2026-05"))["month"].max() == month("2026-05")


# ------------------------------------------------------------
# Unusual transactions
# ------------------------------------------------------------

def test_one_off_hotel_is_unusual(sample):
    unusual = unusual_transactions(sample, month("2026-05"))

    assert unusual["description"].tolist() == ["Weekend Trip Hotel"]


def test_rent_and_subscriptions_are_never_unusual(sample):
    for period in sample["month"].unique():
        unusual = unusual_transactions(sample, period)

        assert "DUWO Rent" not in unusual["description"].tolist()


def test_large_spend_at_a_known_merchant_is_unusual():
    rows = [
        (f"2026-01-{day:02d}", "Albert Heijn", -45.0, "Groceries")
        for day in (3, 10, 17, 24)
    ]
    rows.append(("2026-02-03", "Albert Heijn", -150.0, "Groceries"))

    unusual = unusual_transactions(make_expenses(rows), month("2026-02"))

    assert len(unusual) == 1
    assert unusual.iloc[0]["compared_with"] == "your usual spend at Albert Heijn"
    assert unusual.iloc[0]["multiple"] == pytest.approx(3.3)


def test_normal_restaurant_visit_is_not_unusual(sample):
    # Restaurants are compared with earlier restaurant visits,
    # not with cheap coffees in the same category.
    for period in sample["month"].unique():
        unusual = unusual_transactions(sample, period)

        assert "Restaurant Eindhoven" not in unusual["description"].tolist()


# ------------------------------------------------------------
# Key insights
# ------------------------------------------------------------

def test_august_key_insights(sample):
    insights = key_insights(sample, month("2026-08"))
    topics = [insight["topic"] for insight in insights]

    assert topics[0] == "increase"
    assert "Shopping" in insights[0]["text"]
    assert "recurring" in topics


def test_first_month_key_insights_do_not_crash(sample):
    insights = key_insights(sample, month("2026-03"))

    assert all(insight["topic"] != "increase" for insight in insights)



# ------------------------------------------------------------
# Price changes, new recurring payments, duplicate charges
# ------------------------------------------------------------

@pytest.fixture
def demo():
    """
    insights_demo.csv: the multi-month sample plus a Netflix price rise
    from July, Disney Plus from June and a double Zalando charge in August.
    """

    with open(SAMPLE_DATA / "insights_demo.csv", "rb") as file:
        _, parsed = parse_statement(file.read())

    df = combine_statements([("demo.csv", parsed)])
    df["category"] = categorize_dataframe(df, DEFAULT_CATEGORY_RULES)
    df["flow"] = classify_flows(df)
    df["month"] = df["date"].dt.to_period("M")

    return df


def monthly(description, amounts, category="Subscriptions"):
    """One payment on the 5th of every month, starting January 2026."""
    dates = pd.date_range("2026-01-01", periods=len(amounts), freq="MS") + pd.Timedelta(days=4)

    return [
        (date.strftime("%Y-%m-%d"), description, -amount, category)
        for date, amount in zip(dates, amounts)
    ]


def test_price_increase_is_reported_in_its_month(demo):
    july = price_changes(demo, month("2026-07"))

    assert july["merchant"].tolist() == ["Netflix"]
    assert july.iloc[0]["old_amount"] == pytest.approx(13.99)
    assert july.iloc[0]["new_amount"] == pytest.approx(15.99)

    # Only reported in the month it happened.
    assert price_changes(demo, month("2026-08")).empty


def test_recurring_uses_the_current_price(demo):
    netflix = detect_recurring(demo).set_index("merchant").loc["Netflix"]

    assert netflix["amount"] == pytest.approx(15.99)


def test_large_price_increase_is_still_recurring():
    # 10.99 -> 14.99 is +36%, more than the ±15% allowed for variable
    # bills, but a clear one-step price change.
    df = make_expenses(monthly("Streamly", [10.99, 10.99, 10.99, 14.99]))

    recurring = detect_recurring(df)
    changes = price_changes(df, month("2026-04"))

    assert recurring.iloc[0]["amount"] == pytest.approx(14.99)
    assert changes.iloc[0]["change"] == pytest.approx(4.00)


def test_price_decrease():
    df = make_expenses(monthly("Phone plan", [20.0, 20.0, 15.0]))

    changes = price_changes(df, month("2026-03"))

    assert changes.iloc[0]["change"] == pytest.approx(-5.0)


def test_variable_bill_reports_no_price_changes():
    # Energy varies a little every month: recurring, but no "price changes".
    df = make_expenses(monthly("Energy Co", [92.0, 88.5, 95.2, 90.1], category="Housing"))

    assert len(detect_recurring(df)) == 1

    for period in df["month"].unique():
        assert price_changes(df, period).empty


def test_new_recurring_payment(demo):
    august = new_recurring(demo, month("2026-08"))

    assert august["merchant"].tolist() == ["Disney Plus"]

    # In July it only has two payments, too few to recognize.
    assert new_recurring(demo, month("2026-07")).empty


def test_payments_from_the_start_of_the_statement_are_not_new(demo):
    # Spotify starts in the first month of the statement: it was
    # probably paid before, so it isn't "new".
    for period in demo["month"].unique():
        assert "Spotify" not in new_recurring(demo, period)["merchant"].tolist()


def test_duplicate_charge(demo):
    august = duplicate_charges(demo, month("2026-08"))

    assert august["merchant"].tolist() == ["Zalando"]
    assert august.iloc[0]["amount"] == pytest.approx(110.00)
    assert august.iloc[0]["first_id"] != august.iloc[0]["second_id"]


def test_no_duplicates_in_normal_spending(sample):
    for period in sample["month"].unique():
        assert duplicate_charges(sample, period).empty


def test_small_or_distant_repeats_are_not_duplicates():
    df = make_expenses(
        [
            # Two coffees: same amount, same day, but small.
            ("2026-03-02", "Cafe", -3.50, "Restaurants"),
            ("2026-03-02", "Cafe", -3.50, "Restaurants"),
            # Same amount a week apart: a habit, not a double charge.
            ("2026-03-03", "Yoga Studio", -20.00, "Other"),
            ("2026-03-10", "Yoga Studio", -20.00, "Other"),
        ]
    )

    assert duplicate_charges(df, month("2026-03")).empty


def test_three_identical_charges_count_as_one_pair_plus_one():
    df = make_expenses(
        [
            ("2026-03-02", "Webshop", -40.0, "Shopping"),
            ("2026-03-02", "Webshop", -40.0, "Shopping"),
            ("2026-03-03", "Webshop", -40.0, "Shopping"),
        ]
    )

    # The first two pair up; the third has no partner left within
    # two days of a charge that isn't already paired.
    assert len(duplicate_charges(df, month("2026-03"))) == 1


def test_demo_key_insights(demo):
    july = [insight["topic"] for insight in key_insights(demo, month("2026-07"))]
    august = [insight["topic"] for insight in key_insights(demo, month("2026-08"))]

    assert "price_change" in july
    assert "duplicate" in august
    assert "new_recurring" in august


# ------------------------------------------------------------
# Month-end forecast
# ------------------------------------------------------------

from insights import month_end_forecast  # noqa: E402


def test_no_forecast_for_complete_months(demo):
    # The demo statement runs to 30 August: August counts as complete.
    assert month_end_forecast(demo, month("2026-08")) is None
    assert month_end_forecast(demo, month("2026-05")) is None


def test_forecast_halfway_through_a_month(demo):
    halfway = demo[demo["date"] <= "2026-08-15"]

    forecast = month_end_forecast(halfway, month("2026-08"))

    assert forecast["days_elapsed"] == 15
    assert forecast["forecast"] == pytest.approx(
        forecast["spent_so_far"]
        + forecast["recurring_due"]
        + forecast["variable_remaining"]
    )
    # Health insurance (27th) and Netflix (18th) are still due.
    assert forecast["recurring_due"] == pytest.approx(131.40 + 15.99)
    # Average of May, June and July.
    assert forecast["usual"] is not None


def test_rent_is_not_projected_as_daily_spending(demo):
    halfway = demo[demo["date"] <= "2026-08-15"]

    forecast = month_end_forecast(halfway, month("2026-08"))

    # Rent was paid once on the 2nd; it must stay €650, not double.
    assert forecast["by_category"]["Housing"] == pytest.approx(650.0)


def test_forecast_category_totals_add_up(demo):
    halfway = demo[demo["date"] <= "2026-08-15"]

    forecast = month_end_forecast(halfway, month("2026-08"))

    assert forecast["by_category"].sum() == pytest.approx(forecast["forecast"], abs=0.05)


def test_forecast_only_for_the_latest_month(demo):
    halfway = demo[demo["date"] <= "2026-08-15"]

    assert month_end_forecast(halfway, month("2026-07")) is None
