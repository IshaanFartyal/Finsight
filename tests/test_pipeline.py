from categorizer import DEFAULT_CATEGORY_RULES
from corrections import SCOPE_MERCHANT, SCOPE_TRANSACTION, add_correction, empty_corrections
from flows import default_settings, suggest_own_accounts
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


def test_demo_data_loads_and_shows_every_feature():
    from analytics import calculate_summary

    df, loaded, failed = build_transactions(
        files("demo_ing.csv", "demo_revolut.csv"),
        DEFAULT_CATEGORY_RULES,
        default_settings(),
        empty_corrections(),
    )

    assert loaded == {"demo_ing.csv": "ing", "demo_revolut.csv": "revolut"}
    assert failed == {}
    assert str(df["month"].min()) == "2026-03"
    assert str(df["month"].max()) == "2026-09"

    september = calculate_summary(df[df["month"].astype(str) == "2026-09"])

    # Transfers, refunds and fees all appear in September.
    assert september["transfers_out"] > 0
    assert september["refunds"] > 0
    assert september["fees"] > 0

    # The USD pocket needs an exchange rate.
    assert "USD" in set(df["currency"])


def test_savings_keep_their_category_and_dont_lower_the_savings_rate():
    from analytics import calculate_summary

    csv = (
        '"Datum";"Naam / Omschrijving";"Rekening";"Tegenrekening";"Code";"Af Bij";'
        '"Bedrag (EUR)";"Mutatiesoort";"Mededelingen";"Saldo na mutatie";"Tag"\n'
        '"20260901";"Employer";"NL12INGB0123456789";"NL03BANK1234567890";"OV";"Bij";'
        '"2000,00";"Overschrijving";"SALARY SEPTEMBER";"2000,00";""\n'
        '"20260905";"DEGIRO";"NL12INGB0123456789";"NL55DEGI0123456789";"OV";"Af";'
        '"500,00";"Overschrijving";"DEGIRO storting";"1500,00";""\n'
        '"20260910";"Albert Heijn";"NL12INGB0123456789";"NL01BANK1234567890";"BA";"Af";'
        '"100,00";"Betaalautomaat";"ALBERT HEIJN";"1400,00";""\n'
    )

    df, _, _ = build_transactions(
        [("ing.csv", csv.encode())],
        DEFAULT_CATEGORY_RULES,
        default_settings(),
        empty_corrections(),
    )

    degiro = df[df["description"] == "DEGIRO"].iloc[0]

    assert degiro["category"] == "Savings & Investments"
    assert degiro["flow"] == "transfer"

    summary = calculate_summary(df)

    assert summary["expenses"] == 100.0
    assert summary["savings_rate"] == 0.95


def test_own_account_question_sample():
    # A sample made to show "Are these accounts yours?" in Settings:
    # a reserve account and a friend (money goes both ways) are asked
    # about; the webshop that refunded an order and the landlord aren't.
    df, _, _ = build(None, "own_account_question_sample.csv")

    suggestions = suggest_own_accounts(df, default_settings())

    assert dict(zip(suggestions["name"], suggestions["account"])) == {
        "J Jansen": "NL77BANK0222222222",
        "Sam de Boer": "NL66BANK0111111111",
    }

    # Before the user confirms, payments to the reserve account are not
    # transfers...
    assert "transfer" not in set(df.loc[df["description"] == "J Jansen", "flow"])

    # ...and after confirming they all are.
    settings = default_settings()
    settings["own_accounts"] = ["NL77BANK0222222222"]

    confirmed, _, _ = build_transactions(
        files("own_account_question_sample.csv"),
        DEFAULT_CATEGORY_RULES,
        settings,
        empty_corrections(),
    )

    assert set(confirmed.loc[confirmed["description"] == "J Jansen", "flow"]) == {"transfer"}
    assert suggest_own_accounts(confirmed, settings)["name"].tolist() == ["Sam de Boer"]
