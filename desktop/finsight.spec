# Build settings for the Finsight desktop experiment.
#
# Run from the project folder:
#
#     pyinstaller desktop/finsight.spec --noconfirm
#
# The result is the folder dist/Finsight/ with Finsight.exe in it.

import os

from PyInstaller.utils.hooks import collect_all, copy_metadata

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))


def project_modules():
    """
    Finsight's own Python files as module names ("pipeline",
    "views.overview", ...). Streamlit runs app.py as a script, so
    PyInstaller can't discover on its own what app.py imports.
    """

    modules = []

    for name in sorted(os.listdir(ROOT)):
        if name.endswith(".py") and name != "app.py":
            modules.append(name[:-3])

    for package in ("views", "parsers"):
        for name in sorted(os.listdir(os.path.join(ROOT, package))):
            if name.endswith(".py") and name != "__init__.py":
                modules.append(f"{package}.{name[:-3]}")

        modules.append(package)

    return modules


datas = []
binaries = []
hiddenimports = []

# Streamlit and Plotly ship files that aren't Python code (the web page,
# chart templates); they have to be copied in as well.
for package in ("streamlit", "plotly"):
    package_datas, package_binaries, package_imports = collect_all(package)

    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_imports

# Streamlit looks up its own version at startup.
datas += copy_metadata("streamlit")

# Finsight's own files that are read at run time.
datas += [
    (os.path.join(ROOT, "app.py"), "."),
    (os.path.join(ROOT, "styles"), "styles"),
    (os.path.join(ROOT, "sample_data"), "sample_data"),
    (os.path.join(ROOT, ".streamlit", "config.toml"), ".streamlit"),
]

hiddenimports += project_modules()
hiddenimports += ["pandas", "openpyxl"]

analysis = Analysis(
    [os.path.join(SPECPATH, "launcher.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tests", "pytest"],
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="Finsight",
    # No black console window behind the app.
    console=False,
)

COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    name="Finsight",
)
