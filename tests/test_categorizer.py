from categorizer import (
    DEFAULT_CATEGORY_RULES,
    categorize_dataframe,
    categorize_transaction,
    load_rules,
    save_rules,
)
from tests.helpers import load_sample


def category(text):
    return categorize_transaction(text, DEFAULT_CATEGORY_RULES)


def test_known_merchants():
    assert category("Albert Heijn 1234 Eindhoven") == "Groceries"
    assert category("Spotify P1A2B3") == "Subscriptions"
    assert category("Bol.com") == "Shopping"


def test_keywords_must_start_a_word():
    # "RENT" used to match inside PARENT and CURRENT.
    assert category("Gift for parent") == "Other"
    assert category("CURRENT ACCOUNT FEE") == "Other"
    assert category("Monthly rent") == "Housing"


def test_longer_keywords_may_continue_into_a_word():
    assert category("McDonalds Eindhoven") == "Restaurants"


def test_short_keywords_match_whole_words_only():
    assert category("NS") == "Transport"
    assert category("NS REIZEN") == "Transport"
    assert category("INSURANCE") == "Other"
    assert category("NSA MERCH") == "Other"


def test_first_matching_category_wins():
    rules = {
        "Business": ["CAFE DE ZWAAN"],
        "Restaurants": ["CAFE"],
    }

    assert categorize_transaction("Cafe de Zwaan", rules) == "Business"
    assert categorize_transaction("Cafe Central", rules) == "Restaurants"


def test_details_text_is_searched():
    # ING: "Employer" alone is unknown, but Mededelingen says SALARY.
    _, _, df = load_sample("ing_sample.csv")

    categories = dict(
        zip(
            df["description"],
            categorize_dataframe(df, DEFAULT_CATEGORY_RULES),
        )
    )

    assert categories["Employer"] == "Income"
    assert categories["NS"] == "Transport"


def test_rules_round_trip(tmp_path):
    path = tmp_path / "rules.json"
    rules = {"Business": ["CLIENT LUNCH"], "Groceries": ["JUMBO"]}

    save_rules(rules, path)

    assert load_rules(path) == rules


def test_missing_rules_file_falls_back_to_defaults(tmp_path):
    assert load_rules(tmp_path / "missing.json") == DEFAULT_CATEGORY_RULES


def test_corrupt_rules_file_falls_back_to_defaults(tmp_path):
    path = tmp_path / "rules.json"
    path.write_text("{ not valid json", encoding="utf-8")

    assert load_rules(path) == DEFAULT_CATEGORY_RULES
