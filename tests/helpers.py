from pathlib import Path

from parsers.detector import detect_bank
from parsers.generic import parse_generic
from parsers.loader import load_bank_csv
from statements import PARSERS

SAMPLE_DATA = Path(__file__).parent.parent / "sample_data"


def load_sample(file_name):
    """Load, detect and parse a sample file the same way the app does."""

    with open(SAMPLE_DATA / file_name, "rb") as file:
        raw_df = load_bank_csv(file)

    bank = detect_bank(raw_df)
    parser = PARSERS.get(bank, parse_generic)

    return bank, raw_df, parser(raw_df)
