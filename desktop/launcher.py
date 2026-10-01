"""
Finsight as a desktop app (beta).

Starts the normal Finsight (Streamlit) app in the background and shows
it in its own window instead of a browser tab. Nothing in Finsight
itself is changed: this file only starts it and displays it.

Try it without building anything:

    python desktop/launcher.py

Build a Windows program and a zip to share (see desktop/README.md):

    python desktop/build.py

The user's rules, settings, corrections and budgets are kept in their
own data folder (on Windows: %LOCALAPPDATA%\\Finsight), not next to
the program.

How it works: this program runs twice. The first copy opens the window.
It starts a second copy of itself with "--run-server", which runs
Streamlit; Streamlit and the window each need to be the main program of
their own process. When the window closes, the server is stopped.
"""

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

APP_NAME = "Finsight"

SERVER_FLAG = "--run-server"

# Error messages of the built program, in the user's data folder.
LOG_FILE = "finsight.log"

# How long to wait for Finsight to start before showing an error.
STARTUP_TIMEOUT_SECONDS = 90

LOADING_PAGE = """
<html>
  <body style="margin:0; height:100vh; display:flex; align-items:center;
               justify-content:center; background:#07111f; color:#f4f7fb;
               font-family:'Segoe UI', sans-serif;">
    <div style="text-align:center;">
      <div style="font-size:28px; font-weight:600;">Finsight</div>
      <div style="margin-top:10px; color:#9fb3c8;">Starting…</div>
    </div>
  </body>
</html>
"""

ERROR_PAGE = """
<html>
  <body style="margin:0; padding:40px; background:#07111f; color:#f4f7fb;
               font-family:'Segoe UI', sans-serif;">
    <h2>Finsight could not start</h2>
    <p style="color:#9fb3c8;">{reason}</p>
    <p style="color:#9fb3c8;">Details may be in: {log}</p>
  </body>
</html>
"""


def is_built():
    """True when running as a built program instead of from the code."""

    return getattr(sys, "frozen", False)


def app_folder():
    """
    The folder that holds app.py, styles/ and sample_data/: inside the
    built program, or the project folder when running from the code.
    """

    if is_built():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))

    return Path(__file__).resolve().parent.parent


def version():
    """Finsight's version number, or "" if it can't be read."""

    folder = str(app_folder())

    if folder not in sys.path:
        sys.path.insert(0, folder)

    try:
        from version import __version__

    except ImportError:
        return ""

    return __version__


def window_title():
    number = version()

    return f"{APP_NAME} {number} (beta)" if number else APP_NAME


def user_data_folder(environ=None, platform=None):
    """
    Where this user's Finsight files are kept:

    Windows  %LOCALAPPDATA%\\Finsight
    macOS    ~/Library/Application Support/Finsight
    Linux    ~/.local/share/Finsight  (or $XDG_DATA_HOME/Finsight)
    """

    environ = os.environ if environ is None else environ
    platform = sys.platform if platform is None else platform

    home = Path.home()

    if platform.startswith("win"):
        # Local, not Roaming (%APPDATA%): on managed work or university
        # networks, Roaming folders can be copied to a server. Finsight's
        # files should stay on this computer.
        base = Path(environ.get("LOCALAPPDATA") or home / "AppData" / "Local")

    elif platform == "darwin":
        base = home / "Library" / "Application Support"

    else:
        base = Path(environ.get("XDG_DATA_HOME") or home / ".local" / "share")

    return base / APP_NAME


def free_port():
    """A port on this computer that nothing else is using."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


# ============================================================
# THE SERVER COPY: runs Streamlit
# ============================================================

def run_server(port):
    folder = app_folder()

    # app.py opens "styles/style.css" relative to the current folder.
    os.chdir(folder)
    sys.path.insert(0, str(folder))

    # Finsight saves the user's rules, settings, corrections and budgets
    # here (see storage.py) instead of inside the program's own folder.
    data_folder = user_data_folder()
    data_folder.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("FINSIGHT_DATA_DIR", str(data_folder))

    # A built program has no console to print to. Error messages go to
    # a log file instead, so a problem can be looked up afterwards. The
    # file starts empty on every launch.
    if sys.stdout is None or sys.stderr is None:
        log = open(data_folder / LOG_FILE, "w", encoding="utf-8", buffering=1)
        sys.stdout = sys.stdout or log
        sys.stderr = sys.stderr or log

    from streamlit.web import cli as streamlit_cli

    sys.argv = [
        "streamlit",
        "run",
        str(folder / "app.py"),
        # A built program looks like a development copy of Streamlit to
        # Streamlit itself; without this it refuses the settings below.
        "--global.developmentMode=false",
        "--server.headless=true",
        f"--server.port={port}",
        # Only this computer can connect.
        "--server.address=127.0.0.1",
        "--server.fileWatcherType=none",
        "--browser.gatherUsageStats=false",
        # Hide Streamlit's own "Deploy" button and developer menu.
        "--client.toolbarMode=minimal",
    ]

    sys.exit(streamlit_cli.main())


# ============================================================
# THE WINDOW COPY: starts the server and shows it
# ============================================================

def start_server(port):
    if is_built():
        command = [sys.executable, SERVER_FLAG, str(port)]
    else:
        command = [sys.executable, str(Path(__file__).resolve()), SERVER_FLAG, str(port)]

    # Don't flash a black console window on Windows.
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

    return subprocess.Popen(command, creationflags=flags)


def wait_until_ready(url, server, timeout=STARTUP_TIMEOUT_SECONDS):
    """
    Wait until Finsight answers. Raises RuntimeError if the server stops
    or takes too long.
    """

    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if server.poll() is not None:
            raise RuntimeError(
                f"The background process stopped (exit code {server.returncode})."
            )

        try:
            with urllib.request.urlopen(f"{url}/_stcore/health", timeout=2) as reply:
                if reply.status == 200:
                    return

        except (urllib.error.URLError, OSError):
            pass

        time.sleep(0.3)

    raise RuntimeError(f"Finsight did not start within {timeout} seconds.")


def stop_server(server):
    if server.poll() is not None:
        return

    server.terminate()

    try:
        server.wait(timeout=5)

    except subprocess.TimeoutExpired:
        server.kill()


def show_in_browser(url, server):
    """Fallback when the window library (pywebview) isn't installed."""

    import webbrowser

    wait_until_ready(url, server)
    webbrowser.open(url)

    print(f"{APP_NAME} is running at {url}. Press Ctrl+C to stop.")

    try:
        server.wait()

    except KeyboardInterrupt:
        pass


def show_in_window(webview, url, server):
    # Needed for the CSV and Excel export buttons.
    webview.settings["ALLOW_DOWNLOADS"] = True

    window = webview.create_window(
        window_title(),
        html=LOADING_PAGE,
        width=1400,
        height=900,
        min_size=(900, 600),
    )

    started = time.monotonic()

    def load_app():
        try:
            wait_until_ready(url, server)

        except RuntimeError as error:
            window.load_html(
                ERROR_PAGE.format(
                    reason=error,
                    log=user_data_folder() / LOG_FILE,
                )
            )
            return

        print(f"{APP_NAME} ready after {time.monotonic() - started:.1f} seconds.")
        window.load_url(url)

    # Blocks until the window is closed.
    webview.start(load_app)


def main():
    port = free_port()
    url = f"http://127.0.0.1:{port}"

    server = start_server(port)

    try:
        try:
            import webview

        except ImportError:
            show_in_browser(url, server)

        else:
            show_in_window(webview, url, server)

    finally:
        stop_server(server)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == SERVER_FLAG:
        run_server(int(sys.argv[2]))

    else:
        main()
