# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Beancount-Reporter generates financial reports from [beancount](https://github.com/beancount/beancount) ledger files. It queries beancount data using `beanquery`, processes it with `polars` DataFrames, and renders it with `great_tables`. The README states the goal is PDF reports, but the current implementation renders HTML and opens it in a browser (`great_tables`' `GT(...).show()`) — no file is written yet.

This is early-stage, single-developer code. Expect German-language identifiers (DataFrame columns like `Konto`, `Jahr`, `Monat`, `Betrag`, `JahrMonat`, `Summe`; report titles), German comments, and `FIXME` markers throughout.

## Setup & Running

Install in development mode:
```bash
pip install -e .
```

Run the reporter (config file is required):
```bash
python src/BeancountReporter.py -f localconfig/beancount_reporter.config.toml
```

Debug mode:
```bash
python src/BeancountReporter.py -f localconfig/beancount_reporter.config.toml -d
```

There are no tests or linting configuration defined yet. Debug tracing uses `icecream`'s `ic()` (enabled via `ic.enable()` in the entry point), not the `logging` logger — the logger exists in `Config` but is barely used.

`testcode/` holds throwaway experiment scripts (e.g. probing beanquery output). `localconfig/` holds the developer's real config plus a small `test.beancount` sample — treat it as local, not canonical.

## Architecture

```
src/BeancountReporter.py          # Entry point: builds Config, calls report functions
src/beancount_reporter/
    __init__.py                   # Re-exports public API
    config.py                     # Config class (TOML file + CLI args + env vars)
    beancount_reporter.py         # Data retrieval: queries beancount, returns polars DataFrames
    output.py                     # Rendering: takes DataFrames, outputs via great_tables
```

**Data flow:** `Config` → `get_financial_overview_dataframe(config)` → `output_financial_overview(df)`

### Config system (`config.py`)

Config is resolved in priority order (lowest to highest): defaults → env vars → TOML file → CLI args.

TOML tables map to nested attributes: `[common]` section → `config.common.beancount_file`. The `DictConfig` dataclass wraps each TOML table. Required parameters are listed in `self.required` and validated at startup.

### Report types (`beancount_reporter.py`)

- **`get_financial_overview_dataframe`**: A net-worth-over-time report. For each time column it runs one balance query and assembles a wide DataFrame whose rows are: asset lines → `Summe Vermögen` (total assets) → liability lines → `Summe Verbindlichkeiten` (total liabilities) → `Nettovermögen` (net worth = plain column sum, since beancount liabilities are negative). Accounts listed in the `[groups]` config table collapse into one line per group; every other account is its own line.
- **`get_financial_performance_df`**: Calculates XIRR performance per investment instrument using `pyxirr`. Currently partially implemented (hardcoded accounts/dates).

Both report functions read the ledger via `beancount.loader.load_file` and derive the account filter from beancount options: `opts["name_assets"]` and `opts["name_liabilities"]` build the `WHERE account ~ ...` clause. Balances come from `value(SUM(position), <price_date>)` (converted to the operating currency), and `numberify.numberify_results` turns that into numeric columns. The **date argument to `value()` is required for correct history**: without it, beanquery values every column at the *latest* price, so past columns would show old quantities at today's prices. `<price_date>` is `query_date - 1` (the actual balance date, since `CLOSE ON` is exclusive), giving each column the most-recent price on or before its period end.

`output_financial_overview` (`output.py`) renders the DataFrame with `great_tables`, moving `Konto` into the row stub and bold-styling the three summary rows (`SUMMARY_ROWS`).

`get_financial_performance_df` maps each investment account to its income counterpart by string-replacing `Vermögen` → `Einnahmen:Kapitalertrag` in the account name — so it assumes the German account hierarchy of the developer's own ledger. Its account list and date ranges are hardcoded in the `_get_list_of_accounts_for_performanceoverview` / `_get_list_of_start_end_dates` helpers.

### Date logic

`get_list_of_dates_for_query(config, entries)` returns the overview's time columns as `(query_date, label)` pairs, oldest to newest (today rightmost): year-end for each older year in the ledger (`"YYYY"`), end-of-month for the last 12 completed months (`"YYYY-MM"`), and today (`"YYYY-MM-DD"`).

Key subtlety: beanquery's `CLOSE ON D` is **exclusive** — it returns the balance of postings dated *before* `D`. So a period's closing balance is queried on the first day of the *following* period (end of Jan → `CLOSE ON <year>-02-01`; today's live state → `CLOSE ON today+1`). This was verified empirically against `localconfig/test.beancount`. The lower bound of the year columns comes from `config.common.start`, else the earliest ledger entry, else 2014; `config.common.end` overrides "today".

## Config File Format

```toml
[common]
beancount_file = "/path/to/your.beancount"
start = "2020-01-01"   # optional; limits earliest year column (defaults to earliest ledger entry / 2014)
end = "2026-05-01"     # optional; overrides "today" (defaults to today)

# Optional: collapse accounts into one overview line each.
# Key = displayed label, value = list of accounts. A listed name matches itself
# and all sub-accounts (prefix + ":"). Unlisted accounts appear individually.
[groups]
"Krypto" = ["Vermögen:Aktien:Krypto"]
"Aktien" = ["Vermögen:Aktien:DKB", "Vermögen:Aktien:TR"]
```

Config tables are read into `DictConfig` wrappers; grouping reads `config.groups._raw`. The config file path is passed via `-f` CLI argument. A local example is at `localconfig/beancount_reporter.config.toml`.
