"""
Helpers shared by the app's pages (views/).

The insight functions are wrapped in st.cache_data here, so each page
gets the same cached results: switching pages or months doesn't
recalculate anything that was already calculated.
"""

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd
import streamlit as st

import export
import hosting
import insights

BANK_NAMES = {
    "revolut": "Revolut",
    "wise": "Wise",
    "ing": "ING",
    "rabobank": "Rabobank",
    "unknown": "Undetected bank",
}

FLOW_OPTIONS = ["income", "expense", "refund", "transfer"]


@dataclass
class AppData:
    """Everything the pages need about the uploaded statements."""

    df: Optional[pd.DataFrame] = None
    monthly_finances: Optional[pd.DataFrame] = None
    # file name -> detected bank
    loaded_files: dict = field(default_factory=dict)


# ============================================================
# CACHED INSIGHTS
# ============================================================

@st.cache_data(show_spinner=False)
def category_changes(df, month):
    return insights.category_changes(df, month)


@st.cache_data(show_spinner=False)
def recurring_until(df, month):
    """Recurring payments using data up to and including month."""
    return insights.detect_recurring(insights.data_until(df, month))


@st.cache_data(show_spinner=False)
def unusual_transactions(df, month):
    return insights.unusual_transactions(df, month)


@st.cache_data(show_spinner=False)
def price_changes(df, month):
    return insights.price_changes(df, month)


@st.cache_data(show_spinner=False)
def new_recurring(df, month):
    return insights.new_recurring(df, month)


@st.cache_data(show_spinner=False)
def duplicate_charges(df, month):
    return insights.duplicate_charges(df, month)


@st.cache_data(show_spinner=False)
def month_end_forecast(df, month):
    return insights.month_end_forecast(df, month)


@st.cache_data(show_spinner=False)
def key_insights(df, month):
    return insights.key_insights(df, month)


@st.cache_data(show_spinner=False)
def export_csv(df):
    return export.to_csv_bytes(df)


@st.cache_data(show_spinner="Preparing Excel file…")
def export_excel(df):
    return export.to_excel_bytes(df)


# ============================================================
# HOSTED MODE (online demo)
# ============================================================

def _secrets():
    """st.secrets, or None when it can't be read."""
    try:
        return st.secrets
    except Exception:
        return None


# Decided once when the app starts.
HOSTED = hosting.is_hosted(secrets=_secrets())

# Start sessions as private sessions (FINSIGHT_PRIVATE, from the
# environment or a secrets.toml file). Local only.
PRIVATE_BY_DEFAULT = (
    not HOSTED
    and hosting.private_by_default(secrets=_secrets())
)


def is_private():
    """True during a private session (sidebar switch, local only)."""
    return bool(st.session_state.get("private_mode", False))


def persist(save, data):
    """
    Save data with the given save function, except in the online demo
    and in a private session, where changes stay in memory only.
    """
    return hosting.save_if_local(save, data, HOSTED or is_private())


def storage_note():
    """Caption text saying where changes are kept."""
    return hosting.storage_note(HOSTED, is_private())


# ============================================================
# DISPLAY HELPERS
# ============================================================

def require_data(df):
    """Show a message when no bank statement has been uploaded."""
    if df is None:
        st.info(
            "Upload one or more bank statements from the sidebar "
            "to start using Finsight."
        )
        return False

    return True


def show_insight(container, insight):
    """Show one insight in the bubble style matching its kind."""
    if insight["kind"] == "warning":
        container.warning(insight["text"])
    elif insight["kind"] == "positive":
        container.success(insight["text"])
    else:
        container.info(insight["text"])


def month_selector(df, key):
    """Month picker, newest month first."""
    available_months = sorted(
        df["month"].dropna().unique(),
        reverse=True,
    )

    return st.selectbox(
        "Month",
        available_months,
        format_func=lambda month: month.strftime("%B %Y"),
        key=key,
    )


def parse_lines(text):
    """One entry per line, blank lines ignored."""
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]
