"""Settings page: your own accounts, names and transfer keywords."""

import streamlit as st

from flows import save_settings
from ui import parse_lines


def render(data):
    df = data.df

    st.title(
        "Settings"
    )

    st.caption(
        "Manage your Finsight preferences. "
        "Settings are saved on this computer only."
    )

    st.subheader(
        "Your Accounts"
    )

    st.caption(
        "Money moving between your own accounts is a transfer, "
        "not income or spending. Finsight recognizes most transfers "
        "automatically when you upload statements from all your "
        "accounts. These settings catch the rest."
    )

    settings = st.session_state.transfer_settings

    own_accounts_text = st.text_area(
        "Your own account numbers (IBANs), one per line",
        value="\n".join(settings["own_accounts"]),
        placeholder="NL12 INGB 0123 4567 89",
        key="settings_own_accounts",
    )

    own_names_text = st.text_area(
        "Names your accounts are held under, one per line",
        value="\n".join(settings["own_names"]),
        help=(
            "A payment to or from this name is treated as a "
            "transfer between your own accounts."
        ),
        key="settings_own_names",
    )

    keywords_text = st.text_area(
        "Transfer keywords, one per line",
        value="\n".join(settings["transfer_keywords"]),
        help=(
            "Transactions whose description contains one of these "
            "are treated as transfers, e.g. your savings account name."
        ),
        key="settings_transfer_keywords",
    )

    updated_settings = {
        "own_accounts": parse_lines(own_accounts_text),
        "own_names": parse_lines(own_names_text),
        "transfer_keywords": parse_lines(keywords_text),
    }

    if updated_settings != settings:
        st.session_state.transfer_settings = updated_settings
        save_settings(updated_settings)
        st.rerun()

    if df is not None:
        st.divider()

        st.subheader(
            "Accounts in your uploaded statements"
        )

        accounts = (
            df.groupby(["bank", "account"], dropna=False)
            .agg(
                transactions=("amount", "size"),
                first=("date", "min"),
                last=("date", "max"),
            )
            .reset_index()
        )

        st.dataframe(
            accounts,
            width="stretch",
            hide_index=True,
        )
