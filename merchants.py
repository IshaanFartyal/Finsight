"""
Turn messy transaction descriptions into clean merchant names.

Bank statements rarely say just "Bakkerij Jansen". Card payments often
go through a payment processor or carry card and terminal codes:

    SumUp  *Bakkerij Jansen
    CCV*CAFE DE ZWAAN
    Zettle_*Kapsalon Mooi
    PayPal *Netflix
    Card transaction of 12.50 EUR issued by Albert Heijn Eindhoven
    BEA, Apple Pay ALBERT HEIJN 1234,PAS123 NR:ABC123, 06.09.26/12:34

clean_merchant() turns these into readable names ("Bakkerij Jansen"), and
normalize_merchant() into a matching key ("BAKKERIJ JANSEN"), so the same
merchant is recognized across transactions: for corrections, refunds,
recurring payments, unusual spending and the review screen.
"""

import re

# Payment processors and wallets that appear before the real merchant,
# separated by *, _ or similar ("SumUp *", "CCV*", "Zettle_*").
_PROCESSORS = [
    "SUMUP",
    "SUM UP",
    "IZETTLE",
    "ZETTLE",
    "CCV",
    "MOLLIE",
    "PAY.NL",
    "PAYNL",
    "ADYEN",
    "STRIPE",
    "PAYPAL",
    "PP",
    "SQ",
    "TST",
    "BCK",
    "MYPOS",
    "WORLDLINE",
    "BUCKAROO",
    "KLARNA",
    "GOOGLE",
    "APPLE",
]

_PROCESSOR_PREFIX = re.compile(
    r"^\s*(?:" + "|".join(re.escape(name) for name in _PROCESSORS) + r")\s*[*_]+[*_\s]*",
    re.IGNORECASE,
)

# Wise: "Card transaction of 12.50 EUR issued by Albert Heijn Eindhoven"
_WISE_CARD = re.compile(
    r"^card transaction of .*? issued by\s+(.+)$",
    re.IGNORECASE,
)

# ING and other Dutch banks: "BEA, Apple Pay ...", "GEA, Betaalpas ..."
_CARD_TYPE_PREFIX = re.compile(
    r"^\s*(?:BEA|GEA|POS)\s*[,:]?\s*(?:(?:APPLE|GOOGLE)\s+PAY|BETAALPAS|BANKPAS)?\s*[,:]?\s*",
    re.IGNORECASE,
)

# Card, terminal and transaction codes, plus dates and times.
_CODES = re.compile(
    r"""
    (?:\b(?:PASVOLGNR|PASNR|PAS|TRANSACTIE|TERM|TERMINAL|NR|REF|KENMERK)
        \s*[:.]?\s*[\w./-]*\d[\w./-]*)        # Pasvolgnr: 001, NR:ABC123
    | (?:\b\d{1,2}[-./]\d{1,2}[-./]\d{2,4}\b)  # 06.09.26, 06-09-2026
    | (?:\b\d{1,2}[:.]\d{2}(?::\d{2})?\b)      # 12:34, 12:34:56
    | (?:/\d{1,2}[:.]\d{2})                    # /12:34
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Legal forms at the end of a name: "Jansen B.V." is the same as "Jansen".
_LEGAL_SUFFIX = re.compile(
    r"[\s,]+(?:B\.?V\.?|N\.?V\.?|V\.?O\.?F\.?|GMBH|LTD|INC|LLC|S\.?A\.?|AB)\.?\s*$",
    re.IGNORECASE,
)


def clean_merchant(description):
    """
    A readable merchant name: processor prefixes, card codes, dates and
    legal suffixes removed. Falls back to the original text if nothing
    sensible remains.
    """

    original = str(description).strip()
    text = original

    match = _WISE_CARD.match(text)
    if match:
        text = match.group(1)

    text = _CARD_TYPE_PREFIX.sub("", text)

    # Processors can be nested ("PayPal *SumUp *Shop"), so repeat.
    for _ in range(3):
        stripped = _PROCESSOR_PREFIX.sub("", text)

        if stripped == text:
            break

        text = stripped

    text = _CODES.sub(" ", text)
    text = _LEGAL_SUFFIX.sub("", text)

    # Tidy separators and spaces left behind.
    text = re.sub(r"\s*,\s*(?=,|$)", "", text)
    text = re.sub(r"\s+", " ", text).strip(" ,;:-*_/")

    return text or original


def normalize_merchant(description):
    """
    A key for recognizing the same merchant: 'Albert Heijn 1234',
    'ALBERT HEIJN' and 'SumUp *Albert Heijn B.V.' all become
    'ALBERT HEIJN'.

    Words containing digits are reference codes that change from payment
    to payment, so they are dropped.
    """

    text = clean_merchant(description)

    words = [
        word
        for word in text.upper().split()
        if not re.search(r"\d", word)
    ]

    key = re.sub(r"[^A-Z ]", " ", " ".join(words))
    key = re.sub(r"\s+", " ", key).strip()

    # Descriptions without letters (e.g. only a reference number)
    # are kept as they are.
    return key or str(description).strip().upper()
