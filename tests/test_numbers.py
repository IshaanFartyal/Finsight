import pytest

from parsers.numbers import parse_number


@pytest.mark.parametrize(
    "text, expected",
    [
        ("12,50", 12.50),
        ("12.50", 12.50),
        ("1.234,56", 1234.56),
        ("1,234.56", 1234.56),
        ("1.234.567", 1234567.0),
        ("1,234,567", 1234567.0),
        ("-25,00", -25.00),
        ("+12,50", 12.50),
        ("€ 12,50", 12.50),
        ("1 234,56", 1234.56),
        ("0", 0.0),
    ],
)
def test_reads_common_formats(text, expected):
    assert parse_number(text) == pytest.approx(expected)


@pytest.mark.parametrize("text", ["", " ", "-", "abc", None])
def test_unreadable_values(text):
    assert parse_number(text) is None
