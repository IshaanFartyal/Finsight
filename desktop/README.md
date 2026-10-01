# Finsight desktop app (beta)

The same Finsight, shown in its own window instead of a browser tab, and
built into a program that runs without Python installed.

`launcher.py` starts the normal app in the background and displays it.

## Try the window (no build)

```powershell
python -m pip install -r desktop/requirements.txt
python desktop/launcher.py
```

## Build the program (Windows)

```powershell
python desktop/build.py
```

This creates:

- `dist\Finsight\`: the program. `Finsight.exe` needs the files next to
  it, so always move or share the whole folder.
- `dist\Finsight-<version>-windows.zip`: the same folder zipped, to send
  to testers. They unzip it and double-click `Finsight.exe`.

The version number comes from `version.py` in the project folder.

## Where your files are kept

The desktop app saves your rules, settings, corrections and budgets in
your own data folder, not next to the program:

| System  | Folder                                    |
|---------|-------------------------------------------|
| Windows | `%LOCALAPPDATA%\Finsight`                  |
| macOS   | `~/Library/Application Support/Finsight`  |
| Linux   | `~/.local/share/Finsight`                 |

On Windows this is the "Local" folder, which stays on this computer; the
"Roaming" folder (`%APPDATA%`) can be copied to a server on managed
networks. Settings shows the exact folder. **Settings > Saved data > Delete all saved data** removes these files
from inside the app; deleting the folder by hand does the same. Bank
statements are never saved there or anywhere else.

`finsight.log` in the same folder holds the error messages of the last
run of the built program; it starts empty on every launch.

Running Finsight the normal way (`streamlit run app.py`) still keeps
these files in the project folder.

## For testers

- Windows shows "Windows protected your PC" the first time, because the
  program isn't signed. Choose **More info > Run anyway**.
- The window uses Microsoft Edge WebView2, which is part of Windows 11
  and most Windows 10 installations.

## Before sharing a build

Test the zip on a computer without Python installed: unzip, start
`Finsight.exe`, load the demo data, upload a sample file, export.
