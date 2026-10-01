import json
import re
from pathlib import Path

import pandas as pd

# Keywords per category. When keywords from several categories match,
# the most specific (longest) keyword wins, so "UBER EATS" is Restaurants
# even though "UBER" is Transport. Matching ignores upper/lower case.
DEFAULT_CATEGORY_RULES = {
    "Groceries": [
        "ALBERT HEIJN",
        "AH TO GO",
        "JUMBO",
        "LIDL",
        "ALDI",
        # Not just "DIRK": that would also match a friend called Dirk.
        "DIRK VAN DEN BROEK",
        "DIRK VDBROEK",
        "PLUS SUPERMARKT",
        "SPAR",
        "PICNIC",
        "CRISP",
    ],
    "Restaurants": [
        "MCDONALD",
        "BURGER KING",
        "RESTAURANT",
        "CAFE",
        "STARBUCKS",
        "THUISBEZORGD",
        "UBER EATS",
    ],
    "Transport": [
        "NS",
        "ISSUED BY NS",
        "NEDERLANDSE SPOORWEGEN",
        "OVPAY",
        "GVB",
        "RET",
        "HTM",
        "ARRIVA",
        "UBER",
        "BOLT",
        "SHELL",
        "ESSO",
    ],
    "Subscriptions": [
        "SPOTIFY",
        "NETFLIX",
        "DISNEY",
        "YOUTUBE PREMIUM",
        "AMAZON PRIME",
    ],
    "Shopping": [
        "AMAZON",
        "BOL.COM",
        "ZALANDO",
        "COOLBLUE",
        "MEDIAMARKT",
        "IKEA",
        "ACTION",
        "H&M",
        "ZARA",
    ],
    "Travel": [
        "BOOKING.COM",
        "AIRBNB",
        "KLM",
        "TRANSAVIA",
        "RYANAIR",
        "EASYJET",
    ],
    "Housing": [
        "RENT",
        "HOUSING",
        "DUWO",
    ],
    "Utilities": [
        "VATTENFALL",
        "ENECO",
        "ESSENT",
        "ZIGGO",
        "KPN",
        "ODIDO",
        "VODAFONE",
    ],
    "Insurance": [
        "VGZ",
        "ZILVEREN KRUIS",
        "MENZIS",
        "ACHMEA",
        "AON",
    ],
    "Healthcare": [
        "APOTHEEK",
        "PHARMACY",
        "TANDARTS",
        "DENTIST",
    ],
    "Education": [
        "UNIVERSITY",
        "TUITION",
        "COLLEGE",
        "COURSE FEE",
        "COURSERA",
        "UDEMY",
    ],
    # Money settled with friends (Tikkie). Unlike "Transfer", which is
    # money between your own accounts, this still counts as income or
    # spending.
    "Payment Requests": [
        "TIKKIE",
    ],
    "Cash Withdrawal": [
        "GELDMAAT",
        "CASH WITHDRAWAL",
    ],
    # Money moved to your own investment or savings accounts. Treated as
    # a transfer (see flows.py), so it doesn't count as spending.
    "Savings & Investments": [
        "DEGIRO",
        # How DEGIRO deposits usually appear on bank statements
        "FLATEXDEGIRO",
        "TRADE REPUBLIC",
        "BUX",
    ],
    "Fees": [
        "BANK FEE",
        "SERVICE FEE",
        # Monthly account charges at Dutch banks: "Kosten OranjePakket"
        # (ING), "Kosten Rabo DirectPakket" (Rabobank), "BasisPakket",
        # "BetaalPakket".
        "ORANJEPAKKET",
        "DIRECTPAKKET",
        "BASISPAKKET",
        "TOTAALPAKKET",
        "BETAALPAKKET",
        "BANKKOSTEN",
    ],
    "Income": [
        "SALARY",
        "SALARIS",
        "PAYROLL",
    ],
}

SAVINGS_CATEGORY = "Savings & Investments"

# Local, per-user rules file. It can contain personal details
# (employer, clients), so it is git-ignored.
RULES_PATH = Path(__file__).parent / "rules.json"

# Keywords this short must match a whole word: "NS" should match
# "NS REIZEN" but not "INSURANCE", and "SPAR" not "SPARKASSE".
SHORT_KEYWORD_LENGTH = 4


def _keyword_pattern(keyword):
    """
    Build a regex for one keyword.

    Every keyword must start at a word boundary, so "RENT" does not
    match "PARENT" or "CURRENT". Longer keywords may continue into the
    rest of a word, so "MCDONALD" still matches "MCDONALDS".
    Short keywords (up to 4 characters) must match a whole word.
    """

    keyword = keyword.strip().upper()
    pattern = r"(?<![A-Z0-9])" + re.escape(keyword)

    if len(keyword) <= SHORT_KEYWORD_LENGTH:
        pattern += r"(?![A-Z0-9])"

    return re.compile(pattern)


def compile_rules(category_rules):
    """
    Turn {category: [keywords]} into a list of
    (category, keyword length, pattern), one per keyword.
    """

    return [
        (category, len(keyword.strip()), _keyword_pattern(keyword))
        for category, keywords in category_rules.items()
        for keyword in keywords
        if keyword.strip()
    ]


def categorize_transaction(text, category_rules):
    """
    Return the category of the most specific (longest) keyword found in
    text, or "Other" if none match. On a tie, the category listed first
    wins.

    category_rules may be raw {category: [keywords]} or the output
    of compile_rules().
    """

    if isinstance(category_rules, dict):
        category_rules = compile_rules(category_rules)

    text = str(text).upper()

    best_category = "Other"
    best_length = 0

    for category, length, pattern in category_rules:
        if length > best_length and pattern.search(text):
            best_category = category
            best_length = length

    return best_category


def categorize_dataframe(df, category_rules):
    """
    Categorize every transaction, searching both the description and
    any extra details text the parser provides (e.g. ING Mededelingen).

    Works one keyword at a time over the whole column, longest keyword
    first, so each row stops being checked once it has a match.
    """

    compiled = compile_rules(category_rules)

    if "details" in df.columns:
        details = df["details"].fillna("").astype(str)
    else:
        details = pd.Series("", index=df.index)

    text = (
        df["description"].fillna("").astype(str) + " " + details
    ).str.upper()

    category = pd.Series("Other", index=df.index, dtype=object)
    unmatched = pd.Series(True, index=df.index)

    # Longest keywords first (ties: the category listed first), so the
    # first match for a row is also its best match, and rows that
    # already have one don't need to be checked again.
    ordered = sorted(
        enumerate(compiled),
        key=lambda item: (-item[1][1], item[0]),
    )

    for _, (name, _, pattern) in ordered:
        if not unmatched.any():
            break

        rows = unmatched[unmatched].index
        found = text.loc[rows].str.contains(pattern, regex=True)
        found = found[found].index

        category.loc[found] = name
        unmatched.loc[found] = False

    return category


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
