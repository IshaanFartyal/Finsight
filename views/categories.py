"""Categories page: edit the keyword rules used to categorize transactions."""

from copy import deepcopy

import streamlit as st

from categorizer import (
    DEFAULT_CATEGORY_RULES,
    save_rules,
)
from ui import (
    persist,
    storage_note,
)


def render(data):
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

    st.caption(
        "Categories are checked from top to bottom. "
        "The first category with a matching keyword wins. "
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
