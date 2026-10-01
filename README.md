# Finsight

Finsight is a Python and Streamlit personal finance analytics app that reads your bank statement CSV files, normalizes transactions into a common format, and produces basic spending and savings insights.

Upload statements from all your accounts at once: Finsight combines them and recognizes money moving between your own accounts, so it isn't counted as income or spending.

## Features

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
- Settings for your own IBANs, account holder names and transfer keywords, saved locally in `settings.json`
- Rule-based transaction categorization with word-aware keyword matching
- User editable categories and keyword rules, saved locally in `rules.json`
- Rule priority: categories are checked top to bottom, first match wins
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
│   └── settings.py
├── pipeline.py         # files -> parsed, categorized, classified transactions
├── statements.py       # parse one file, combine several, de-duplicate
├── categorizer.py      # keyword rules -> categories
├── flows.py            # income / expense / transfer / refund
├── corrections.py      # the user's manual corrections
├── analytics.py        # income, expenses, savings, spending by category
├── insights.py         # spending changes, recurring payments, unusual spending
├── charts.py           # Plotly charts
├── parsers/            # one parser per bank + generic fallback
├── sample_data/        # synthetic statements for testing
├── styles/style.css
└── tests/              # pytest suite
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
- [ ] User-defined budget goals and recommendations
- [ ] AI integration and financial insights

## Tech Stack

- Python
- pandas
- Streamlit

## If you made it this far

Thanks for checking Finsight out! You can find me on LinkedIn at https://www.linkedin.com/in/ishaanfartyal/
