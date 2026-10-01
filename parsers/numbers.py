"""
Turn amounts written in bank exports into numbers.

Banks write the same amount in different ways: 1234.56, 1234,56,
1.234,56, 1,234.56, "+12,50", "€ 12,50". Every parser uses the same
rules, so they all read amounts the same way.
"""

import re

import pandas as pd

# Currency symbols, spaces (incl. non-breaking) and apostrophes used as
# thousands separators (1'234.56).
_NOISE = re.compile(r"[€$£\s ']")


def parse_number(value):
    """
    Convert one written amount into a float, or None if it isn't one.

    - Both "," and "." present: the last one is the decimal separator
      (1.234,56 and 1,234.56 are both 1234.56).
    - Only ",": it is the decimal separator (12,50), unless it is used
      more than once (1,234,567 is a thousands separator).
    - Only ".": it is the decimal separator (12.50), unless it is used
      more than once (1.234.567).
    """

    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None

    text = _NOISE.sub("", str(value))

    if text in ("", "-", "+"):
        return None

    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")

    elif "," in text:
        if text.count(",") > 1:
            text = text.replace(",", "")
        else:
            text = text.replace(",", ".")

    elif text.count(".") > 1:
        text = text.replace(".", "")

    try:
        return float(text)

    except ValueError:
        return None


def parse_numbers(series):
    """parse_number for a whole column; unreadable values become NaN."""

    return pd.to_numeric(series.map(parse_number), errors="coerce")
