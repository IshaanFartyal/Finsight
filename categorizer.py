import json
import re
from pathlib import Path

import pandas as pd

# Categories are checked top to bottom: the first category with a
# matching keyword wins. Order therefore sets priority.
DEFAULT_CATEGORY_RULES = {
    "Groceries": [
        "ALBERT HEIJN",
        "JUMBO",
        "LIDL",
        "ALDI",
    ],
    "Subscriptions": [
        "SPOTIFY",
        "NETFLIX",
        "YOUTUBE PREMIUM",
    ],
    "Transport": [
        "UBER",
        "NS",
        "OVPAY",
        "SHELL",
    ],
    "Restaurants": [
        "MCDONALD",
        "BURGER KING",
        "RESTAURANT",
        "CAFE",
    ],
    "Shopping": [
        "AMAZON",
        "BOL.COM",
        "ZALANDO",
    ],
    "Housing": [
        "RENT",
        "HOUSING",
        "DUWO",
    ],
    "Income": [
        "SALARY",
        "SALARIS",
        "PAYROLL",
    ],
}

# Local, per-user rules file. It can contain personal details
# (employer, clients), so it is git-ignored.
RULES_PATH = Path(__file__).parent / "rules.json"

# Keywords this short must match a whole word ("NS" should match
# "NS REIZEN" but not "NSA" or "INSURANCE").
SHORT_KEYWORD_LENGTH = 3


def _keyword_pattern(keyword):
    """
    Build a regex for one keyword.

    Every keyword must start at a word boundary, so "RENT" does not
    match "PARENT" or "CURRENT". Longer keywords may continue into the
    rest of a word, so "MCDONALD" still matches "MCDONALDS".
    Short keywords must match a whole word.
    """

    keyword = keyword.strip().upper()
    pattern = r"(?<![A-Z0-9])" + re.escape(keyword)

    if len(keyword) <= SHORT_KEYWORD_LENGTH:
        pattern += r"(?![A-Z0-9])"

    return re.compile(pattern)


def compile_rules(category_rules):
    """Turn {category: [keywords]} into [(category, [patterns])]."""

    return [
        (
            category,
            [
                _keyword_pattern(keyword)
                for keyword in keywords
                if keyword.strip()
            ],
        )
        for category, keywords in category_rules.items()
    ]


def categorize_transaction(text, category_rules):
    """
    Return the first category whose keyword appears in text,
    or "Other" if none match.

    category_rules may be raw {category: [keywords]} or the output
    of compile_rules().
    """

    if isinstance(category_rules, dict):
        category_rules = compile_rules(category_rules)

    text = str(text).upper()

    for category, patterns in category_rules:
        for pattern in patterns:
            if pattern.search(text):
                return category

    return "Other"


def categorize_dataframe(df, category_rules):
    """
    Categorize every transaction, searching both the description and
    any extra details text the parser provides (e.g. ING Mededelingen).
    """

    compiled = compile_rules(category_rules)

    if "details" in df.columns:
        details = df["details"].fillna("").astype(str)
    else:
        details = pd.Series("", index=df.index)

    text = df["description"].fillna("").astype(str) + " " + details

    return text.apply(
        lambda value: categorize_transaction(value, compiled)
    )


def load_rules(path=RULES_PATH):
    """Load saved rules, falling back to the defaults."""

    path = Path(path)

    if not path.exists():
        return {
            category: list(keywords)
            for category, keywords in DEFAULT_CATEGORY_RULES.items()
        }

    try:
        with open(path, encoding="utf-8") as rules_file:
            rules = json.load(rules_file)

    except (OSError, json.JSONDecodeError):
        return {
            category: list(keywords)
            for category, keywords in DEFAULT_CATEGORY_RULES.items()
        }

    # Keep only well-formed entries.
    return {
        str(category): [str(keyword) for keyword in keywords]
        for category, keywords in rules.items()
        if isinstance(keywords, list)
    }


def save_rules(category_rules, path=RULES_PATH):
    """Save rules to the local rules file."""

    with open(path, "w", encoding="utf-8") as rules_file:
        json.dump(
            category_rules,
            rules_file,
            indent=2,
            ensure_ascii=False,
        )
