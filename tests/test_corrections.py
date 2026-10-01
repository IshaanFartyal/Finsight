import pandas as pd

from corrections import (
    SCOPE_MERCHANT,
    SCOPE_TRANSACTION,
    add_correction,
    apply_corrections,
    corrections_table,
    empty_corrections,
    load_corrections,
    remove_correction,
    save_corrections,
)


def transactions():
    return pd.DataFrame(
        {
            "transaction_id": ["a", "b", "c"],
            "date": pd.to_datetime(["2026-09-05", "2026-10-05", "2026-09-10"]),
            "description": ["Spotify P1A2", "SPOTIFY", "Tikkie J Jansen"],
            "amount": [-10.99, -10.99, 50.0],
            "category": ["Subscriptions", "Subscriptions", "Other"],
            "flow": ["expense", "expense", "refund"],
        }
    )


def test_no_corrections_changes_nothing():
    df = apply_corrections(transactions(), empty_corrections())

    assert df["category"].tolist() == ["Subscriptions", "Subscriptions", "Other"]
    assert (df["corrected"] == "").all()


def test_merchant_correction_applies_to_every_matching_transaction():
    corrections = empty_corrections()
    row = transactions().iloc[0]

    add_correction(corrections, row, "category", "Entertainment", SCOPE_MERCHANT)

    df = apply_corrections(transactions(), corrections)

    # "Spotify P1A2" and "SPOTIFY" are the same merchant.
    assert df["category"].tolist() == ["Entertainment", "Entertainment", "Other"]
    assert df["corrected"].tolist() == ["merchant", "merchant", ""]


def test_transaction_correction_applies_to_one_transaction():
    corrections = empty_corrections()
    row = transactions().iloc[2]

    add_correction(corrections, row, "flow", "income", SCOPE_TRANSACTION)

    df = apply_corrections(transactions(), corrections)

    assert df["flow"].tolist() == ["expense", "expense", "income"]
    assert df["corrected"].tolist() == ["", "", "transaction"]


def test_transaction_correction_beats_merchant_correction():
    corrections = empty_corrections()
    rows = transactions()

    add_correction(corrections, rows.iloc[0], "category", "Entertainment", SCOPE_MERCHANT)
    add_correction(corrections, rows.iloc[1], "category", "Work", SCOPE_TRANSACTION)

    df = apply_corrections(rows, corrections)

    assert df["category"].tolist() == ["Entertainment", "Work", "Other"]


def test_new_merchant_correction_replaces_older_single_correction():
    corrections = empty_corrections()
    rows = transactions()

    add_correction(corrections, rows.iloc[0], "category", "Work", SCOPE_TRANSACTION)
    add_correction(corrections, rows.iloc[0], "category", "Entertainment", SCOPE_MERCHANT)

    df = apply_corrections(rows, corrections)

    assert df["category"].tolist()[:2] == ["Entertainment", "Entertainment"]
    assert corrections["transactions"] == {}


def test_both_fields_can_be_corrected():
    corrections = empty_corrections()
    row = transactions().iloc[2]

    add_correction(corrections, row, "category", "Social", SCOPE_TRANSACTION)
    add_correction(corrections, row, "flow", "income", SCOPE_TRANSACTION)

    df = apply_corrections(transactions(), corrections)

    assert df.loc[2, "category"] == "Social"
    assert df.loc[2, "flow"] == "income"


def test_remove_correction():
    corrections = empty_corrections()
    row = transactions().iloc[0]

    add_correction(corrections, row, "category", "Entertainment", SCOPE_MERCHANT)
    remove_correction(corrections, SCOPE_MERCHANT, "SPOTIFY")

    assert corrections == empty_corrections()


def test_round_trip(tmp_path):
    path = tmp_path / "corrections.json"
    corrections = empty_corrections()

    add_correction(corrections, transactions().iloc[0], "category", "Entertainment", SCOPE_MERCHANT)
    add_correction(corrections, transactions().iloc[2], "flow", "income", SCOPE_TRANSACTION)

    save_corrections(corrections, path)

    assert load_corrections(path) == corrections


def test_missing_or_corrupt_file_means_no_corrections(tmp_path):
    assert load_corrections(tmp_path / "missing.json") == empty_corrections()

    path = tmp_path / "corrections.json"
    path.write_text("{ broken", encoding="utf-8")

    assert load_corrections(path) == empty_corrections()


def test_corrections_table_describes_each_correction():
    corrections = empty_corrections()
    rows = transactions()

    add_correction(corrections, rows.iloc[0], "category", "Entertainment", SCOPE_MERCHANT)
    add_correction(corrections, rows.iloc[2], "flow", "income", SCOPE_TRANSACTION)

    table = corrections_table(corrections, rows)

    assert table["applies_to"].tolist() == [
        "All transactions from Spotify",
        "Tikkie J Jansen, 10 Sep 2026, €50.00",
    ]
