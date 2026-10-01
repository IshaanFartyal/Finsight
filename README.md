# Finsight

[![Tests](https://github.com/IshaanFartyal/finsight/actions/workflows/tests.yml/badge.svg)](https://github.com/IshaanFartyal/finsight/actions/workflows/tests.yml)

Finsight is a Python and Streamlit personal finance analytics app that reads your bank statement CSV files, normalizes transactions into a common format, and produces basic spending and savings insights.

Upload statements from all your accounts at once: Finsight combines them and recognizes money moving between your own accounts, so it isn't counted as income or spending.

## Features

- **Try with demo data**: one click loads made-up statements from an ING and a Revolut account, so you can explore every feature without a bank file. The demo dates move along with the calendar, so it always ends in a recent month

- Automatic bank/export format detection
- Currently dedicated CSV parsers for Revolut and Wise, with plans to expand
- Generic fallback parser for unsupported CSV formats
- Automatic comma/semicolon delimiter detection
- Transaction normalization into a common schema
- Upload several statements at once (e.g. ING + Revolut); overlapping exports are de-duplicated
- Every transaction classified as income, expense, transfer or refund:
    - transfers between your own accounts are left out of income and expenses
    - refunds are deducted from the category they belong to
    - bank fees (Revolut) are counted as expenses
- Manual corrections: change a transaction's category or type on the Transactions page, for that one transaction or for every transaction from the same merchant. Corrections are remembered (locally, in `corrections.json`) and survive re-uploading the same statements
- Budgets per category with progress bars, and savings goals turned into "€X/month needed" compared with what you actually save
- Month-end forecast for an unfinished month: spending so far, recurring payments still due, and everyday spending at your current pace
- Currency conversion to euros using exchange rates you set (no internet connection needed)
- Export your categorized, corrected transactions as CSV or Excel (with monthly summary sheets)
- Settings for your own IBANs, account holder names and transfer keywords, saved locally in `settings.json`
- Rule-based transaction categorization with 87 keywords in 16 categories for common Dutch and international merchants (supermarkets, NS and public transport, energy and telecom, health insurers, airlines, brokers...) and word-aware matching
- Merchant names are cleaned before matching: payment-processor prefixes (`SumUp *`, `CCV*`, `Zettle_*`, `PayPal *`...), Wise card texts, card and terminal codes, dates and legal suffixes (`B.V.`) are removed, so `SumUp *Bakkerij Jansen B.V.` and `BAKKERIJ JANSEN` are recognized as the same merchant
- **To Review** (Categories page): every merchant without a category is listed once, with how often you paid there; one choice categorizes all its transactions, including future uploads
- User editable categories and keyword rules, saved locally in `rules.json`
- The most specific keyword wins ("Uber Eats" is Restaurants, "Uber" is Transport); keywords of up to 4 letters only match whole words
- Money moved to your own investment accounts (DEGIRO, Trade Republic, BUX) is treated as a transfer, so it doesn't lower your savings rate
- Financial summary metrics: income, expenses, savings, and savings rate
- Spending by category
- Monthly spending trends
- Insights page:
    - spending per category compared with your recent 3-month average
    - recurring payment detection (subscriptions, rent, insurance) with monthly cost and next expected date
    - subscription price changes (e.g. Netflix €13.99 → €15.99) and new recurring payments
    - unusual spending: purchases far above what you normally spend at that merchant or in that category
    - possible double charges: the same merchant charging the same amount twice within two days
    - key insights, with the most notable one shown on the Overview
- Streamlit dashboard with CSV upload and transaction table
- Clear warning when a bank format is not recognized
- Warning when a statement mixes currencies
- Automated tests for parsers, date handling, categorization and analytics

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
├── analytics.py        # income, expenses, savings, spending by category
├── insights.py         # spending changes, recurring payments, unusual spending
├── charts.py           # Plotly charts
├── parsers/            # one parser per bank + generic fallback
├── sample_data/        # synthetic statements for testing
├── styles/style.css
├── tests/              # pytest suite
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

## Run the App

```bash
streamlit run app.py
```

Then open the local Streamlit page in your browser and upload a supported CSV statement.

## Online Demo

Finsight can run as a public online demo, for example on [Streamlit Community Cloud](https://share.streamlit.io). Set `FINSIGHT_HOSTED = "true"` in the app's secrets to switch on **hosted mode**:

- the demo statements load automatically, with example budgets, a savings goal and an exchange rate;
- uploading statements is disabled, so nobody sends real bank data to a shared server;
- nothing is written to disk: each visitor's changes stay in their own browser session.

To analyse your own statements, run Finsight locally as described above.

## Run the Tests

Install the development dependencies once:

```bash
python -m pip install -r requirements-dev.txt
```

Then run:

```bash
python -m pytest
```

The tests parse every file in `sample_data/` and check that no
transactions are dropped, dates are read correctly, and categories
and totals come out as expected.

## How It Works

```text
CSV files ──> parsers ──> combine & de-duplicate ──> categorize ──> income / expense /
                                                                   transfer / refund
                                                                         │
            Overview, Trends, Insights  <── analytics & insights <── your corrections
```

Everything up to the corrections step runs once per upload (or when rules, settings or corrections change) and is cached, so moving around the app stays fast even with years of transactions.

## How Transfers Are Recognized

Each transaction is classified in this order (see `flows.py`):

1. **Bank signals**: Revolut top-ups and currency exchanges, Wise conversions, Revolut refunds.
2. **Your own accounts**: payments to or from an IBAN listed in Settings.
3. **Your own names**: payments to or from a name listed in Settings.
4. **Transfer keywords**: e.g. `SPAARREKENING`, editable in Settings.
5. **Matching pairs**: money leaving one uploaded account and the same amount arriving in another within 3 days.
6. **Refunds**: money back from a merchant you have also paid.

Try it with `sample_data/multi_account_ing.csv` and `sample_data/multi_account_revolut.csv` uploaded together.

## How the Forecast Works

For a month that isn't over yet, Finsight estimates the total as:

**spent so far + recurring payments still due + everyday spending at your pace so far**

Recurring payments (rent, subscriptions) are counted once on their expected date instead of being projected per day, so rent paid on the 2nd doesn't make the forecast explode. Budgets use the same projection to warn you before a category goes over.

## How Insights Are Calculated

All insights are calculated in Python (`insights.py`), not generated:

- **Spending changes** compare a month with the average of the previous 3 months. Changes under €25 or under 25% are not highlighted.
- **Recurring payments** need at least 3 payments to the same merchant at a regular weekly, monthly, quarterly or yearly interval, either at a fixed price (price changes are recognized and reported) or, for variable bills, within 15% of the typical amount.
- **New recurring payments** are those first paid in the last 3 months. A payment needs 3 occurrences to be recognized, so a new subscription appears after its third payment.
- **Possible double charges** are the same merchant and the exact same amount (at least €15) twice within 2 days.
- **Unusual spending** compares a purchase with what you usually spend at that merchant, or, for a new merchant, with your category (or all spending) history. Recurring payments are left out of what counts as normal.

Try the Insights page with `sample_data/insights_demo.csv`: July shows a Netflix price increase, August a new Disney Plus subscription and a possible double charge from Zalando.

## Supported Formats

Finsight currently includes dedicated parsers for Revolut and Wise CSV exports. Dedicated parser for ING is created through an online template, but not verified.

If the bank is not recognized, Finsight attempts to interpret the file using a generic CSV parser. Generic-parser results are explicitly marked as coming from an undetected bank and may be less reliable.

If the generic parser cannot identify enough information to interpret the file, the app reports that the statement could not be interpreted.

## Sample Data

The `sample_data` folder contains synthetic CSV files for testing. These files contain no real financial information.

## Privacy

Finsight runs entirely on your own computer. Uploaded statements are analysed in memory by the local Streamlit process; nothing is sent anywhere, and Streamlit's anonymous usage statistics are switched off in `.streamlit/config.toml`. Your rules, settings, corrections and budgets are saved as local JSON files that are excluded from Git.

**Private session:** switch on "🔒 Private session" in the sidebar and nothing is written to disk: rules, settings, corrections and budgets only last until you close the app. "Clear everything from memory" removes your uploaded statements, the analysis cache and all changes immediately.

To start every session as a private session, add this to your personal secrets file, `~/.streamlit/secrets.toml` (or set the environment variable `FINSIGHT_PRIVATE=true`):

```toml
FINSIGHT_PRIVATE = "true"
```

**Only your own computer can connect:** by default, Streamlit also accepts connections from other devices on the same network. To prevent that, add this to your personal Streamlit config (`~/.streamlit/config.toml`, not the project's):

```toml
[server]
address = "localhost"
```

Bank statements can contain highly sensitive personal and financial information.

Finsight is currently intended as a local development/portfolio project. DO NOT commit real bank statements, account numbers, transaction histories, or other sensitive financial data to GitHub.

The included `.gitignore` excludes common local bank-statement filenames and data folders, but you should still verify staged files before every commit.

## Limitations

- Transaction categorization is currently rule-based.
- Transfer and refund detection is rule-based. A friend paying you back for something counts as a refund if you also paid them.
- Wise "Total Fees" are assumed to be included in the amount (not verified against a real export).
- Multi-currency statements are summed without currency conversion (the app shows a warning).
- Generic CSV parsing is best-effort and may interpret unusual formats incorrectly.
- Bank export formats may change over time and can require parser updates.
- Finsight does not provide financial, investment, tax, or legal advice.

## Roadmap

- [ ] Additional bank integrations
    - [ ] Verify ING
    - [ ] ABN AMRO
    - [ ] Rabobank
    - [ ] Bunq
- [x] Monthly dashboard filter
- [x] Multi-account upload with transfer and refund detection
- [x] Recurring subscription detection
- [x] Unusual spending detection
- [x] Budgets and savings goals
- [x] Month-end forecast
- [x] Currency conversion
- [x] CSV and Excel export
- [ ] AI integration and financial insights

## Tech Stack

- Python
- pandas
- Streamlit
- Plotly
- pytest, GitHub Actions

## If you made it this far

Thanks for checking Finsight out! You can find me on LinkedIn at https://www.linkedin.com/in/ishaanfartyal/
