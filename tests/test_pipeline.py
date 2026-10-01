from categorizer import DEFAULT_CATEGORY_RULES
from corrections import SCOPE_MERCHANT, SCOPE_TRANSACTION, add_correction, empty_corrections
from flows import default_settings
from pipeline import build_transactions
from tests.helpers import SAMPLE_DATA


def files(*names):
    return [(name, (SAMPLE_DATA / name).read_bytes()) for name in names]


def build(corrections=None, *names):
    names = names or ("multi_account_ing.csv", "multi_account_revolut.csv")

    return build_transactions(
        files(*names),
        DEFAULT_CATEGORY_RULES,
        default_settings(),
        corrections or empty_corrections(),
    )


def test_builds_combined_transactions():
    df, loaded, failed = build()

    assert len(df) == 14
    assert loaded == {
        "multi_account_ing.csv": "ing",
        "multi_account_revolut.csv": "revolut",
    }
    assert failed == {}
    assert {"category", "flow", "month", "transaction_id", "corrected"} <= set(df.columns)


def test_transfers_get_transfer_category():
    df, _, _ = build()

    assert (df.loc[df["flow"] == "transfer", "category"] == "Transfer").all()


def test_unreadable_file_is_reported_and_others_still_load():
    bad = ("broken.csv", b"\x00\x01 not a csv at all")

    df, loaded, failed = build_transactions(
        [bad] + files("ing_sample.csv"),
        DEFAULT_CATEGORY_RULES,
        default_settings(),
        empty_corrections(),
    )

    assert "broken.csv" in failed
    assert list(loaded) == ["ing_sample.csv"]
    assert len(df) == 4


def test_no_readable_files():
    df, loaded, failed = build_transactions(
        [("broken.csv", b"\x00\x01")],
        DEFAULT_CATEGORY_RULES,
        default_settings(),
        empty_corrections(),
    )

    assert df is None
    assert loaded == {}


def test_corrections_survive_reuploading_the_same_file():
    df, _, _ = build()
    zalando_refund = df[(df["description"] == "Zalando") & (df["amount"] > 0)].iloc[0]

    corrections = empty_corrections()
    add_correction(corrections, zalando_refund, "flow", "income", SCOPE_TRANSACTION)

    # Same files again, uploaded in a different order.
    again, _, _ = build_transactions(
        files("multi_account_revolut.csv", "multi_account_ing.csv"),
        DEFAULT_CATEGORY_RULES,
        default_settings(),
        corrections,
    )

    row = again[again["transaction_id"] == zalando_refund["transaction_id"]].iloc[0]

    assert row["flow"] == "income"
    assert row["corrected"] == "transaction"


def test_marking_a_merchant_as_transfer():
    df, _, _ = build()
    jumbo = df[df["description"] == "Jumbo"].iloc[0]

    corrections = empty_corrections()
    add_correction(corrections, jumbo, "flow", "transfer", SCOPE_MERCHANT)

    corrected, _, _ = build(corrections)
    row = corrected[corrected["description"] == "Jumbo"].iloc[0]

    assert row["flow"] == "transfer"
    assert row["category"] == "Transfer"


def test_explicit_category_on_a_transfer_is_kept():
    df, _, _ = build()
    jumbo = df[df["description"] == "Jumbo"].iloc[0]

    corrections = empty_corrections()
    add_correction(corrections, jumbo, "flow", "transfer", SCOPE_TRANSACTION)
    add_correction(corrections, jumbo, "category", "Savings", SCOPE_TRANSACTION)

    corrected, _, _ = build(corrections)
    row = corrected[corrected["description"] == "Jumbo"].iloc[0]

    assert row["category"] == "Savings"
