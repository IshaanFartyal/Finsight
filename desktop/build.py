"""
Build the Finsight desktop app and a zip to share with testers.

Run from the project folder:

    python desktop/build.py

Results:

    dist/Finsight/                      the program (Finsight.exe + files)
    dist/Finsight-<version>-<system>.zip  the same folder, zipped

A build only runs on the kind of computer it was made on: build on
Windows for Windows.
"""

import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
SPEC = Path(__file__).resolve().parent / "finsight.spec"

sys.path.insert(0, str(ROOT))

from version import __version__  # noqa: E402


def system_name():
    """ "windows", "macos" or "linux"."""

    return {"Darwin": "macos"}.get(platform.system(), platform.system().lower())


def zip_name(version=__version__, system=None):
    return f"Finsight-{version}-{system or system_name()}"


def folder_size_mb(folder):
    total = sum(file.stat().st_size for file in Path(folder).rglob("*") if file.is_file())

    return total / (1024 * 1024)


def build():
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", str(SPEC), "--noconfirm"],
        cwd=ROOT,
        check=True,
    )


def make_zip():
    """Zip dist/Finsight so that the zip contains one folder, Finsight/."""

    archive = shutil.make_archive(
        str(DIST / zip_name()),
        "zip",
        root_dir=DIST,
        base_dir="Finsight",
    )

    return Path(archive)


def main():
    build()

    archive = make_zip()

    print()
    print(f"Program: {DIST / 'Finsight'}  ({folder_size_mb(DIST / 'Finsight'):.0f} MB)")
    print(f"Zip:     {archive}  ({archive.stat().st_size / (1024 * 1024):.0f} MB)")


if __name__ == "__main__":
    main()
