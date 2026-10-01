import pandas as pd

from parsers.dates import parse_dates


def as_strings(series):
    return [
        value.strftime("%Y-%m-%d") if not pd.isna(value) else None
        for value in series
    ]


def test_iso_dates_are_not_read_day_first():
    # Regression test: dayfirst=True used to turn 1 March into
    # 3 January and drop any date with a day above 12.
    result = parse_dates(pd.Series(["2026-03-01", "2026-03-15"]))

    assert as_strings(result) == ["2026-03-01", "2026-03-15"]


def test_iso_datetimes():
    result = parse_dates(pd.Series(["2026-09-01 09:00:00"]))

    assert result.iloc[0] == pd.Timestamp("2026-09-01 09:00:00")


def test_compact_ing_dates():
    result = parse_dates(pd.Series(["20260912"]))

    assert as_strings(result) == ["2026-09-12"]


def test_european_dates_are_read_day_first():
    result = parse_dates(pd.Series(["01-03-2026", "15/03/2026"]))

    assert as_strings(result) == ["2026-03-01", "2026-03-15"]


def test_empty_and_invalid_values_become_nat():
    result = parse_dates(pd.Series(["", None, "not a date"]))

    assert result.isna().all()
