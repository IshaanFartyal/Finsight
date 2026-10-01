"""
Categories page: review merchants Finsight couldn't categorize, and edit
the keyword rules used to categorize transactions.
"""

from copy import deepcopy

import streamlit as st

from categorizer import (
    DEFAULT_CATEGORY_RULES,
    save_rules,
)
from corrections import (
    SCOPE_MERCHANT,
    add_correction,
    save_corrections,
)
from review import UNCATEGORIZED, categorized_share, uncategorized_merchants
from ui import (
    persist,
    storage_note,
)

REVIEW_EDITOR_KEY = "review_editor"


def _render_review(df):
    """Each uncategorized merchant once, with a category to pick."""

    st.subheader("To Review")

    if df is None:
        st.info(
            "Upload statements to see which merchants Finsight "
            "couldn't categorize."
        )
        return

    merchants = uncategorized_merchants(df)
    share = categorized_share(df)

    share_col, count_col, _ = st.columns(3)

    share_col.metric(
        "Categorized",
        f"{share:.0%}",
        help=(
            "Share of your income and spending transactions that have a "
            "category. Transfers between your own accounts don't count."
        ),
    )

    count_col.metric(
        "Merchants to Review",
        f"{len(merchants)}",
    )

    if merchants.empty:
        st.success("🎉 Every transaction has a category.")
        return

    st.caption(
        "Pick a category for each merchant. It applies to all its "
        "transactions, including in future uploads. Leave \"Other\" for "
        "merchants you want to skip. " + storage_note()
    )

    options = [
        category
        for category in st.session_state.category_rules
        if category != UNCATEGORIZED
    ] + [UNCATEGORIZED]

    table = merchants[
        ["merchant", "transactions", "total", "last_date", "example"]
    ].assign(category=UNCATEGORIZED)

    edited = st.data_editor(
        table,
        key=REVIEW_EDITOR_KEY,
        width="stretch",
        hide_index=True,
        disabled=["merchant", "transactions", "total", "last_date", "example"],
        column_order=["merchant", "category", "transactions", "total", "last_date", "example"],
        column_config={
            "merchant": "Merchant",
            "category": st.column_config.SelectboxColumn(
                "Category ✎",
                options=options,
                required=True,
            ),
            "transactions": "Transactions",
            "total": st.column_config.NumberColumn(
                "Total",
                format="€%.2f",
                help="Negative: money spent. Positive: money received.",
            ),
            "last_date": st.column_config.DateColumn(
                "Last seen",
                format="D MMM YYYY",
            ),
            "example": "As on your statement",
        },
    )

    chosen = edited[edited["category"] != UNCATEGORIZED]

    if chosen.empty:
        return

    corrections = st.session_state.corrections

    for position in chosen.index:
        add_correction(
            corrections,
            {
                "transaction_id": "",
                # Any description of this merchant gives the same key.
                "description": merchants.loc[position, "example"],
            },
            "category",
            chosen.loc[position, "category"],
            SCOPE_MERCHANT,
        )

    persist(save_corrections, corrections)
    st.session_state.corrections = corrections

    # The table is rebuilt without the merchants just categorized.
    st.session_state.pop(REVIEW_EDITOR_KEY, None)
    st.rerun()


def render(data):
    st.title(
        "Categories"
    )

    st.caption(
        "Customize how Finsight categorizes "
        "your transactions."
    )

    _render_review(data.df)

    st.divider()

    st.subheader(
        "Category Rules"
    )

    st.caption(
        "Matching ignores upper and lower case. When keywords from "
        "several categories match, the most specific (longest) one "
        "wins: \"Uber Eats\" is Restaurants, \"Uber\" is Transport. "
        "Keywords of up to 4 letters only match whole words. "
        "Corrections you make on the Transactions page "
        "take priority over these rules. "
        + storage_note()
    )

    rules_before = deepcopy(
        st.session_state.category_rules
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

    if st.session_state.category_rules != rules_before:
        persist(
            save_rules,
            st.session_state.category_rules
        )

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

            persist(

                save_rules,
                st.session_state.category_rules
            )

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

            # Clear the text boxes' stored values, otherwise they
            # write the old keywords straight back after the rerun.
            for key in list(st.session_state.keys()):
                if str(key).startswith("keywords_"):
                    del st.session_state[key]

            persist(

                save_rules,
                st.session_state.category_rules
            )

            st.rerun()
