"""
Where Finsight keeps the user's own files: rules.json, settings.json,
corrections.json and budgets.json.

Normally that is the project folder, next to the code. The desktop app
(desktop/launcher.py) sets FINSIGHT_DATA_DIR, because a built program
can't write into its own folder; the files then live in the user's own
data folder (on Windows: %LOCALAPPDATA%\\Finsight).
"""

import os
from pathlib import Path

DATA_DIR_SETTING = "FINSIGHT_DATA_DIR"

PROJECT_FOLDER = Path(__file__).parent


def data_dir(environ=None):
    """
    The folder for the user's files. Created if it doesn't exist yet.
    """

    environ = os.environ if environ is None else environ

    chosen = str(environ.get(DATA_DIR_SETTING, "")).strip()

    if not chosen:
        return PROJECT_FOLDER

    folder = Path(chosen).expanduser()
    folder.mkdir(parents=True, exist_ok=True)

    return folder


def data_path(file_name, environ=None):
    """Full path of one of the user's files, e.g. data_path("rules.json")."""

    return data_dir(environ) / file_name


# Everything Finsight saves for the user. Bank statements are never
# saved, so they are not in this list.
USER_FILES = [
    "rules.json",
    "settings.json",
    "corrections.json",
    "budgets.json",
    # Error messages of the desktop app (desktop/launcher.py).
    "finsight.log",
]


def saved_files(environ=None):
    """The names of the user's files that exist right now."""

    folder = data_dir(environ)

    return [name for name in USER_FILES if (folder / name).is_file()]


def delete_user_files(environ=None):
    """
    Delete everything Finsight saved for the user. Returns
    (deleted, failed): two lists of file names.

    Only the files in USER_FILES are touched, never the folder itself
    or anything else in it.
    """

    folder = data_dir(environ)

    deleted = []
    failed = []

    for name in saved_files(environ):
        path = folder / name

        try:
            path.unlink()
            deleted.append(name)
            continue

        except OSError:
            pass

        # A file that is in use can't be deleted on Windows (the desktop
        # app keeps its log open): empty it instead.
        try:
            path.write_text("", encoding="utf-8")
            deleted.append(name)

        except OSError:
            failed.append(name)

    return deleted, failed

