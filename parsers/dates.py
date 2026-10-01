import re

import pandas as pd

# 2026-09-01, 2026/09/01, 2026-09-01 09:00:00, 2026-09-01T09:00:00
_ISO_PATTERN = r"^\d{4}[-/.]\d{1,2}[-/.]\d{1,2}([ T].*)?$"

# 20260901 (used by ING)
_COMPACT_PATTERN = r"^\d{8}$"


def parse_dates(series: pd.Series) -> pd.Series:
    """
    Convert a column of date strings into datetimes.

    Year-first dates (ISO, e.g. 2026-03-01) are never read day-first:
    doing so turns 1 March into 3 January and makes any day above 12
    unparseable. Only ambiguous formats such as 01-03-2026 are read
    day-first, which matches European bank exports.

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
            values.str.replace("/", "-").str.replace(".", "-", regex=False),
            format="ISO8601",
            errors="coerce",
        )

    return pd.to_datetime(
        values,
        format="mixed",
        dayfirst=True,
        errors="coerce",
    )
