"""
Transactions page: browse transactions and correct their category or type.
"""

import streamlit as st

from export import excel_available
from corrections import (
    SCOPE_MERCHANT,
    SCOPE_TRANSACTION,
    add_correction,
    corrections_table,
    remove_correction,
    save_corrections,
)
from ui import (
    FLOW_OPTIONS,
    export_csv,
    export_excel,
    month_selector,
    require_data,
)

# The table editor remembers edits by row position, so each month and
# filter combination gets its own editor; otherwise a pending edit could
# land on a different transaction after switching months.
EDITOR_KEY_PREFIX = "transactions_editor"

COLUMNS = [
    "date",
    "description",
    "category",
    "flow",
    "amount",
    "currency",
    "bank",
    "account",
    "corrected",
]


def _save_and_refresh(corrections):
    save_corrections(corrections)
    st.session_state.corrections = corrections

    # Forget the editors' pending edits: the table is rebuilt from the
    # corrected data on the next run.
    for key in list(st.session_state.keys()):
        if str(key).startswith(EDITOR_KEY_PREFIX):
            del st.session_state[key]

    st.rerun()


def _category_options(df):
    """Every category the user might want to pick."""
    options = list(st.session_state.category_rules)
    options += sorted(set(df["category"]) - set(options))

    for extra in ("Other", "Income", "Transfer"):
        if extra not in options:
            options.append(extra)

    return options


def render(data):
    df = data.df

    st.title(
        "Transactions"
    )

    st.caption(
        "Browse your transactions. Click a category or type to "
        "correct it; Finsight remembers your corrections."
    )

    if not require_data(df):
        return

    month_col, flow_col = st.columns(2)

    with month_col:
        selected_month = month_selector(
            df,
            key="transactions_month",
        )

    with flow_col:
        selected_flows = st.multiselect(
            "Type",
            FLOW_OPTIONS,
            default=FLOW_OPTIONS,
            key="transactions_flows",
        )

    transaction_df = (
        df[
            (df["month"] == selected_month)
            & df["flow"].isin(selected_flows)
        ]
        .sort_values("date", ascending=False)
        .set_index("transaction_id")
    )

    apply_to_merchant = st.toggle(
        "Apply my changes to every transaction from the same merchant",
        value=True,
        key="apply_to_merchant",
        help=(
            "On: changing one Spotify payment changes all Spotify "
            "payments, including future uploads. "
            "Off: only the transaction you edit changes."
        ),
    )

    editor_key = (
        f"{EDITOR_KEY_PREFIX}_{selected_month}_"
        + "-".join(sorted(selected_flows))
    )

    edited = st.data_editor(
        transaction_df[COLUMNS],
        key=editor_key,
        width="stretch",
        hide_index=True,
        disabled=[
            column
            for column in COLUMNS
            if column not in ("category", "flow")
        ],
        column_config={
            "date": st.column_config.DatetimeColumn(
                "Date",
                format="D MMM YYYY",
            ),
            "description": "Description",
            "category": st.column_config.SelectboxColumn(
                "Category ✎",
                options=_category_options(df),
                required=True,
            ),
            "flow": st.column_config.SelectboxColumn(
                "Type ✎",
                options=FLOW_OPTIONS,
                required=True,
            ),
            "amount": st.column_config.NumberColumn(
                "Amount",
                format="%.2f",
            ),
            "currency": "Currency",
            "bank": "Bank",
            "account": "Account",
            "corrected": st.column_config.TextColumn(
                "Corrected",
                help=(
                    "Empty: set automatically. merchant / transaction: "
                    "your correction."
                ),
            ),
        },
    )

    # ----------------------------------------------------
    # SAVE EDITS AS CORRECTIONS
    # ----------------------------------------------------

    corrections = st.session_state.corrections
    scope = SCOPE_MERCHANT if apply_to_merchant else SCOPE_TRANSACTION
    changed = False

    for transaction_id, row in edited.iterrows():
        original = transaction_df.loc[transaction_id]

        for field in ("category", "flow"):
            if row[field] != original[field]:
                add_correction(
                    corrections,
                    {
                        "transaction_id": transaction_id,
                        "description": original["description"],
                    },
                    field,
                    row[field],
                    scope,
                )
                changed = True

    if changed:
        _save_and_refresh(corrections)

    # ----------------------------------------------------
    # EXPORT
    # ----------------------------------------------------

    csv_col, excel_col, _ = st.columns([1, 1, 2])

    with csv_col:
        st.download_button(
            "⬇ Download CSV",
            data=export_csv(df),
            file_name="finsight_transactions.csv",
            mime="text/csv",
            help=f"All {len(df)} transactions, with your corrections.",
        )

    with excel_col:
        if excel_available():
            st.download_button(
                "⬇ Download Excel",
                data=export_excel(df),
                file_name="finsight_transactions.xlsx",
                mime=(
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
                help=(
                    "All transactions plus a monthly summary and spending "
                    "by category per month."
                ),
            )

        else:
            st.caption(
                "Excel export needs the openpyxl package: run "
                "`python -m pip install -r requirements.txt`."
            )

    # ----------------------------------------------------
    # SAVED CORRECTIONS
    # ----------------------------------------------------

    table = corrections_table(corrections, df)

    with st.expander(f"Your corrections ({len(table)})"):

        if table.empty:
            st.caption(
                "You haven't corrected anything yet. Corrections are "
                "saved on this computer only."
            )
            return

        st.dataframe(
            table[["applies_to", "category", "flow"]].rename(
                columns={
                    "applies_to": "Applies to",
                    "category": "Category",
                    "flow": "Type",
                }
            ),
            width="stretch",
            hide_index=True,
        )

        labels = {}

        for _, row in table.iterrows():
            label = row["applies_to"]

            # Keep labels unique if two corrections read the same.
            while label in labels:
                label += " "

            labels[label] = (row["scope"], row["key"])

        to_remove = st.multiselect(
            "Remove corrections",
            list(labels),
            key="corrections_to_remove",
        )

        remove_col, clear_col = st.columns(2)

        with remove_col:
            if st.button("Remove selected", disabled=not to_remove):
                for label in to_remove:
                    remove_correction(corrections, *labels[label])

                st.session_state.pop("corrections_to_remove", None)
                _save_and_refresh(corrections)

        with clear_col:
            if st.button("Remove all corrections"):
                corrections["transactions"].clear()
                corrections["merchants"].clear()

                st.session_state.pop("corrections_to_remove", None)
                _save_and_refresh(corrections)
