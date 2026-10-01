"""Overview page: the selected month at a glance."""

import streamlit as st

from analytics import (
    calculate_spending_by_category,
    calculate_summary,
)
from charts import (
    create_category_donut,
    create_income_expense_chart,
)
from currency import foreign_currencies
from ui import (
    BANK_NAMES,
    key_insights,
    month_end_forecast,
    require_data,
    show_insight,
)


def render(data):
    df = data.df
    monthly_finances = data.monthly_finances
    loaded_files = data.loaded_files

    st.markdown(
        """
        <div class="page-header">
            <h1>Finsight</h1>
            <p>Your finances, in focus.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if require_data(df):

        unknown_files = [
            file_name
            for file_name, bank in loaded_files.items()
            if bank == "unknown"
        ]

        if unknown_files:
            st.warning(
                "Bank format was not recognized for "
                f"{', '.join(unknown_files)}. "
                "Finsight is using its generic parser, "
                "so results may be less reliable."
            )

        # Currencies still without an exchange rate (left unconverted)
        missing_rates = foreign_currencies(df)

        if missing_rates:
            st.warning(
                "Some transactions are in "
                f"{', '.join(missing_rates)}. They are counted as if they "
                "were euros until you set an exchange rate in Settings."
            )

        converted = sorted(
            set(df.loc[df["original_currency"] != df["currency"], "original_currency"])
        )

        if converted:
            st.caption(
                f"Amounts in {', '.join(converted)} are converted to euros "
                "using the exchange rates in Settings."
            )

        # ----------------------------------------------------
        # MONTH SELECTOR
        # ----------------------------------------------------

        available_months = sorted(
            df["month"].dropna().unique(),
            reverse=True,
        )

        selector_col, bank_col = st.columns(
            [3, 1]
        )

        with selector_col:
            selected_month = st.selectbox(
                "Month",
                available_months,
                format_func=lambda month: month.strftime(
                    "%B %Y"
                ),
            )

        with bank_col:
            banks = sorted(
                {
                    BANK_NAMES.get(bank, bank)
                    for bank in loaded_files.values()
                }
            )
            label = "Bank" if len(banks) == 1 else "Banks"
            st.caption(f"{label}: {', '.join(banks)}")

        monthly_df = df[
            df["month"] == selected_month
        ].copy()

        # ----------------------------------------------------
        # SELECTED-MONTH ANALYTICS
        # ----------------------------------------------------

        summary = calculate_summary(
            monthly_df
        )

        spending_by_category = (
            calculate_spending_by_category(
                monthly_df
            )
        )

        # ----------------------------------------------------
        # MONTH HEADER
        # ----------------------------------------------------

        st.markdown(
            f"""
            <div class="overview-heading">
                <h2>
                    {selected_month.strftime("%B %Y")} Overview
                </h2>
                <p>
                    Here's an overview of your finances
                    for the selected month.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ----------------------------------------------------
        # KPI CARDS
        # ----------------------------------------------------

        col1, col2, col3, col4 = st.columns(4)

        col1.metric(
            "Total Income",
            f"€{summary['income']:,.2f}",
        )

        col2.metric(
            "Total Expenses",
            f"€{summary['expenses']:,.2f}",
        )

        col3.metric(
            "Savings",
            f"€{summary['savings']:,.2f}",
        )

        col4.metric(
            "Savings Rate",
            f"{summary['savings_rate']:.1%}",
        )

        # ----------------------------------------------------
        # ADJUSTMENT CARDS
        # Only shown when they apply, so a single-account user
        # without refunds or fees sees no empty cards.
        # ----------------------------------------------------

        moved = max(
            summary["transfers_in"],
            summary["transfers_out"],
        )

        adjustment_cards = []

        # (label, value, explanation, delta)
        forecast = month_end_forecast(df, selected_month)

        if forecast:
            delta = None

            if forecast["usual"]:
                delta = (
                    f"{forecast['forecast'] - forecast['usual']:+,.0f} € "
                    "vs usual"
                )

            adjustment_cards.append(
                (
                    "Projected Spending",
                    f"€{forecast['forecast']:,.2f}",
                    f"Estimated total for "
                    f"{selected_month.strftime('%B')}, based on your "
                    f"statements up to {forecast['as_of'].strftime('%d %B')}: "
                    f"€{forecast['spent_so_far']:,.0f} spent so far, "
                    f"€{forecast['recurring_due']:,.0f} in recurring payments "
                    f"still due, and €{forecast['variable_remaining']:,.0f} "
                    "of everyday spending at your current pace.",
                    delta,
                )
            )

        if moved > 0:
            adjustment_cards.append(
                (
                    "Moved Between Accounts",
                    f"€{moved:,.2f}",
                    "Transfers between your own accounts. "
                    "Not counted as income or expenses.",
                    None,
                )
            )

        if summary["refunds"] > 0:
            adjustment_cards.append(
                (
                    "Refunds",
                    f"€{summary['refunds']:,.2f}",
                    "Money back from merchants. Deducted from "
                    "expenses and from the category it belongs to.",
                    None,
                )
            )

        if summary["fees"] > 0:
            adjustment_cards.append(
                (
                    "Bank Fees",
                    f"€{summary['fees']:,.2f}",
                    "Fees charged on top of transactions. "
                    "Included in expenses.",
                    None,
                )
            )

        if adjustment_cards:
            # Same four-column grid as the cards above,
            # so the cards line up.
            card_columns = st.columns(4)

            for column, (label, value, explanation, delta) in zip(
                card_columns,
                adjustment_cards,
            ):
                column.metric(
                    label,
                    value,
                    delta=delta,
                    # Spending more than usual is shown in red.
                    delta_color="inverse",
                    help=explanation,
                )

        # ----------------------------------------------------
        # PLOTLY CHART ROW
        # ----------------------------------------------------

        chart_col1, chart_col2 = st.columns(
            [1.15, 1]
        )

        with chart_col1:
            st.subheader(
                "Income vs. Expenses"
            )

            if (
                monthly_finances is not None
                and not monthly_finances.empty
            ):
                income_expense_fig = (
                    create_income_expense_chart(
                        monthly_finances
                    )
                )

                st.plotly_chart(
                    income_expense_fig,
                    width="stretch",
                    config={
                        "displayModeBar": False,
                    },
                )

            else:
                st.info(
                    "No monthly financial data available."
                )

        with chart_col2:
            st.subheader(
                "Spending by Category"
            )

            if not spending_by_category.empty:
                category_fig = (
                    create_category_donut(
                        spending_by_category,
                        summary["expenses"],
                    )
                )

                st.plotly_chart(
                    category_fig,
                    width="stretch",
                    config={
                        "displayModeBar": False,
                    },
                )

            else:
                st.info(
                    "No spending transactions found."
                )

        # ----------------------------------------------------
        # KEY INSIGHTS
        # ----------------------------------------------------

        st.subheader(
            "Key Insights"
        )

        insight1, insight2, insight3 = (
            st.columns(3)
        )

        if not spending_by_category.empty:
            largest_category = (
                spending_by_category.idxmax()
            )

            largest_amount = (
                spending_by_category.max()
            )

            insight1.info(
                f"💳 Your largest spending category "
                f"was **{largest_category}** at "
                f"**€{largest_amount:,.2f}**."
            )

        else:
            insight1.info(
                "💳 No spending categories are "
                "available for this month."
            )

        if summary["savings_rate"] >= 0.20:
            insight2.success(
                f"💰 You saved "
                f"**{summary['savings_rate']:.0%}** "
                f"of your income this month."
            )

        else:
            insight2.warning(
                f"💡 Your savings rate was "
                f"**{summary['savings_rate']:.0%}** "
                f"this month."
            )

        # The most notable finding that isn't already shown
        # in the savings-rate bubble next to it.
        overview_insights = [
            insight
            for insight in key_insights(df, selected_month)
            if insight["topic"] != "savings"
        ]

        if overview_insights:
            show_insight(insight3, overview_insights[0])
        else:
            insight3.info(
                "✨ Nothing stands out this month. "
                "See Insights for the details."
            )

        # ----------------------------------------------------
        # RECENT TRANSACTIONS
        # ----------------------------------------------------

        st.subheader(
            "Recent Transactions"
        )

        transaction_view = monthly_df[
            [
                "date",
                "description",
                "category",
                "flow",
                "amount",
            ]
        ].copy()

        transaction_view = (
            transaction_view.sort_values(
                "date",
                ascending=False,
            )
        )

        st.dataframe(
            transaction_view.head(10),
            width="stretch",
            hide_index=True,
        )
