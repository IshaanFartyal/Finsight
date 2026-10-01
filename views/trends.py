"""Trends page: income, expenses and savings over time."""

import streamlit as st

from charts import create_monthly_trends_chart
from ui import require_data


def render(data):
    df = data.df
    monthly_finances = data.monthly_finances

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
