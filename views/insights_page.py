"""Insights page: what changed, what repeats, and what stands out."""

import streamlit as st

from analytics import calculate_summary
from charts import create_category_comparison_chart
from insights import LOOKBACK_MONTHS
from ui import (
    category_changes,
    duplicate_charges,
    key_insights,
    month_selector,
    new_recurring,
    price_changes,
    recurring_until,
    require_data,
    show_insight,
    unusual_transactions,
)


def render(data):
    df = data.df

    st.title(
        "Insights"
    )

    st.caption(
        "What changed, what repeats, and what stands out."
    )

    if require_data(df):

        selected_month = month_selector(
            df,
            key="insights_month",
        )

        month_name = selected_month.strftime("%B %Y")

        # ----------------------------------------------------
        # KEY INSIGHTS
        # ----------------------------------------------------

        st.subheader("Key Insights")

        insights_list = key_insights(df, selected_month)

        if insights_list:
            insight_columns = st.columns(2)

            for position, insight in enumerate(insights_list):
                show_insight(
                    insight_columns[position % 2],
                    insight,
                )
        else:
            st.info(
                f"Nothing stands out in {month_name}."
            )

        # ----------------------------------------------------
        # SPENDING VS RECENT AVERAGE
        # ----------------------------------------------------

        st.subheader("Spending vs. Your Recent Average")

        changes = category_changes(df, selected_month)

        if changes.empty:
            st.info(
                f"{month_name} is the first month in your "
                "statements, so there is nothing to compare "
                "it with yet."
            )

        else:
            compared_months = sorted(
                month
                for month in df["month"].dropna().unique()
                if month < selected_month
            )[-LOOKBACK_MONTHS:]

            st.caption(
                f"{month_name} compared with your average over "
                f"{compared_months[0].strftime('%B')}"
                + (
                    f" – {compared_months[-1].strftime('%B %Y')}."
                    if len(compared_months) > 1
                    else f" {compared_months[0].strftime('%Y')}."
                )
            )

            notable = changes[
                changes["notable"].astype(bool)
            ].head(4)

            if not notable.empty:
                change_columns = st.columns(4)

                for column, (_, row) in zip(
                    change_columns,
                    notable.iterrows(),
                ):
                    if row["change_pct"] is not None:
                        delta = (
                            f"{row['change_pct']:+.0%} vs "
                            f"€{row['average']:,.0f} avg"
                        )
                    else:
                        delta = "New this month"

                    column.metric(
                        row["category"],
                        f"€{row['this_month']:,.2f}",
                        delta=delta,
                        # More spending is shown in red.
                        delta_color="inverse",
                    )

            st.plotly_chart(
                create_category_comparison_chart(changes),
                width="stretch",
                config={
                    "displayModeBar": False,
                },
            )

        # ----------------------------------------------------
        # RECURRING PAYMENTS
        # ----------------------------------------------------

        st.subheader("Recurring Payments")

        recurring = recurring_until(
            df,
            selected_month,
        )

        if recurring.empty:
            st.info(
                "No recurring payments found yet. Finsight needs "
                "at least three payments to the same merchant at "
                "a regular interval."
            )

        else:
            active = recurring[recurring["active"]]
            stopped = recurring[~recurring["active"]]

            total_col, count_col, subs_col, _ = st.columns(4)

            total_col.metric(
                "Recurring per Month",
                f"€{active['monthly_cost'].sum():,.2f}",
                help=(
                    "Subscriptions, rent, insurance and other "
                    "payments that repeat for a similar amount. "
                    "Weekly and yearly payments are converted to "
                    "a monthly cost."
                ),
            )

            count_col.metric(
                "Recurring Payments",
                f"{len(active)}",
            )

            income = calculate_summary(
                df[df["month"] == selected_month]
            )["income"]

            if income > 0:
                subs_col.metric(
                    "Share of Income",
                    f"{active['monthly_cost'].sum() / income:.0%}",
                    help=(
                        f"Recurring payments as a share of your "
                        f"income in {month_name}."
                    ),
                )

            st.dataframe(
                active[
                    [
                        "merchant",
                        "category",
                        "amount",
                        "frequency",
                        "monthly_cost",
                        "next_expected",
                    ]
                ].rename(
                    columns={
                        "merchant": "Merchant",
                        "category": "Category",
                        "amount": "Amount (€)",
                        "frequency": "Frequency",
                        "monthly_cost": "Per month (€)",
                        "next_expected": "Next expected",
                    }
                ),
                width="stretch",
                hide_index=True,
            )

            if not stopped.empty:
                st.caption(
                    "Possibly stopped (no recent payment): "
                    + ", ".join(stopped["merchant"])
                    + "."
                )

        for _, change in price_changes(df, selected_month).iterrows():
            message = (
                f"🏷️ **{change['merchant']}** "
                f"{'went up' if change['change'] > 0 else 'went down'} "
                f"from €{change['old_amount']:,.2f} to "
                f"**€{change['new_amount']:,.2f}** "
                f"({change['change_pct']:+.0%}) on "
                f"{change['date'].strftime('%d %B')}."
            )

            if change["change"] > 0:
                st.warning(message)
            else:
                st.success(message)

        for _, payment in new_recurring(df, selected_month).iterrows():
            st.info(
                f"🆕 **{payment['merchant']}** is a new recurring payment: "
                f"€{payment['amount']:,.2f} {payment['frequency']}, "
                f"first paid on {payment['first_date'].strftime('%d %B')}."
            )

        # ----------------------------------------------------
        # UNUSUAL SPENDING
        # ----------------------------------------------------

        st.subheader("Unusual Spending")

        unusual = unusual_transactions(df, selected_month)
        duplicates = duplicate_charges(df, selected_month)

        for _, pair in duplicates.iterrows():
            when = (
                f"on {pair['second_date'].strftime('%d %B')}"
                if pair["first_date"] == pair["second_date"]
                else (
                    f"on {pair['first_date'].strftime('%d')} and "
                    f"{pair['second_date'].strftime('%d %B')}"
                )
            )

            st.warning(
                f"⚠️ **Possible double charge:** {pair['merchant']} "
                f"charged **€{pair['amount']:,.2f}** twice {when}. "
                "If you only bought once, contact the merchant or "
                "your bank."
            )

        if unusual.empty and duplicates.empty:
            st.success(
                f"Nothing unusual in {month_name}."
            )

        else:
            for _, row in unusual.iterrows():
                st.warning(
                    f"🔎 **{row['description']}** on "
                    f"{row['date'].strftime('%d %B')}: "
                    f"**€{abs(row['amount']):,.2f}**, "
                    f"{row['multiple']:.1f}x "
                    f"{row['compared_with']} "
                    f"(about €{row['typical']:,.2f})."
                )
