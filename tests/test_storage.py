from storage import (
    PROJECT_FOLDER,
    data_dir,
    data_path,
    delete_user_files,
    saved_files,
)


def test_project_folder_by_default():
    assert data_dir({}) == PROJECT_FOLDER
    assert data_path("rules.json", {}) == PROJECT_FOLDER / "rules.json"


def test_empty_setting_means_project_folder():
    assert data_dir({"FINSIGHT_DATA_DIR": "  "}) == PROJECT_FOLDER


def test_chosen_folder_is_created(tmp_path):
    folder = tmp_path / "Finsight" / "data"

    environ = {"FINSIGHT_DATA_DIR": str(folder)}

    assert data_dir(environ) == folder
    assert folder.is_dir()
    assert data_path("settings.json", environ) == folder / "settings.json"


def test_settings_files_follow_the_data_folder():
    # The four files Finsight saves all use the same folder.
    import budgets
    import categorizer
    import corrections
    import flows

    assert budgets.BUDGETS_PATH == data_path("budgets.json")
    assert categorizer.RULES_PATH == data_path("rules.json")
    assert corrections.CORRECTIONS_PATH == data_path("corrections.json")
    assert flows.SETTINGS_PATH == data_path("settings.json")


def test_delete_removes_only_finsight_files(tmp_path):
    environ = {"FINSIGHT_DATA_DIR": str(tmp_path)}

    for name in ("rules.json", "budgets.json", "finsight.log"):
        (tmp_path / name).write_text("{}", encoding="utf-8")

    # Not Finsight's: must be left alone.
    (tmp_path / "statement.csv").write_text("my data", encoding="utf-8")
    (tmp_path / "notes.json").write_text("{}", encoding="utf-8")

    assert saved_files(environ) == ["rules.json", "budgets.json", "finsight.log"]

    deleted, failed = delete_user_files(environ)

    assert deleted == ["rules.json", "budgets.json", "finsight.log"]
    assert failed == []
    assert saved_files(environ) == []
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "notes.json",
        "statement.csv",
    ]


def test_delete_with_nothing_saved(tmp_path):
    environ = {"FINSIGHT_DATA_DIR": str(tmp_path)}

    assert saved_files(environ) == []
    assert delete_user_files(environ) == ([], [])

