import pandas as pd
import pytest

from budgets import clean_goal, save_budgets
from categorizer import save_rules
from corrections import empty_corrections, save_corrections
from demo import DEMO_EXCHANGE_RATES, demo_budgets
from flows import default_settings, save_settings
from hosting import is_hosted, save_if_local, storage_note


@pytest.mark.parametrize(
    "value, expected",
    [("true", True), ("TRUE", True), ("1", True), ("yes", True), ("false", False), ("", False), ("0", False)],
)
def test_hosted_from_environment(value, expected):
    assert is_hosted(environ={"FINSIGHT_HOSTED": value}) is expected


def test_not_hosted_without_the_setting():
    assert is_hosted(environ={}) is False


def test_hosted_from_secrets():
    assert is_hosted(environ={}, secrets={"FINSIGHT_HOSTED": "true"}) is True
    assert is_hosted(environ={}, secrets={}) is False


def test_missing_secrets_file_means_not_hosted():
    class MissingSecrets:
        def get(self, *args):
            raise FileNotFoundError("No secrets file found")

    assert is_hosted(environ={}, secrets=MissingSecrets()) is False


@pytest.mark.parametrize(
    "save, data",
    [
        (save_rules, {"Groceries": ["JUMBO"]}),
        (save_settings, default_settings()),
        (save_corrections, empty_corrections()),
        (save_budgets, {"budgets": {"Groceries": 100.0}, "goals": []}),
    ],
)
def test_hosted_mode_never_writes_files(tmp_path, save, data):
    path = tmp_path / "saved.json"

    saved = save_if_local(lambda value: save(value, path), data, hosted=True)

    assert saved is False
    assert not path.exists()


def test_local_mode_saves(tmp_path):
    path = tmp_path / "rules.json"

    assert save_if_local(lambda value: save_rules(value, path), {"A": ["B"]}, hosted=False)
    assert path.exists()


def test_storage_note():
    assert "this computer" in storage_note(hosted=False)
    assert "session" in storage_note(hosted=True)


def test_demo_budgets_are_valid_and_dated_ahead():
    data = demo_budgets("2026-10-01")

    assert all(amount > 0 for amount in data["budgets"].values())
    assert [clean_goal(goal) for goal in data["goals"]] == data["goals"]
    assert pd.Timestamp(data["goals"][0]["deadline"]) > pd.Timestamp("2026-10-01")


def test_demo_exchange_rate_covers_the_demo_currency():
    assert "USD" in DEMO_EXCHANGE_RATES


def test_disclaimer_warns_against_real_data_and_links_to_the_code():
    from hosting import DISCLAIMER, REPO_URL, SIDEBAR_NOTICE

    for text in (DISCLAIMER, SIDEBAR_NOTICE):
        assert "real personal" in text
        assert REPO_URL in text

    assert "IBAN" in DISCLAIMER


@pytest.mark.parametrize("value, expected", [("true", True), ("1", True), ("", False), ("false", False)])
def test_private_by_default(value, expected):
    from hosting import private_by_default

    assert private_by_default(environ={"FINSIGHT_PRIVATE": value}) is expected


def test_storage_note_in_a_private_session():
    note = storage_note(hosted=False, private=True)

    assert "nothing is saved to disk" in note
    # The online demo keeps its own wording.
    assert storage_note(hosted=True, private=True) == storage_note(hosted=True)


def test_private_by_default_from_secrets():
    from hosting import private_by_default

    assert private_by_default(environ={}, secrets={"FINSIGHT_PRIVATE": "true"}) is True
    assert private_by_default(environ={}, secrets={}) is False


def test_private_setting_does_not_switch_on_hosted_mode():
    secrets = {"FINSIGHT_PRIVATE": "true"}

    assert is_hosted(environ={}, secrets=secrets) is False
