from copy import deepcopy

import streamlit as st
from pandas.errors import ParserError

from analytics import (
    calculate_spending_by_category,
    calculate_summary,
)
from categorizer import (
    DEFAULT_CATEGORY_RULES,
    categorize_transaction,
)
from charts import (
    create_category_donut,
    create_income_expense_chart,
    create_monthly_trends_chart,
)
from parsers.detector import detect_bank
from parsers.generic import parse_generic
from parsers.ing import parse_ing
from parsers.loader import load_bank_csv
from parsers.revolut import parse_revolut
from parsers.wise import parse_wise

# ============================================================
# PAGE SETUP
# ============================================================

st.set_page_config(
    page_title="Finsight",
    page_icon="💰",
    layout="wide",
)


# ============================================================
# HELPERS
# ============================================================

def load_css(file_path):
    """Load the external Finsight stylesheet."""
    with open(file_path, encoding="utf-8") as css_file:
        st.markdown(
            f"<style>{css_file.read()}</style>",
            unsafe_allow_html=True,
        )


def require_data(df):
    """Show a message when no bank statement has been uploaded."""
    if df is None:
        st.info(
            "Upload a bank statement from the sidebar "
            "to start using Finsight."
        )
        return False

    return True


def build_monthly_finances(df):
    """Create monthly income, expense, and savings totals."""
    monthly_finances = (
        df.groupby("month")["amount"]
        .agg(
            income=lambda values: values[values > 0].sum(),
            expenses=lambda values: abs(
                values[values < 0].sum()
            ),
        )
        .reset_index()
    )

    monthly_finances["savings"] = (
        monthly_finances["income"]
        - monthly_finances["expenses"]
    )

    monthly_finances["month"] = (
        monthly_finances["month"]
        .astype(str)
    )

    return monthly_finances


load_css("styles/style.css")


# ============================================================
# SESSION STATE
# ============================================================

if "category_rules" not in st.session_state:
    st.session_state.category_rules = deepcopy(
        DEFAULT_CATEGORY_RULES
    )


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.markdown(
    """
    <div class="sidebar-brand">
        <div class="sidebar-logo">⌁</div>
        <div>
            <div class="sidebar-title">Finsight</div>
            <div class="sidebar-tagline">
                Your finances, in focus.
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

page = st.sidebar.radio(
    "Navigation",
    [
        "Overview",
        "Transactions",
        "Categories",
        "Trends",
        "Insights",
        "Settings",
    ],
    label_visibility="collapsed",
)

st.sidebar.divider()

uploaded_file = st.sidebar.file_uploader(
    "Import bank statement",
    type=["csv"],
    key="bank_statement",
)


# ============================================================
# LOAD + PARSE FILE
# ============================================================

df = None
bank = None
monthly_finances = None

if uploaded_file is not None:

    try:
        raw_df = load_bank_csv(uploaded_file)

        bank = detect_bank(raw_df)

        if bank == "revolut":
            df = parse_revolut(raw_df)

        elif bank == "wise":
            df = parse_wise(raw_df)

        elif bank == "ing":
            df = parse_ing(raw_df)

        else:
            df = parse_generic(raw_df)

        # Categorize transactions using the user's current rules.
        df["category"] = df["description"].apply(
            lambda description: categorize_transaction(
                description,
                st.session_state.category_rules,
            )
        )

        # Used for filtering and monthly analytics.
        df["month"] = df["date"].dt.to_period("M")

        monthly_finances = build_monthly_finances(df)

    except (
        ValueError,
        UnicodeDecodeError,
        ParserError,
    ) as error:

        st.error(
            "Statement could not be interpreted."
        )

        st.caption(
            f"Reason: {error}"
        )

        df = None
        monthly_finances = None


# ============================================================
# OVERVIEW
# ============================================================

if page == "Overview":

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

        if bank == "unknown":
            st.warning(
                "Bank format was not recognized. "
                "Finsight is using its generic parser, "
                "so results may be less reliable."
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
            if bank == "unknown":
                st.caption("Bank: Undetected")
            else:
                st.caption(
                    f"Bank: {bank.title()}"
                )

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

        insight3.info(
            "✨ More personalized insights will "
            "appear here as Finsight develops."
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


# ============================================================
# TRANSACTIONS
# ============================================================

elif page == "Transactions":

    st.title(
        "Transactions"
    )

    st.caption(
        "Browse and review your imported transactions."
    )

    if require_data(df):

        available_months = sorted(
            df["month"].dropna().unique(),
            reverse=True,
        )

        selected_month = st.selectbox(
            "Month",
            available_months,
            format_func=lambda month: month.strftime(
                "%B %Y"
            ),
            key="transactions_month",
        )

        transaction_df = df[
            df["month"] == selected_month
        ].copy()

        transaction_df = (
            transaction_df.sort_values(
                "date",
                ascending=False,
            )
        )

        st.dataframe(
            transaction_df[
                [
                    "date",
                    "description",
                    "category",
                    "amount",
                    "currency",
                    "transaction_type",
                ]
            ],
            width="stretch",
            hide_index=True,
        )


# ============================================================
# CATEGORIES
# ============================================================

elif page == "Categories":

    st.title(
        "Categories"
    )

    st.caption(
        "Customize how Finsight categorizes "
        "your transactions."
    )

    st.subheader(
        "Category Rules"
    )

    for (
        category,
        keywords,
    ) in st.session_state.category_rules.items():

        with st.expander(category):

            keyword_text = st.text_area(
                f"Keywords for {category}",
                value=", ".join(keywords),
                key=f"keywords_{category}",
            )

            updated_keywords = [
                keyword.strip()
                for keyword
                in keyword_text.split(",")
                if keyword.strip()
            ]

            st.session_state.category_rules[
                category
            ] = updated_keywords

    st.divider()

    st.subheader(
        "Add Category"
    )

    add_col1, add_col2 = st.columns(2)

    with add_col1:
        new_category = st.text_input(
            "Category name"
        )

    with add_col2:
        new_keywords = st.text_input(
            "Keywords",
            placeholder=(
                "GYM, BASIC FIT, SPORTCITY"
            ),
        )

    button_col1, button_col2 = (
        st.columns(2)
    )

    with button_col1:
        if (
            st.button("Add Category")
            and new_category
        ):
            keyword_list = [
                keyword.strip()
                for keyword
                in new_keywords.split(",")
                if keyword.strip()
            ]

            st.session_state.category_rules[
                new_category
            ] = keyword_list

            st.rerun()

    with button_col2:
        if st.button(
            "Reset Categories"
        ):
            st.session_state.category_rules = (
                deepcopy(
                    DEFAULT_CATEGORY_RULES
                )
            )

            st.rerun()


# ============================================================
# TRENDS
# ============================================================

elif page == "Trends":

    st.title(
        "Trends"
    )

    st.caption(
        "See how your finances change over time."
    )

    if require_data(df):

        if (
            monthly_finances is not None
            and not monthly_finances.empty
        ):
            trends_fig = (
                create_monthly_trends_chart(
                    monthly_finances
                )
            )

            st.plotly_chart(
                trends_fig,
                width="stretch",
                config={
                    "displayModeBar": False,
                },
            )

        else:
            st.info(
                "No monthly trend data available."
            )


# ============================================================
# INSIGHTS
# ============================================================

elif page == "Insights":

    st.title(
        "Insights"
    )

    st.caption(
        "Deeper financial insights will live here."
    )

    if require_data(df):

        st.info(
            "Future features could include "
            "month-over-month comparisons, "
            "recurring payment detection, "
            "unusual spending detection, "
            "and AI-generated insights."
        )


# ============================================================
# SETTINGS
# ============================================================

elif page == "Settings":

    st.title(
        "Settings"
    )

    st.caption(
        "Manage your Finsight preferences."
    )

    st.info(
        "Settings will be added as Finsight grows."
    )
