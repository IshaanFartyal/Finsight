"""Settings page: your own accounts, names and transfer keywords."""

import pandas as pd
import streamlit as st

from currency import HOME_CURRENCY, clean_rates
from flows import accounts_to_remember, save_settings, suggest_own_accounts
from storage import PROJECT_FOLDER, data_dir, delete_user_files, saved_files
from ui import (
    HOSTED,
    is_private,
    parse_lines,
    persist,
    storage_note,
)


def _render_account_suggestions(df):
    """
    Ask whether accounts that look like the user's own really are.

    Finsight never treats an account as the user's own by itself: an
    account only counts once the user confirms it here or types it in
    the list above.
    """
    settings = st.session_state.transfer_settings
    suggestions = suggest_own_accounts(df, settings)

    if suggestions.empty:
        return

    st.markdown("**Are these accounts yours?**")

    st.caption(
        "These accounts might be your own, for example because money "
        "regularly goes both ways. Tick the ones that are yours and "
        "payments to and from them become transfers instead of income "
        "or spending. For accounts you didn't upload a statement for, "
        "Finsight never decides this for you."
    )

    table = suggestions.copy()
    table.insert(0, "selected", False)

    edited = st.data_editor(
        table,
        key="settings_account_suggestions",
        hide_index=True,
        width="stretch",
        disabled=[column for column in table.columns if column != "selected"],
        column_config={
            "selected": st.column_config.CheckboxColumn("Select"),
            "account": "Account",
            "name": "Name",
            "transactions": "Transactions",
            "sent": st.column_config.NumberColumn("Sent", format="€%.2f"),
            "received": st.column_config.NumberColumn("Received", format="€%.2f"),
            "reason": "Why Finsight asks",
        },
    )

    selected = edited.loc[edited["selected"], "account"].tolist()

    mine, not_mine = st.columns(2)

    add_to = None

    if mine.button(
        "These are my accounts",
        disabled=not selected,
        type="primary",
        key="settings_suggestions_mine",
    ):
        add_to = "own_accounts"

    if not_mine.button(
        "Not mine, don't ask again",
        disabled=not selected,
        key="settings_suggestions_not_mine",
    ):
        add_to = "not_own_accounts"

    if add_to is None:
        return

    new_settings = {
        **settings,
        add_to: list(settings.get(add_to, [])) + selected,
    }

    st.session_state.transfer_settings = new_settings
    persist(save_settings, new_settings)

    # Rebuild the widgets from the new settings: the list of own
    # accounts above, and this table without the answered accounts.
    for key in ("settings_own_accounts", "settings_account_suggestions"):
        st.session_state.pop(key, None)

    st.rerun()


def _render_remember_accounts(df):
    """
    Opt-in: add the uploaded accounts to the saved list of own accounts.

    Without this, an account only counts as the user's own while its
    statement is uploaded, and nothing about it is saved.
    """
    settings = st.session_state.transfer_settings
    accounts = accounts_to_remember(df, settings)

    if not accounts:
        return

    # "No" hides the question for these accounts until Finsight is
    # closed. Nothing is saved: remembering that you declined would
    # mean storing the account numbers after all.
    declined = st.session_state.get("remember_accounts_declined", [])

    if set(accounts) <= set(declined):
        return

    st.markdown("**Remember these accounts?**")

    st.caption(
        "These accounts only count as yours while their statements are "
        "uploaded: "
        + ", ".join(accounts)
        + ". Remember them to keep recognizing transfers to them next "
        "time, even when you upload only some of your statements."
    )

    if is_private():
        st.caption(
            "🔒 Private session: your answer is kept until you close "
            "Finsight and is not saved to disk."
        )

    elif HOSTED:
        st.caption(storage_note())

    else:
        st.caption(
            "They are added to your own account numbers at the top of "
            "this page and saved on this computer only. You can remove "
            "them there at any time."
        )

    yes, no, _ = st.columns([1, 1, 3])

    if no.button(
        "No, don't remember",
        help="Hides this question until you close Finsight. Nothing is saved.",
        key="settings_remember_accounts_no",
    ):
        st.session_state.remember_accounts_declined = sorted(
            set(declined) | set(accounts)
        )
        st.rerun()

    if not yes.button(
        "Yes, remember them",
        type="primary",
        key="settings_remember_accounts",
    ):
        return

    new_settings = {
        **settings,
        "own_accounts": list(settings.get("own_accounts", [])) + accounts,
    }

    st.session_state.transfer_settings = new_settings
    persist(save_settings, new_settings)

    # Rebuild the list of own accounts at the top from the new settings.
    st.session_state.pop("settings_own_accounts", None)

    st.rerun()


# Kept when saved data is deleted: the uploaded statements and how the
# session was started. Everything else is rebuilt from the defaults.
KEEP_AFTER_DELETE = {
    "bank_statements",
    "private_mode",
    "use_demo",
    "disclaimer_shown",
}


def _render_saved_data():
    """
    Let the user delete everything Finsight saved for them: rules,
    settings, corrections and budgets. Not shown in the online demo,
    where nothing is saved.
    """
    if HOSTED:
        return

    st.divider()

    st.subheader("Saved data")

    if st.session_state.pop("saved_data_deleted", False):
        st.success(
            "Your saved data is deleted. Finsight is back to its default "
            "categories, with no budgets, corrections or own accounts."
        )

    failed = st.session_state.pop("saved_data_not_deleted", [])

    if failed:
        st.error(
            "These files could not be deleted: "
            + ", ".join(failed)
            + f". You can delete them yourself in `{data_dir()}`."
        )

    st.caption(
        "Finsight saves your category rules, settings (own accounts, "
        "names, exchange rates), corrections, and budgets and goals on "
        "this computer. Your bank statements are never saved."
    )

    files = saved_files()

    if files:
        st.caption(f"Saved now, in `{data_dir()}`: " + ", ".join(files) + ".")
    else:
        st.caption("Nothing is saved at the moment.")

    if not st.session_state.get("confirm_delete_saved_data"):
        if st.button(
            "Delete all saved data…",
            help=(
                "Removes your rules, settings, corrections and budgets "
                "from this computer and from this session. Asks for "
                "confirmation first."
            ),
            key="settings_delete_saved_data",
        ):
            st.session_state.confirm_delete_saved_data = True
            st.rerun()

        return

    st.warning(
        "Delete all saved data? Your category rules, settings, corrections, "
        "budgets and goals are removed from this computer and from this "
        "session, and Finsight goes back to its defaults. Your uploaded "
        "statements stay loaded. **This can't be undone.**"
    )

    yes, no, _ = st.columns([1, 1, 3])

    if no.button("Cancel", key="settings_delete_saved_data_cancel"):
        st.session_state.confirm_delete_saved_data = False
        st.rerun()

    if not yes.button(
        "Yes, delete everything",
        type="primary",
        key="settings_delete_saved_data_confirm",
    ):
        return

    _, failed = delete_user_files()

    # Forget the same things in this session; the app then starts again
    # from the defaults (or from whatever could not be deleted).
    st.cache_data.clear()

    for key in list(st.session_state.keys()):
        if key not in KEEP_AFTER_DELETE:
            del st.session_state[key]

    st.session_state.saved_data_deleted = not failed
    st.session_state.saved_data_not_deleted = failed

    st.rerun()


def render(data):
    df = data.df

    st.title(
        "Settings"
    )

    st.caption(
        "Manage your Finsight preferences. "
        + storage_note()
    )

    # The desktop app keeps the user's files in their own data folder;
    # say where, so they can find or delete them.
    if not HOSTED and not is_private() and data_dir() != PROJECT_FOLDER:
        st.caption(f"Your Finsight files are kept in: `{data_dir()}`")

    st.subheader(
        "Your Accounts"
    )

    st.caption(
        "Money moving between your own accounts is a transfer, "
        "not income or spending. The accounts of the statements you "
        "upload count as yours automatically. Use these settings for "
        "accounts you don't upload a statement for."
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

    _render_account_suggestions(df)

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

        st.caption(
            "Finsight treats these as your own accounts, so only upload "
            "your own statements in one session. Accounts from a bank "
            "Finsight doesn't recognize are the exception: it asks about "
            "those above."
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

        _render_remember_accounts(df)

    _render_saved_data()
