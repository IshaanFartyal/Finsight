"""
Finsight: the Streamlit entry point.

This file sets up the page, the sidebar and the uploaded data; each page
lives in its own module under views/. Run with:

    streamlit run app.py
"""

import json
import time

import streamlit as st

from budgets import load_budgets
from categorizer import DEFAULT_CATEGORY_RULES, load_rules
from corrections import empty_corrections, load_corrections
from demo import DEMO_EXCHANGE_RATES, demo_budgets, demo_files
from flows import default_settings, load_settings
from hosting import (
    DISCLAIMER,
    DISCLAIMER_TITLE,
    SIDEBAR_NOTICE,
)
from pipeline import build_monthly_finances, build_transactions
from ui import HOSTED, PRIVATE_BY_DEFAULT, AppData
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

def initial_state():
    """
    Locally: everything is loaded from its JSON file (if it exists), so
    customizations survive a page refresh.

    Online demo: every visitor starts fresh, with example budgets, a
    savings goal and an exchange rate for the demo's USD account. No
    files are read or written.
    """
    if HOSTED:
        settings = default_settings()
        settings["exchange_rates"] = dict(DEMO_EXCHANGE_RATES)

        return {
            "category_rules": {
                category: list(keywords)
                for category, keywords in DEFAULT_CATEGORY_RULES.items()
            },
            "transfer_settings": settings,
            "corrections": empty_corrections(),
            "budgets": demo_budgets(),
        }

    return {
        "category_rules": load_rules(),
        "transfer_settings": load_settings(),
        "corrections": load_corrections(),
        "budgets": load_budgets(),
    }


for key, value in initial_state().items():
    if key not in st.session_state:
        st.session_state[key] = value


# The "cleared from memory" confirmation: fully visible for 2 seconds,
# fades out over 1 second, then folds away in 0.3 seconds
# (CSS animation in styles/style.css; keep the total in sync).
CLEARED_NOTICE_SECONDS = 3.3

CLEARED_NOTICE = (
    "✅ Cleared from memory: your statements, the analysis cache "
    "and all changes from this session are gone."
)


def show_cleared_notice(cleared_at):
    """
    Show the confirmation under the clear button.

    If the app reruns while the message is still showing (e.g. the user
    clicks something), the animation continues where it was instead of
    starting over, via a negative animation delay.
    """
    elapsed = time.time() - cleared_at

    if elapsed >= CLEARED_NOTICE_SECONDS:
        st.session_state.pop("cleared_at", None)
        return

    st.sidebar.markdown(
        f'<div class="finsight-cleared" '
        f'style="animation-delay: -{elapsed:.2f}s">{CLEARED_NOTICE}</div>',
        unsafe_allow_html=True,
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
    list(PAGES),
    label_visibility="collapsed",
)

st.sidebar.divider()

if HOSTED:
    # Online demo: no uploads, so nobody sends a real bank statement
    # to a shared server. The demo data is always shown.
    uploaded_files = []
    st.session_state.use_demo = True

    st.sidebar.warning(SIDEBAR_NOTICE)

else:
    # Private session: nothing is written to disk (rules, settings,
    # corrections, budgets), and everything can be wiped from memory
    # with one click. Useful for testing with real statements.
    if "private_mode" not in st.session_state:
        st.session_state.private_mode = PRIVATE_BY_DEFAULT

    st.sidebar.toggle(
        "🔒 Private session",
        key="private_mode",
        help=(
            "Nothing is saved to disk while this is on: changes to rules, "
            "settings, corrections and budgets only last until you close "
            "Finsight. Files saved earlier stay where they are."
        ),
    )

    if st.session_state.private_mode:
        st.sidebar.caption(
            "Nothing is saved to disk. Your statements and changes are "
            "only held in memory until you close Finsight."
        )

        if st.sidebar.button(
            "🧹 Clear everything from memory",
            help=(
                "Removes your uploaded statements, the analysis cache and "
                "all changes from this session right away."
            ),
        ):
            # Cached analyses of uploaded statements
            st.cache_data.clear()

            # Uploads, selections and unsaved changes
            for key in list(st.session_state.keys()):
                del st.session_state[key]

            st.session_state.private_mode = True

            # Remembered so the confirmation below can show after the rerun.
            st.session_state.cleared_at = time.time()
            st.rerun()

        if st.session_state.get("cleared_at"):
            show_cleared_notice(st.session_state.cleared_at)

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
if not uploaded_files and not HOSTED:
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
# ONLINE DEMO DISCLAIMER
# ============================================================

@st.dialog(DISCLAIMER_TITLE)
def show_disclaimer():
    st.markdown(DISCLAIMER)

    if st.button("I understand, show me the demo", type="primary"):
        st.rerun()


# Shown once per visit. Closing it any way (button, ✕ or Esc) counts,
# so it never blocks the demo; the sidebar keeps a short reminder.
if HOSTED and not st.session_state.get("disclaimer_shown"):
    st.session_state.disclaimer_shown = True
    show_disclaimer()


# ============================================================
# SHOW THE SELECTED PAGE
# ============================================================

PAGES[page].render(data)
