<p align="center">
  <img src="desktop/finsight.png" alt="Finsight logo" width="120">
</p>

# Finsight

[![Tests](https://github.com/IshaanFartyal/finsight/actions/workflows/tests.yml/badge.svg)](https://github.com/IshaanFartyal/finsight/actions/workflows/tests.yml)

Finsight is a personal finance analytics app that turns your bank statements into clear spending insights, budgets, and forecasts, with a focus on data privacy.

Upload statements from all your accounts at once: Finsight combines them and recognizes money moving between your own accounts, so it isn't counted as income or spending.

## Online Demo

**[Try Finsight in your browser →](https://finsight-live.streamlit.app/)**

The demo runs on made-up statements from an ING and a Revolut account. Uploads are switched off and nothing is stored, so please don't enter real data there. To analyze your own statements, run Finsight on your own computer (see below).

## Features

- **Multi-bank import**: Revolut, Wise, ING, Rabobank and bunq parsers (payment and savings accounts) plus a generic fallback, with automatic separator, encoding and date-format detection. Overlapping exports are de-duplicated.
- **Income, expense, transfer or refund**: transfers between your own accounts (including investments such as DEGIRO) are left out of income and spending; refunds reduce the category they belong to; bank fees count as expenses.
- **Categorization**: 93 keywords in 16 categories, matched on cleaned merchant names (`SumUp *Bakkerij Jansen B.V.` → `Bakkerij Jansen`).
- **To Review**: every unrecognized merchant is listed once; one choice categorizes all its transactions, now and in future uploads.
- **Your accounts**: the accounts of the statements you upload count as yours, so upload only your own statements in one session. For any other account that looks like yours (money regularly goes both ways), Finsight asks first.
- **Corrections**: fix a category or type per transaction or per merchant; Finsight remembers it.
- **Insights**: spending vs. your 3-month average, recurring payments and price changes, new subscriptions, unusual spending and possible double charges.
- **Budgets & goals**: monthly budgets per category, savings goals, and a month-end spending forecast.
- **Currency conversion** with your own exchange rates, and **CSV/Excel export**.
- **Private by design**: runs locally, optional private sessions that never write to disk, no usage statistics.
- **Demo data** button to explore everything without a bank file.

## Project Structure

```text
finsight/
├── app.py              # Streamlit entry point: sidebar, upload, page routing
├── ui.py               # shared page helpers and cached insights
├── views/              # one module per page
│   ├── overview.py
│   ├── transactions.py
│   ├── categories.py
│   ├── trends.py
│   ├── insights_page.py
│   ├── budgets_page.py
│   └── settings.py
├── pipeline.py         # files -> parsed, categorized, classified transactions
├── statements.py       # parse one file, combine several, de-duplicate
├── categorizer.py      # keyword rules -> categories
├── flows.py            # income / expense / transfer / refund
├── corrections.py      # the user's manual corrections
├── merchants.py        # clean merchant names from messy descriptions
├── review.py           # merchants that still need a category
├── currency.py         # convert foreign currencies to euros
├── budgets.py          # budgets and savings goals
├── export.py           # CSV and Excel export
├── demo.py             # demo statements, dated to end in a recent month
├── hosting.py          # hosted mode for the online demo
├── storage.py          # where your rules, settings and budgets are saved
├── desktop/            # desktop app: launcher and build files
├── analytics.py        # income, expenses, savings, spending by category
├── insights.py         # spending changes, recurring payments, unusual spending
├── charts.py           # Plotly charts
├── parsers/            # one parser per bank + generic fallback
├── sample_data/        # synthetic statements for testing
├── styles/style.css
├── tests/              # pytest suite
├── .devcontainer/      # setup for GitHub Codespaces
└── .github/workflows/  # runs the tests on every push
```

## Installation

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows:

```powershell
.venv\Scripts\activate
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

To explore or edit the code without installing anything, open it in [GitHub Codespaces](https://codespaces.new/IshaanFartyal/finsight): it sets everything up and starts the app in your browser. For your own bank data, run Finsight on your own computer.

## Run the App

```bash
streamlit run app.py
```

Then open the local Streamlit page in your browser and upload a supported CSV statement.

## Desktop App (Beta)

Finsight can also run in its own window and be built into a Windows program that needs no Python. See [desktop/README.md](desktop/README.md).

## Run the Tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```

The tests also run on every push via GitHub Actions.

## How It Works

```text
CSV files ──> parsers ──> combine & de-duplicate ──> categorize ──> income / expense /
                                                                   transfer / refund
                                                                         │
            Overview, Trends, Insights  <── analytics & insights <── your corrections
```

Everything up to the corrections step runs once per upload and is cached, so the app stays fast with years of transactions.

- **Transfers** are recognized from bank signals (top-ups, exchanges), your own accounts (those of the uploaded statements, plus IBANs and names you list in Settings), transfer keywords, investment categories, and matching amounts leaving one account and arriving in another within 3 days (`flows.py`).
- **Categories**: the most specific keyword wins ("Uber Eats" is Restaurants, "Uber" is Transport); keywords of up to 4 letters only match whole words (`categorizer.py`).
- **Forecast**: spent so far + recurring payments still due + everyday spending at your current pace.
- **Insights** are calculated, not generated (`insights.py`):
    - spending changes under €25 or 25% are not highlighted;
    - recurring payments need 3 payments at a regular interval;
    - double charges are the same merchant and amount (at least €15) within 2 days;
    - unusual spending is compared with what you normally spend at that merchant.

## Supported Formats

Current supported CSV formats are:

- Revolut
- Wise
- ING: payment and savings accounts, semicolon- or comma-separated, Dutch or English column names (built from ING's documented format, not yet verified with a real export)
- Rabobank: payment and savings accounts, several accounts in one file (built from Rabobank's documented format, not yet verified with a real export)
- bunq: several sub-accounts in one file, English or Dutch column names (built from the format bunq users have documented, not yet verified with a real export)

with plans to add further banks.

If the bank is not recognized, Finsight attempts to interpret the file using a generic CSV parser. Generic-parser results are explicitly marked as coming from an undetected bank and may be less reliable.

If the generic parser cannot identify enough information to interpret the file, the app reports that the statement could not be interpreted.

## Sample Data

`sample_data/` contains synthetic statements only. Try `multi_account_ing.csv` with `multi_account_revolut.csv` and `ing_savings_sample.csv` for transfers, `rabobank_sample.csv` or `bunq_sample.csv` for a payment and a savings account in one file, `own_account_question_sample.csv` to see Finsight ask whether an account is yours, or `insights_demo.csv` for price changes, new subscriptions and double charges.

## Privacy

Finsight runs entirely on your own computer: statements are analyzed in memory, nothing is sent anywhere, and Streamlit's usage statistics are switched off. Your rules, settings, corrections and budgets are saved as local JSON files, excluded from Git.

- **Private session**: switch on "🔒 Private session" in the sidebar and nothing is written to disk. "Clear everything from memory" removes your statements and changes immediately. To make it the default, add `FINSIGHT_PRIVATE = "true"` to `~/.streamlit/secrets.toml`.
- **Local connections only**: Streamlit also accepts connections from other devices on your network by default. To prevent that, add this to `~/.streamlit/config.toml` (your personal config, not the project's):

  ```toml
  [server]
  address = "localhost"
  ```

Never commit real bank statements or account details. `.gitignore` excludes common statement filenames and Finsight's JSON files, but check your staged files before each commit.

## Limitations

- Categorization, transfer and refund detection are rule-based. A friend paying you back counts as a refund if you also paid them.
- Foreign currencies need an exchange rate in Settings; until then they're counted as euros (the app shows a warning).
- Wise "Total Fees" are assumed to be included in the amount (not verified against a real export).
- Generic CSV parsing is best-effort, and bank export formats can change over time.
- Finsight does not provide financial, investment, tax, or legal advice.

## Roadmap

- [ ] Additional bank integrations
    - [ ] Verify ING
    - [ ] ABN AMRO
    - [ ] Verify Rabobank
    - [ ] Verify bunq
- [x] Monthly dashboard filter
- [x] Multi-account upload with transfer and refund detection
- [x] Recurring subscription detection
- [x] Unusual spending detection
- [x] Budgets and savings goals
- [x] Month-end forecast
- [x] Currency conversion
- [x] CSV and Excel export
- [x] Online demo
- [ ] AI integration and financial insights

## Tech Stack

- Python
- pandas
- Streamlit
- Plotly
- pytest, GitHub Actions

## If you made it this far

Thanks for checking Finsight out! You can find me on LinkedIn at https://www.linkedin.com/in/ishaanfartyal/
