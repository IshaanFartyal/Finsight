"""
Online demo ("hosted mode").

Finsight is meant to run on your own computer, where it saves rules,
settings, corrections and budgets to local JSON files. When it runs as a
public online demo (e.g. on Streamlit Community Cloud), every visitor
shares the same server, so in hosted mode:

- nothing is ever written to disk: changes live only in the visitor's
  own browser session;
- statements can't be uploaded; the demo data loads automatically;
- a banner explains that this is a demo and links to the code.

Hosted mode is switched on by setting FINSIGHT_HOSTED = "true", either as
an environment variable or in the app's secrets on Streamlit Cloud.
"""

import os

HOSTED_SETTING = "FINSIGHT_HOSTED"

REPO_URL = "https://github.com/IshaanFartyal/finsight"

_TRUE = {"1", "true", "yes", "on"}


def _is_true(value):
    return str(value).strip().lower() in _TRUE


def is_hosted(environ=None, secrets=None):
    """
    True when FINSIGHT_HOSTED is switched on in the environment or in
    the given secrets (anything with a .get(), like st.secrets).
    """

    environ = os.environ if environ is None else environ

    if _is_true(environ.get(HOSTED_SETTING, "")):
        return True

    if secrets is not None:
        try:
            return _is_true(secrets.get(HOSTED_SETTING, ""))

        # Locally there is usually no secrets file, and reading
        # st.secrets then raises an error: that means "not hosted".
        except Exception:
            return False

    return False


def save_if_local(save, data, hosted):
    """
    Call save(data) when running locally. In hosted mode, do nothing:
    the data stays in the visitor's session only.

    Returns True if the data was saved.
    """

    if hosted:
        return False

    save(data)
    return True


def storage_note(hosted):
    """Where the user's changes are kept, for captions in the app."""

    if hosted:
        return (
            "This is the online demo: your changes are kept for this "
            "browser session only."
        )

    return "Saved on this computer only."


# Shown once per visit in the online demo, and in short in the sidebar.
DISCLAIMER_TITLE = "Welcome to the Finsight demo"

DISCLAIMER = (
    "This is a **public online demo** with **made-up data** from an ING "
    "and a Revolut account. Explore every page: your changes are kept "
    "for this browser session only.\n\n"
    "**Please don't enter any real personal or financial information "
    "here**: no bank statements, account numbers (IBANs), names or real "
    "amounts. Uploading statements is switched off in this demo.\n\n"
    "Finsight is built to run **on your own computer**, where your bank "
    "data never leaves your device. To use it with your own statements, "
    f"[get the code on GitHub]({REPO_URL})."
)

SIDEBAR_NOTICE = (
    "🌐 **Online demo** with made-up data.\n\n"
    "⚠️ **Don't enter real personal or bank information here.** "
    "Changes are kept for this session only.\n\n"
    "To analyse your own statements privately, run Finsight on your "
    f"own computer: [code on GitHub]({REPO_URL})."
)
