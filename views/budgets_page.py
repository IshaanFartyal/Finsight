"""
Budgets & Goals page: monthly budgets per category and savings goals.
"""

import pandas as pd
import streamlit as st

from analytics import calculate_spending_by_category
from budgets import (
    AT_RISK,
    OVER,
    average_monthly_savings,
    budget_status,
    clean_goal,
    goal_plan,
    goals_table,
    save_budgets,
)
from ui import (
    month_end_forecast,
    month_selector,
    persist,
    storage_note,
)

BUDGET_EDITOR_KEY = "budgets_editor"
GOALS_EDITOR_KEY = "goals_editor"

# Categories that are never spending, so never budgeted.
NOT_BUDGETABLE = {"Income", "Transfer", "Savings & Investments"}


def _save(data, editor_key):
    persist(save_budgets, data)
    st.session_state.budgets = data

    # The editor is rebuilt from the saved data on the next run.
    st.session_state.pop(editor_key, None)

    st.rerun()


def _budget_categories(df):
    categories = list(st.session_state.category_rules)

    if df is not None:
        categories += sorted(set(df["category"]) - set(categories))

    for extra in ("Other", "Fees"):
        if extra not in categories:
            categories.append(extra)

    return [
        category
        for category in categories
        if category not in NOT_BUDGETABLE
    ]


def _render_budgets(df, data):
    st.subheader("Monthly Budgets")

    st.caption(
        "Set a monthly limit for the categories you want to keep an eye "
        "on. Leave the others empty."
    )

    budgets = data["budgets"]
    categories = _budget_categories(df)
    categories += sorted(set(budgets) - set(categories))

    editor_col, status_col = st.columns([1, 2])

    with editor_col:
        edited = st.data_editor(
            pd.DataFrame(
                {
                    "category": categories,
                    "budget": [budgets.get(category) for category in categories],
                }
            ).astype({"budget": "float"}),
            key=BUDGET_EDITOR_KEY,
            hide_index=True,
            disabled=["category"],
            column_config={
                "category": "Category",
                "budget": st.column_config.NumberColumn(
                    "Budget per month (€)",
                    min_value=0.0,
                    step=10.0,
                    format="%.0f",
                ),
            },
        )

    updated = {
        row["category"]: float(row["budget"])
        for _, row in edited.iterrows()
        if pd.notna(row["budget"]) and row["budget"] > 0
    }

    if updated != budgets:
        _save({**data, "budgets": updated}, BUDGET_EDITOR_KEY)

    with status_col:
        if not budgets:
            st.info("No budgets set yet.")
            return

        if df is None:
            st.info("Upload statements to see how you're doing.")
            return

        selected_month = month_selector(df, key="budgets_month")
        month_df = df[df["month"] == selected_month]

        forecast = month_end_forecast(df, selected_month)

        status = budget_status(
            calculate_spending_by_category(month_df),
            budgets,
            forecast["by_category"] if forecast else None,
        )

        if forecast:
            st.caption(
                f"{selected_month.strftime('%B')} isn't over yet: "
                f"projections use your statements up to "
                f"{forecast['as_of'].strftime('%d %B')}."
            )

        for _, row in status.iterrows():
            icon = {"over": "🔴", "at risk": "🟠"}.get(row["status"], "🟢")

            st.progress(
                min(row["share_used"], 1.0),
                text=(
                    f"{icon} **{row['category']}**: €{row['spent']:,.0f} of "
                    f"€{row['budget']:,.0f}"
                    + (
                        f" (€{-row['remaining']:,.0f} over)"
                        if row["status"] == OVER
                        else f" (€{row['remaining']:,.0f} left)"
                    )
                ),
            )

            if (
                row["status"] == AT_RISK
                and row["projected"] is not None
                and row["projected"] > row["budget"]
            ):
                st.caption(
                    f"Heading for about €{row['projected']:,.0f} by the "
                    f"end of the month."
                )


def _render_goals(df, data):
    st.subheader("Savings Goals")

    st.caption(
        "Add a goal with a target amount and date. In \"Saved so far\", "
        "enter what you've already put aside for it."
    )

    goals = data["goals"]

    edited = st.data_editor(
        goals_table(goals),
        key=GOALS_EDITOR_KEY,
        hide_index=True,
        num_rows="dynamic",
        width="stretch",
        column_config={
            "name": st.column_config.TextColumn("Goal", required=True),
            "target": st.column_config.NumberColumn(
                "Target (€)",
                min_value=0.0,
                step=100.0,
                format="%.0f",
                required=True,
            ),
            "deadline": st.column_config.DateColumn(
                "By",
                format="D MMM YYYY",
                required=True,
            ),
            "saved": st.column_config.NumberColumn(
                "Saved so far (€)",
                min_value=0.0,
                step=50.0,
                format="%.0f",
            ),
        },
    )

    # Rows still being typed in are incomplete and simply skipped.
    updated = [
        goal
        for goal in (
            clean_goal(row.to_dict())
            for _, row in edited.iterrows()
        )
        if goal is not None
    ]

    if updated != goals:
        _save({**data, "goals": updated}, GOALS_EDITOR_KEY)

    if not goals:
        return

    average, months_used = average_monthly_savings(df)

    if average is not None:
        st.caption(
            f"You saved on average **€{average:,.0f}/month** over "
            f"{', '.join(month.strftime('%B') for month in months_used)}."
        )

    for goal in goals:
        plan = goal_plan(goal, average)

        st.markdown(f"**{goal['name']}**")

        st.progress(
            plan["progress"],
            text=(
                f"€{goal['saved']:,.0f} of €{goal['target']:,.0f} saved, "
                f"by {pd.Timestamp(goal['deadline']).strftime('%d %B %Y')}"
            ),
        )

        if plan["reached"]:
            st.success("🎉 Goal reached!")

        elif plan["deadline_passed"]:
            st.warning(
                f"The deadline has passed with €{plan['remaining']:,.0f} "
                "still to save. Set a new date to see a new plan."
            )

        else:
            needed_col, average_col, months_col = st.columns(3)

            needed_col.metric(
                "Needed per Month",
                f"€{plan['needed_per_month']:,.0f}",
            )

            if average is not None:
                average_col.metric(
                    "You Save per Month",
                    f"€{average:,.0f}",
                )

            months_col.metric(
                "Months Left",
                f"{plan['months_left']:.1f}",
            )

            if plan["on_track"] is True:
                st.success(
                    "✅ On track: your average savings cover the "
                    f"€{plan['needed_per_month']:,.0f}/month this goal needs."
                )

            elif plan["on_track"] is False:
                st.warning(
                    f"⚠️ €{plan['gap_per_month']:,.0f}/month short. "
                    "Save more each month, lower the target or move the "
                    "date to stay on track."
                )

            else:
                st.info(
                    "Upload statements to compare this with what you "
                    "actually save."
                )


def render(data):
    df = data.df

    st.title(
        "Budgets & Goals"
    )

    st.caption(
        "Set monthly limits and savings targets. "
        + storage_note()
    )

    budgets_data = st.session_state.budgets

    _render_budgets(df, budgets_data)

    st.divider()

    _render_goals(df, st.session_state.budgets)
