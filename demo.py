"""
Demo data that always looks current.

The demo statements in sample_data/ are fixed files (March to mid-September
2026). This module moves every date forward by whole months, so the demo's
last month is the most recent month that has already happened, without
changing any amounts or the story the data tells:

- Netflix's price rise, a new subscription and a double charge still
  appear in the second-to-last and third-to-last months;
- the last month is still half-finished, so the forecast still shows.

Shifting by whole months keeps the day of the month (rent on the 2nd,
Spotify on the 5th), which recurring-payment detection relies on.
Days that don't exist in the target month (30 February) move to the
month's last day.
"""

import csv
import io
from pathlib import Path

import pandas as pd

SAMPLE_DATA = Path(__file__).parent / "sample_data"

DEMO_ING = SAMPLE_DATA / "demo_ing.csv"
DEMO_REVOLUT = SAMPLE_DATA / "demo_revolut.csv"

# The latest transaction in the demo files, as stored on disk.
DEMO_LAST_DATE = pd.Timestamp("2026-09-20")

MONTH_NAMES = [
    "JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE",
    "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER",
]


def months_to_shift(today=None):
    """
    How many months to move the demo forward.

    The demo's last month becomes the latest month in which the demo's
    last transaction (the 20th) is not in the future. On 1 October that
    is still September; from 20 October it is October.
    """

    today = pd.Timestamp(today or pd.Timestamp.today()).normalize()

    months = (
        (today.year - DEMO_LAST_DATE.year) * 12
        + (today.month - DEMO_LAST_DATE.month)
    )

    if DEMO_LAST_DATE + pd.DateOffset(months=months) > today:
        months -= 1

    return months


def _shift(timestamp, months):
    return timestamp + pd.DateOffset(months=months)


def _shift_text(text, months, original_date):
    """
    Update month references in ING descriptions, e.g. "SALARY SEPTEMBER"
    or "SALARY 2026-03", so they match the shifted date.
    """

    shifted = _shift(original_date, months)

    old_name = MONTH_NAMES[original_date.month - 1]
    new_name = MONTH_NAMES[shifted.month - 1]

    text = text.replace(original_date.strftime("%Y-%m"), shifted.strftime("%Y-%m"))

    return text.replace(old_name, new_name)


def shifted_ing(months):
    """demo_ing.csv with every date moved forward by `months` months."""

    with open(DEMO_ING, encoding="utf-8", newline="") as file:
        rows = list(csv.reader(file, delimiter=";"))

    header, body = rows[0], rows[1:]
    date_column = header.index("Datum")
    text_column = header.index("Mededelingen")

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_ALL, lineterminator="\n")
    writer.writerow(header)

    for row in body:
        original = pd.Timestamp(row[date_column])

        row = list(row)
        row[date_column] = _shift(original, months).strftime("%Y%m%d")
        row[text_column] = _shift_text(row[text_column], months, original)

        writer.writerow(row)

    return output.getvalue().encode("utf-8")


def shifted_revolut(months):
    """demo_revolut.csv with every date moved forward by `months` months."""

    with open(DEMO_REVOLUT, encoding="utf-8", newline="") as file:
        rows = list(csv.reader(file))

    header, body = rows[0], rows[1:]
    date_columns = [header.index("Started Date"), header.index("Completed Date")]

    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(header)

    for row in body:
        row = list(row)

        for column in date_columns:
            row[column] = _shift(
                pd.Timestamp(row[column]), months
            ).strftime("%Y-%m-%d %H:%M:%S")

        writer.writerow(row)

    return output.getvalue().encode("utf-8")


def demo_files(today=None):
    """
    The demo statements as (file name, file bytes), dated so that they
    end in the most recent month. Same files as the app's uploads expect.
    """

    months = months_to_shift(today)

    return (
        (DEMO_ING.name, shifted_ing(months)),
        (DEMO_REVOLUT.name, shifted_revolut(months)),
    )
