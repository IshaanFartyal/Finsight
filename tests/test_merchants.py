import pytest

from merchants import clean_merchant, normalize_merchant


@pytest.mark.parametrize(
    "description, merchant",
    [
        ("SumUp  *Bakkerij Jansen", "Bakkerij Jansen"),
        ("CCV*CAFE DE ZWAAN", "CAFE DE ZWAAN"),
        ("Zettle_*Kapsalon Mooi", "Kapsalon Mooi"),
        ("PayPal *Netflix", "Netflix"),
        ("PAY.NL*Thuisbezorgd.nl", "Thuisbezorgd.nl"),
        ("SQ *COFFEE COMPANY", "COFFEE COMPANY"),
        ("Card transaction of 12.50 EUR issued by Albert Heijn Eindhoven", "Albert Heijn Eindhoven"),
        ("BEA, Apple Pay ALBERT HEIJN 1234,PAS123 NR:ABC123, 06.09.26/12:34", "ALBERT HEIJN 1234"),
        ("Jansen B.V.", "Jansen"),
        ("Fietsenmaker Smit BV", "Fietsenmaker Smit"),
        # Left alone
        ("Bol.com", "Bol.com"),
        ("Stripe Payments Europe", "Stripe Payments Europe"),
        ("Sparkasse", "Sparkasse"),
        ("12345", "12345"),
    ],
)
def test_clean_merchant(description, merchant):
    assert clean_merchant(description) == merchant


@pytest.mark.parametrize(
    "variants",
    [
        ["SumUp *Bakkerij Jansen", "SUMUP  *BAKKERIJ JANSEN", "Bakkerij Jansen B.V."],
        ["Spotify P1A2B3", "SPOTIFY", "PayPal *Spotify"],
        ["ALBERT HEIJN 1234", "BEA, Apple Pay ALBERT HEIJN 5678,PAS001 NR:XY12, 01.09.26/09:15"],
        ["Bol.com", "BOL.COM 4401"],
    ],
)
def test_variants_of_one_merchant_share_a_key(variants):
    keys = {normalize_merchant(variant) for variant in variants}

    assert len(keys) == 1


def test_different_merchants_keep_different_keys():
    assert normalize_merchant("SumUp *Bakkerij Jansen") != normalize_merchant("SumUp *Kapsalon Mooi")
