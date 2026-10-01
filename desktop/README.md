# Finsight desktop experiment

A trial to see what Finsight looks like as a desktop program: the same
app, shown in its own window instead of a browser tab, and built into a
program that runs without Python installed.

Nothing in Finsight itself is changed. `launcher.py` starts the normal
app in the background and displays it.

## Try the window (no build)

```powershell
python -m pip install -r desktop/requirements.txt
python desktop/launcher.py
```

## Build the program (Windows)

```powershell
pyinstaller desktop/finsight.spec --noconfirm
dist\Finsight\Finsight.exe
```

The whole `dist\Finsight` folder is the program; `Finsight.exe` doesn't
work without the files next to it.

## What to look at

- **Size** of the `dist\Finsight` folder.
- **Startup time**: from double-click to a usable window.
- **What breaks**: upload, demo data, every page, CSV/Excel export.

## Known limits of this experiment

- **Nothing is saved between runs.** It starts as a private session,
  because Finsight's settings files would otherwise be written inside
  the program's own folder. A real desktop version needs a proper place
  for them (on Windows: `%APPDATA%\Finsight`).
- The window uses Microsoft Edge WebView2, which is part of Windows 11
  and most Windows 10 installations.
- Unsigned programs trigger the Windows "protected your PC" warning on
  other people's computers.
