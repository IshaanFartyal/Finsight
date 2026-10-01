import csv
import io

import pandas as pd

# Separators bank exports use. Tab-separated files are read too.
SEPARATORS = [";", ",", "\t"]

# Tried in this order. UTF-8 first; older Dutch bank exports are often
# Windows-1252 ("Café" saved as a single é byte), which can read any
# byte, so it comes last.
ENCODINGS = ["utf-8-sig", "cp1252"]


def _decode(raw):
    for encoding in ENCODINGS:
        try:
            return raw.decode(encoding), encoding

        except UnicodeDecodeError:
            continue

    raise ValueError("Could not read the file's text encoding.")


def _detect_separator(text):
    """
    Pick the separator that splits the header row into the most columns,
    reading quotes properly ("Bedrag (EUR)";"12,50" has one ";" that
    counts and one "," that doesn't). Falls back to csv.Sniffer when the
    header row doesn't decide.
    """

    lines = [line for line in text.splitlines() if line.strip()]

    if not lines:
        raise ValueError("The file is empty.")

    header = lines[0]

    counts = {
        separator: len(next(csv.reader([header], delimiter=separator)))
        for separator in SEPARATORS
    }

    best = max(counts.values())
    winners = [separator for separator, count in counts.items() if count == best]

    if best > 1 and len(winners) == 1:
        return winners[0]

    try:
        return csv.Sniffer().sniff(
            "\n".join(lines[:50]),
            delimiters="".join(SEPARATORS),
        ).delimiter

    except csv.Error:
        raise ValueError("Could not determine CSV separator.")


def load_bank_csv(file):
    """
    Load a bank CSV with automatic separator (; , or tab) and encoding
    (UTF-8 or Windows-1252) detection. Every value is kept as text; the
    parsers convert dates and amounts.
    """

    file.seek(0)
    raw = file.read()

    if isinstance(raw, str):
        text = raw
    else:
        text, _ = _decode(raw)

    separator = _detect_separator(text)

    return pd.read_csv(
        io.StringIO(text),
        sep=separator,
        dtype=str,
    )
