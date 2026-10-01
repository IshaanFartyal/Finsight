"""
Finsight: the Streamlit entry point.

This file sets up the page, the sidebar and the uploaded data; each page
lives in its own module under views/. Run with:

    streamlit run app.py
"""

import json

import streamlit as st

from budgets import load_budgets
from categorizer import load_rules
from corrections import load_corrections
from demo import demo_files
from flows import load_settings
from pipeline import build_monthly_finances, build_transactions
from ui import AppData
from views import (
    budgets_page,
    categories,
    insights_page,
    overview,
    settings,
    transactions,
    trends,
)

PAGES = {
    "Overview": overview,
    "Transactions": transactions,
    "Categories": categories,
    "Trends": trends,
    "Insights": insights_page,
    "Budgets & Goals": budgets_page,
    "Settings": settings,
}


# ============================================================
# PAGE SETUP
# ============================================================

st.set_page_config(
    page_title="Finsight",
    page_icon="💰",
    layout="wide",
)

with open("styles/style.css", encoding="utf-8") as css_file:
    st.markdown(
        f"<style>{css_file.read()}</style>",
        unsafe_allow_html=True,
    )


# ============================================================
# SESSION STATE
# ============================================================

# Each is loaded from its local JSON file if it exists, so
# customizations survive a page refresh.
if "category_rules" not in st.session_state:
    st.session_state.category_rules = load_rules()

if "transfer_settings" not in st.session_state:
    st.session_state.transfer_settings = load_settings()

if "corrections" not in st.session_state:
    st.session_state.corrections = load_corrections()

if "budgets" not in st.session_state:
    st.session_state.budgets = load_budgets()


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
    list(PAGES),
    label_visibility="collapsed",
)

st.sidebar.divider()

uploaded_files = st.sidebar.file_uploader(
    "Import bank statements",
    type=["csv"],
    accept_multiple_files=True,
    key="bank_statements",
    help=(
        "Upload statements from all your accounts at once. "
        "Transfers between them are recognized and left out "
        "of income and expenses."
    ),
)

if "use_demo" not in st.session_state:
    st.session_state.use_demo = False

# Uploaded statements always take priority over the demo.
if not uploaded_files:
    if st.session_state.use_demo:
        st.sidebar.info(
            "Showing **demo data**: made-up statements from an ING and a "
            "Revolut account."
        )

        if st.sidebar.button("Stop demo"):
            st.session_state.use_demo = False
            st.rerun()

    elif st.sidebar.button(
        "Try with demo data",
        help="Explore Finsight with made-up statements, no bank file needed.",
    ):
        st.session_state.use_demo = True
        st.rerun()


# ============================================================
# LOAD + ANALYSE FILES
# ============================================================

@st.cache_data(show_spinner="Analysing your statements…")
def load_transactions(files, rules_json, settings_json, corrections_json):
    """
    Cached: only re-runs when the files, rules, settings or corrections
    change. The JSON strings make those inputs easy for Streamlit to
    compare between runs.
    """
    df, loaded_files, failed_files = build_transactions(
        list(files),
        json.loads(rules_json),
        json.loads(settings_json),
        json.loads(corrections_json),
    )

    monthly_finances = (
        build_monthly_finances(df)
        if df is not None
        else None
    )

    return df, monthly_finances, loaded_files, failed_files


data = AppData()

if uploaded_files:
    files = tuple(
        (uploaded_file.name, uploaded_file.getvalue())
        for uploaded_file in uploaded_files
    )

elif st.session_state.use_demo:
    # Made-up statements from an ING account and a Revolut account with
    # a USD pocket, moved forward in time so they end in a recent month.
    files = demo_files()

else:
    files = ()

if files:
    df, monthly_finances, loaded_files, failed_files = load_transactions(
        files,
        json.dumps(st.session_state.category_rules, sort_keys=True),
        json.dumps(st.session_state.transfer_settings, sort_keys=True),
        json.dumps(st.session_state.corrections, sort_keys=True),
    )

    for file_name, reason in failed_files.items():
        st.sidebar.error(
            f"{file_name} could not be interpreted."
        )
        st.sidebar.caption(f"Reason: {reason}")

    data = AppData(
        df=df,
        monthly_finances=monthly_finances,
        loaded_files=loaded_files,
    )


# ============================================================
# SHOW THE SELECTED PAGE
# ============================================================

PAGES[page].render(data)
