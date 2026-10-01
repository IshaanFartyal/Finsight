"""Settings page: your own accounts, names and transfer keywords."""

import pandas as pd
import streamlit as st

from currency import HOME_CURRENCY, clean_rates
from flows import save_settings
from ui import (
    HOSTED,
    parse_lines,
    persist,
    storage_note,
)


def render(data):
    df = data.df

    st.title(
        "Settings"
    )

    st.caption(
        "Manage your Finsight preferences. "
        + storage_note()
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

    if HOSTED:
        st.warning(
            "⚠️ This is the online demo: don't enter your real account "
            "numbers or name here. Try it with made-up ones, e.g. "
            "NL00 DEMO 0123 4567 89."
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
        **settings,
        "own_accounts": parse_lines(own_accounts_text),
        "own_names": parse_lines(own_names_text),
        "transfer_keywords": parse_lines(keywords_text),
    }

    if updated_settings != settings:
        st.session_state.transfer_settings = updated_settings
        persist(save_settings, updated_settings)
        st.rerun()

    # ----------------------------------------------------
    # CURRENCIES
    # ----------------------------------------------------

    st.divider()

    st.subheader(
        "Currencies"
    )

    st.caption(
        "Finsight shows everything in euros. Set how many euros one unit "
        "of each other currency is worth, e.g. 1 USD = €0.92. "
        "Rates are entered by you, so Finsight never needs an internet "
        "connection."
    )

    rates = dict(settings.get("exchange_rates", {}))

    in_statements = (
        set(df["original_currency"]) - {HOME_CURRENCY}
        if df is not None and "original_currency" in df.columns
        else set()
    )

    currencies = sorted(in_statements | set(rates))

    if not currencies:
        st.info(
            "All your transactions are in euros, so no exchange rates "
            "are needed."
        )

    else:
        rate_table = pd.DataFrame(
            {
                "currency": currencies,
                "rate": [rates.get(code) for code in currencies],
            }
        ).astype({"rate": "float"})

        edited_rates = st.data_editor(
            rate_table,
            key="settings_exchange_rates",
            hide_index=True,
            disabled=["currency"],
            column_config={
                "currency": "Currency",
                "rate": st.column_config.NumberColumn(
                    "1 unit = € ...",
                    min_value=0.0,
                    format="%.4f",
                    help="Leave empty to keep amounts unconverted.",
                ),
            },
        )

        updated_rates = clean_rates(
            {
                row["currency"]: row["rate"]
                for _, row in edited_rates.iterrows()
                if pd.notna(row["rate"])
            }
        )

        if updated_rates != clean_rates(rates):
            new_settings = {
                **st.session_state.transfer_settings,
                "exchange_rates": updated_rates,
            }
            st.session_state.transfer_settings = new_settings
            persist(save_settings, new_settings)
            st.rerun()

        missing = [code for code in currencies if code not in updated_rates]

        if missing:
            st.caption(
                f"No rate yet for {', '.join(missing)}: those amounts "
                "are counted as if they were euros."
            )

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
