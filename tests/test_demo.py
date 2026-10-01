import pandas as pd
import pytest

from analytics import calculate_summary
from categorizer import DEFAULT_CATEGORY_RULES
from corrections import empty_corrections
from demo import demo_files, months_to_shift, shifted_ing, shifted_revolut
from flows import default_settings
from insights import (
    duplicate_charges,
    month_end_forecast,
    new_recurring,
    price_changes,
)
from pipeline import build_transactions
from statements import parse_statement
from tests.helpers import SAMPLE_DATA


def build(files):
    df, _, failed = build_transactions(
        list(files),
        DEFAULT_CATEGORY_RULES,
        default_settings(),
        empty_corrections(),
    )

    assert failed == {}

    return df


@pytest.mark.parametrize(
    "today, months",
    [
        ("2026-09-20", 0),
        ("2026-10-01", 0),   # 20 October hasn't happened yet
        ("2026-10-19", 0),
        ("2026-10-20", 1),
        ("2027-03-01", 5),
        ("2027-12-31", 15),
    ],
)
def test_months_to_shift(today, months):
    assert months_to_shift(today) == months


def test_no_shift_reproduces_the_files_on_disk():
    for name, shifted in (("demo_ing.csv", shifted_ing(0)), ("demo_revolut.csv", shifted_revolut(0))):
        original = parse_statement((SAMPLE_DATA / name).read_bytes())[1]

        assert parse_statement(shifted)[1].equals(original)


@pytest.mark.parametrize("today", ["2026-10-25", "2027-03-01", "2027-06-21", "2028-02-29"])
def test_demo_never_shows_future_transactions(today):
    df = build(demo_files(today))

    assert df["date"].max() <= pd.Timestamp(today)


def test_demo_ends_in_the_current_month_after_the_20th():
    df = build(demo_files("2027-05-25"))

    assert str(df["month"].max()) == "2027-05"


def test_amounts_are_unchanged_by_shifting():
    original = build(demo_files("2026-09-25"))
    shifted = build(demo_files("2027-05-25"))

    assert len(shifted) == len(original)
    assert shifted["amount"].sum() == pytest.approx(original["amount"].sum())


def test_ing_descriptions_follow_the_new_months():
    text = shifted_ing(5).decode("utf-8")

    assert "SALARY FEBRUARY" in text
    assert "HUUR FEBRUARY" in text
    assert "SALARY 2027-01" in text
    assert "SEPTEMBER" not in text


# Every month shift over the next three years, including ones that put
# demo months in February and across year ends.
@pytest.mark.parametrize("months", range(0, 37))
def test_demo_story_survives_every_shift(months):
    files = (("demo_ing.csv", shifted_ing(months)), ("demo_revolut.csv", shifted_revolut(months)))
    df = build(files)

    last = df["month"].max()
    previous = last - 1
    before = last - 2

    # The story, relative to the last month:
    assert price_changes(df, before)["merchant"].tolist() == ["Netflix"]
    assert duplicate_charges(df, previous)["merchant"].tolist() == ["Zalando"]
    assert new_recurring(df, previous)["merchant"].tolist() == ["Disney Plus"]
    assert month_end_forecast(df, last) is not None

    summary = calculate_summary(df[df["month"] == last])

    assert summary["income"] == pytest.approx(2600.0)
    assert summary["transfers_out"] > 0
    assert summary["refunds"] > 0
    assert summary["fees"] > 0
