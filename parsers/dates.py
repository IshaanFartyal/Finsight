import re

import pandas as pd

# 2026-09-01, 2026/09/01, 2026-09-01 09:00:00, 2026-09-01T09:00:00.123
_ISO_PATTERN = r"^\d{4}[-/.]\d{1,2}[-/.]\d{1,2}([ T].*)?$"

# Only the date part of a year-first date, to normalize its separators
# without touching a time like 12:34:56.789.
_ISO_DATE_PART = r"^(\d{4})[/.](\d{1,2})[/.](\d{1,2})"

# 20260901 (used by ING)
_COMPACT_PATTERN = r"^\d{8}$"

# 06-09-2026, 6/9/26, 06.09.2026 12:00 ... : day and month in either order
_SHORT_PATTERN = r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})(?:[ T].*)?$"


def _parse(values, day_first):
    return pd.to_datetime(
        values,
        format="mixed",
        dayfirst=day_first,
        errors="coerce",
    )


def _score(parsed, today):
    """
    How plausible a reading of a date column is (higher is better):
    no transactions in the future, then rows in date order (bank exports
    are sorted, oldest or newest first).
    """

    dates = parsed.dropna()

    future = int((dates > today + pd.Timedelta(days=1)).sum())

    steps = dates.diff().dropna()
    in_order = (
        max((steps >= pd.Timedelta(0)).mean(), (steps <= pd.Timedelta(0)).mean())
        if len(steps)
        else 1.0
    )

    return (-future, in_order)


def detect_day_first(values, today=None):
    """
    Decide whether short dates like 03/11/2026 are day-first (European,
    3 November) or month-first (US, and what Excel writes on a US-style
    Windows: 11 March), using the whole column.

    - A first number above 12 (15/08/2026) means day-first.
    - A second number above 12 (8/15/2026) means month-first.
    - If every date is ambiguous, the reading that keeps transactions out
      of the future and in date order wins; a tie means day-first.
    """

    today = pd.Timestamp(today or pd.Timestamp.today()).normalize()

    parts = values.str.extract(_SHORT_PATTERN)

    if parts[0].isna().any():
        return True

    first = parts[0].astype(int)
    second = parts[1].astype(int)

    first_over_12 = bool((first > 12).any())
    second_over_12 = bool((second > 12).any())

    if first_over_12 and not second_over_12:
        return True

    if second_over_12 and not first_over_12:
        return False

    if first_over_12 and second_over_12:
        # Inconsistent column: read each date as best we can.
        return True

    day_first_score = _score(_parse(values, True), today)
    month_first_score = _score(_parse(values, False), today)

    return day_first_score >= month_first_score


def parse_dates(series: pd.Series, today=None) -> pd.Series:
    """
    Convert a column of date strings into datetimes.

    - Year-first dates (ISO, e.g. 2026-03-01) are never read day-first:
      doing so turns 1 March into 3 January.
    - Short dates (03/11/2026) are read day-first or month-first depending
      on the whole column (see detect_day_first), so files saved by Excel
      with US-style dates work too.

    Unparseable values become NaT.
    """

    values = series.fillna("").astype(str).str.strip()
    non_empty = values[values != ""]

    if non_empty.empty:
        return pd.to_datetime(values, errors="coerce")

    if non_empty.str.match(_COMPACT_PATTERN).all():
        return pd.to_datetime(values, format="%Y%m%d", errors="coerce")

    if non_empty.str.match(_ISO_PATTERN).all():
        return pd.to_datetime(
            values.str.replace(_ISO_DATE_PART, r"\1-\2-\3", regex=True),
            format="ISO8601",
            errors="coerce",
        )

    day_first = detect_day_first(non_empty, today)

    return _parse(values, day_first)
