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


# ------------------------------------------------------------
# Day-first or month-first
# ------------------------------------------------------------

TODAY = "2026-10-01"


def test_us_style_dates_saved_by_excel():
    # Regression: 11 March was read as 3 November and 12 June as
    # 6 December, so statements ending in September showed November
    # and December.
    result = parse_dates(
        pd.Series(["3/11/2026", "4/2/2026", "6/12/2026", "8/15/2026", "9/6/2026"]),
        today=TODAY,
    )

    assert as_strings(result) == [
        "2026-03-11",
        "2026-04-02",
        "2026-06-12",
        "2026-08-15",
        "2026-09-06",
    ]


def test_european_dates_stay_day_first():
    result = parse_dates(
        pd.Series(["11-03-2026", "12-06-2026", "15-08-2026", "06-09-2026"]),
        today=TODAY,
    )

    assert as_strings(result) == ["2026-03-11", "2026-06-12", "2026-08-15", "2026-09-06"]


def test_ambiguous_dates_avoid_the_future():
    # Read day-first, 02/11/2026 would be 2 November: in the future.
    # Month-first (11 February) is the only sensible reading.
    result = parse_dates(
        pd.Series(["01/05/2026", "02/11/2026", "06/09/2026"]),
        today=TODAY,
    )

    assert as_strings(result) == ["2026-01-05", "2026-02-11", "2026-06-09"]


def test_fully_ambiguous_dates_default_to_day_first():
    result = parse_dates(pd.Series(["01/02/2026", "03/04/2026"]), today=TODAY)

    assert as_strings(result) == ["2026-02-01", "2026-04-03"]


def test_two_digit_years():
    result = parse_dates(pd.Series(["3/11/26", "8/15/26"]), today=TODAY)

    assert as_strings(result) == ["2026-03-11", "2026-08-15"]


def test_short_dates_with_times():
    result = parse_dates(pd.Series(["06-09-2026 12:34:56", "15-08-2026 08:00:00"]), today=TODAY)

    assert as_strings(result) == ["2026-09-06", "2026-08-15"]


def test_iso_dates_with_fractional_seconds():
    # Regression: the "." in 12:34:56.789 was treated as a date separator.
    result = parse_dates(pd.Series(["2026-09-06 12:34:56.789", "2026/08/15 08:00:00.001"]))

    assert as_strings(result) == ["2026-09-06", "2026-08-15"]
