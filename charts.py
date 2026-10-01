import plotly.graph_objects as go

FINSIGHT_COLORS = {
    "green": "#19e6b3",
    "red": "#ff5c78",
    "blue": "#35a7ff",
    "purple": "#9b6dff",
    "orange": "#ffad4d",
    "teal": "#59d4b3",
    "grey": "#91a7c2",
    "pink": "#f06df2",
}


def style_plotly_chart(fig):
    """
    Apply the Finsight dark theme to a Plotly chart.
    """

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={
            "color": "#dbe7f3",
            "family": "Arial",
        },
        margin={
            "l": 20,
            "r": 20,
            "t": 20,
            "b": 20,
        },
        hoverlabel={
            "bgcolor": "#10243a",
            "font_color": "#ffffff",
            "bordercolor": "#1d3958",
        },
    )

    fig.update_xaxes(
        showgrid=False,
        zeroline=False,
    )

    fig.update_yaxes(
        gridcolor="rgba(130,151,173,0.15)",
        zeroline=False,
    )

    return fig


def create_income_expense_chart(monthly_finances):
    """
    Create a grouped bar chart showing
    monthly income vs expenses.
    """

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=monthly_finances["month"],
            y=monthly_finances["income"],
            name="Income",
            marker_color=FINSIGHT_COLORS["green"],
            hovertemplate=(
                "Income: €%{y:,.2f}"
                "<extra></extra>"
            ),
        )
    )

    fig.add_trace(
        go.Bar(
            x=monthly_finances["month"],
            y=monthly_finances["expenses"],
            name="Expenses",
            marker_color=FINSIGHT_COLORS["red"],
            hovertemplate=(
                "Expenses: €%{y:,.2f}"
                "<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        barmode="group",
        height=300,
        bargap=0.25,
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
        },
    )

    fig.update_yaxes(
        tickprefix="€",
    )

    return style_plotly_chart(fig)


def create_category_donut(
    spending_by_category,
    total_expenses,
):
    """
    Create a donut chart showing spending
    distribution by category.
    """

    category_names = (
        spending_by_category.index.tolist()
    )

    category_values = (
        spending_by_category.values.tolist()
    )

    colors = [
        FINSIGHT_COLORS["green"],
        FINSIGHT_COLORS["blue"],
        FINSIGHT_COLORS["purple"],
        FINSIGHT_COLORS["orange"],
        FINSIGHT_COLORS["red"],
        FINSIGHT_COLORS["teal"],
        FINSIGHT_COLORS["grey"],
        FINSIGHT_COLORS["pink"],
    ]

    fig = go.Figure(
        data=[
            go.Pie(
                labels=category_names,
                values=category_values,
                hole=0.62,
                textinfo="none",
                hovertemplate=(
                    "<b>%{label}</b><br>"
                    "€%{value:,.2f}<br>"
                    "%{percent}"
                    "<extra></extra>"
                ),
                marker={
                    "colors": colors,
                },
            )
        ]
    )

    fig.update_layout(
        height=300,
        showlegend=True,
        legend={
            "orientation": "v",
            "yanchor": "middle",
            "y": 0.5,
            "xanchor": "left",
            "x": 1,
        },
        annotations=[
            {
                "text": (
                    f"€{total_expenses:,.0f}"
                    "<br>"
                    "<span style='font-size:11px'>"
                    "Total spent"
                    "</span>"
                ),
                "x": 0.5,
                "y": 0.5,
                "font": {
                    "size": 18,
                    "color": "#ffffff",
                },
                "showarrow": False,
            }
        ],
    )

    return style_plotly_chart(fig)


def create_monthly_trends_chart(
    monthly_finances,
):
    """
    Create a line chart showing
    income, expenses, and savings over time.
    """

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=monthly_finances["month"],
            y=monthly_finances["income"],
            mode="lines+markers",
            name="Income",
            line={
                "color": FINSIGHT_COLORS["green"],
                "width": 3,
            },
            marker={
                "size": 7,
            },
            hovertemplate=(
                "Income: €%{y:,.2f}"
                "<extra></extra>"
            ),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=monthly_finances["month"],
            y=monthly_finances["expenses"],
            mode="lines+markers",
            name="Expenses",
            line={
                "color": FINSIGHT_COLORS["red"],
                "width": 3,
            },
            marker={
                "size": 7,
            },
            hovertemplate=(
                "Expenses: €%{y:,.2f}"
                "<extra></extra>"
            ),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=monthly_finances["month"],
            y=monthly_finances["savings"],
            mode="lines+markers",
            name="Savings",
            line={
                "color": FINSIGHT_COLORS["blue"],
                "width": 3,
            },
            marker={
                "size": 7,
            },
            hovertemplate=(
                "Savings: €%{y:,.2f}"
                "<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        height=350,
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
        },
    )

    fig.update_yaxes(
        tickprefix="€",
    )

    return style_plotly_chart(fig)

def create_category_comparison_chart(changes):
    """
    Horizontal bars: each category's spending this month next to its
    recent monthly average.
    """

    changes = changes.sort_values("this_month")

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            y=changes["category"],
            x=changes["average"],
            name="Recent average",
            orientation="h",
            marker_color=FINSIGHT_COLORS["grey"],
            hovertemplate=(
                "Average: €%{x:,.2f}"
                "<extra></extra>"
            ),
        )
    )

    fig.add_trace(
        go.Bar(
            y=changes["category"],
            x=changes["this_month"],
            name="This month",
            orientation="h",
            marker_color=[
                FINSIGHT_COLORS["red"] if change > 0 and notable
                else FINSIGHT_COLORS["green"] if change < 0 and notable
                else FINSIGHT_COLORS["blue"]
                for change, notable in zip(
                    changes["change"],
                    changes["notable"],
                )
            ],
            hovertemplate=(
                "This month: €%{x:,.2f}"
                "<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        barmode="group",
        height=max(260, 48 * len(changes)),
        bargap=0.3,
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "left",
            "x": 0,
        },
    )

    fig.update_xaxes(
        tickprefix="€",
        gridcolor="rgba(130,151,173,0.15)",
    )

    fig.update_yaxes(
        showgrid=False,
    )

    return style_plotly_chart(fig)
