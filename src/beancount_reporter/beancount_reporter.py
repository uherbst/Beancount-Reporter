"""Different report types for Beancount data"""

from icecream import ic
import datetime
import os

# import sys
# import decimal

import beancount as bc
from beanquery import query
from beanquery import numberify

import polars as pl
from pyxirr import xirr


def get_list_of_dates_for_query(config, entries):
    """Return the time columns of the overview as (query_date, label) pairs.

    Balances are queried with beanquery's ``CLOSE ON``, which is *exclusive*:
    ``CLOSE ON D`` returns the balance of all postings dated before ``D``. So a
    period's closing balance is queried on the first day of the *following*
    period.

    Columns, oldest to newest (today rightmost):
      - year-end for every older year in the ledger    -> label "YYYY"
      - end-of-month for the last 12 completed months  -> label "YYYY-MM"
      - today (state right now)                        -> label = today's date
    """
    end_date = datetime.date.today()
    if hasattr(config.common, "end"):
        end_date = datetime.date.fromisoformat(config.common.end)

    # Last 12 completed months (ascending). Each is queried on the 1st of the
    # month that follows it, so it reflects the balance at the month's end.
    month_cols = []
    oldest_month_year = end_date.year
    for k in range(12, 0, -1):
        year, month = end_date.year, end_date.month - k
        while month <= 0:
            month += 12
            year -= 1
        if k == 12:
            oldest_month_year = year
        next_year, next_month = (year, month + 1) if month < 12 else (year + 1, 1)
        month_cols.append((datetime.date(next_year, next_month, 1), f"{year}-{month:02d}"))

    # Older years: every year before the oldest monthly column. A year's closing
    # balance is queried on Jan 1st of the following year.
    start_year = 2014
    if hasattr(config.common, "start"):
        start_year = datetime.date.fromisoformat(config.common.start).year
    elif entries:
        start_year = min(entry.date for entry in entries).year

    year_cols = [
        (datetime.date(year + 1, 1, 1), str(year))
        for year in range(start_year, oldest_month_year)
    ]

    # Today's state: CLOSE ON is exclusive, so query the day after end_date.
    today_col = (end_date + datetime.timedelta(days=1), end_date.isoformat())

    return year_cols + month_cols + [today_col]


def _get_account_groups(config):
    """Return ordered {group_name: [account_patterns]} from the [groups] table.

    A pattern matches an account if it equals the account or is a parent of it
    (prefix followed by ':'). Missing table -> no groups (every account is its
    own line).
    """
    groups_cfg = getattr(config, "groups", None)
    if groups_cfg is None:
        return {}
    raw = getattr(groups_cfg, "_raw", groups_cfg)
    if not isinstance(raw, dict):
        return {}
    return {
        name: (patterns if isinstance(patterns, list) else [patterns])
        for name, patterns in raw.items()
    }


def get_financial_overview_dataframe(config):
    """Return a wide DataFrame of net-worth over time.

    Rows are grouped into Vermögen (assets) with a subtotal, Verbindlichkeiten
    (liabilities) with a subtotal, and a final Nettovermögen (net worth) row.
    Accounts listed in a [groups] config table are collapsed into one line per
    group; every other account appears on its own line.
    """

    # read ledger file
    if not os.path.isfile(config.common.beancount_file):
        # FIXME: Better error output ? logger ? ic ?
        print(f"File not found: {config.common.beancount_file}")
        exit(-1)

    entries, _, opts = bc.loader.load_file(config.common.beancount_file)
    name_assets = opts["name_assets"]
    name_liabilities = opts["name_liabilities"]
    where_clause = f"account ~ '{name_assets}' or account ~ '{name_liabilities}'"

    columns = get_list_of_dates_for_query(config, entries)

    # balances[account][label] = amount at that point in time
    balances = {}
    labels = []
    for query_date, label in columns:
        labels.append(label)
        # CLOSE ON is exclusive, so the balance is as of the day before
        # query_date. Value the holdings at *that* day's price (most recent price
        # on or before it) instead of the latest price, so historical columns use
        # historical prices for foreign currencies / commodities.
        price_date = query_date - datetime.timedelta(days=1)
        beanquery = (
            f"SELECT account, value(SUM(position), {price_date.isoformat()}) as amount "
            f"FROM CLOSE ON {query_date.isoformat()} "
            f"WHERE {where_clause} "
            f"GROUP BY account ORDER BY account"
        )
        cols, rows = query.run_query(entries, opts, beanquery)
        cols, rows = numberify.numberify_results(cols, rows)
        for row in rows:
            account = row[0]
            # Single operating currency after value(); sum defensively over any
            # numeric columns numberify produced, ignoring empty ones.
            amount = sum(v for v in row[1:] if v is not None)
            balances.setdefault(account, {})[label] = float(amount)

    accounts = sorted(balances)

    def _values(account_list):
        """Column-wise sum over the given accounts, aligned to `labels`."""
        return [
            float(sum(balances[a].get(label, 0.0) for a in account_list))
            for label in labels
        ]

    groups = _get_account_groups(config)

    def _matches(account, patterns):
        return any(account == p or account.startswith(p + ":") for p in patterns)

    # account -> group name (first matching group in config order wins)
    grouped = {}
    for name, patterns in groups.items():
        for account in accounts:
            if account not in grouped and _matches(account, patterns):
                grouped[account] = name

    records = []  # (label, [values aligned to labels])

    def _section(prefix):
        section_accounts = [a for a in accounts if a.startswith(prefix)]
        # Grouped lines first (in config order), then ungrouped single accounts.
        for name in groups:
            members = [a for a in section_accounts if grouped.get(a) == name]
            if members:
                records.append((name, _values(members)))
        for account in section_accounts:
            if account not in grouped:
                records.append((account, _values([account])))
        return section_accounts

    asset_accounts = _section(name_assets)
    records.append(("Summe Vermögen", _values(asset_accounts)))
    liability_accounts = _section(name_liabilities)
    records.append(("Summe Verbindlichkeiten", _values(liability_accounts)))
    records.append(("Nettovermögen", _values(accounts)))

    df = pl.DataFrame(
        {
            "Konto": [label for label, _ in records],
            **{
                label: [values[i] for _, values in records]
                for i, label in enumerate(labels)
            },
        }
    )

    # Drop old year columns (label "YYYY") in which net worth is still zero,
    # i.e. years before the ledger holds anything.
    networth = _values(accounts)
    empty_years = [
        label
        for i, label in enumerate(labels)
        if len(label) == 4 and label.isdigit() and abs(networth[i]) < 0.005
    ]
    if empty_years:
        df = df.drop(empty_years)

    return df


def output_df(df):
    """Output datafram as table."""

    print(df)


def get_financial_performance_df(config):
    """return dataset with financial performance for specified account.

    Output format:
    list of dictionary
    Instrument|Overall time|yr1|yr2|yr3|last 12month
    """

    # read ledger file
    if not os.path.isfile(config.common.beancount_file):
        # FIXME: Better error output ? logger ? ic ?
        print(f"File not found: {config.common.beancount_file}")
        exit(-1)

    entries, _, opts = bc.loader.load_file(config.common.beancount_file)
    # currency = opts["operating_currency"][0]
    # name_assets = opts["name_assets"]
    # name_liabilities = opts["name_liabilities"]

    dates = _get_list_of_start_end_dates(config)
    # format of dates:
    # list of dictionaries
    # each row: start_day | end_day | desc

    accounts = _get_list_of_accounts_for_performanceoverview(config)
    # format of accounts:
    # list of dictionaries: {account_name, account_desc}
    # desc1|account1
    # desc2|account2
    # desc3|account3
    # desc4|accountgroup1 (= account-wildcard)
    # desc5|accountgroup2 (= account-wildcard)

    performance_overview = []
    for account in accounts:

        # Dividends or interest is booked as "Einnahmen:Kapitalertrag" instead of "Vermögen"
        income = account["account_name"].replace("Vermögen", "Einnahmen:Kapitalertrag")

        where_clause = f"account ~ '{account['account_name']}' or account ~ '{income}'"
        ic(where_clause)
        performance_account = {
            "instrument": account["account_desc"],
        }

        for date in dates:
            # Get balance for the beginning and end
            beanquery_start = f"select date, value(sum(position)) \
                FROM OPEN ON {date['start_day']} CLOSE ON {date['start_day']} \
                WHERE ( {where_clause} ) \
                and flag != 'P' \
                group by date"
            cols, rows_start = query.run_query(entries, opts, beanquery_start)
            cols, rows_start = numberify.numberify_results(cols, rows_start)
            beanquery_end = f"select date, value(sum(position)) \
                FROM OPEN ON {date['end_day']} CLOSE ON {date['end_day']} \
                WHERE (  {where_clause} ) \
                and flag != 'P' \
                group by date"
            cols, rows_end = query.run_query(entries, opts, beanquery_end)
            cols, rows_end = numberify.numberify_results(cols, rows_end)

            beanquery = f"select date, value(sum(position)) \
                WHERE (  {where_clause} ) \
                and date >= {date['start_day']} \
                and date <= {date['end_day']} \
                and flag != 'P' \
                group by date"

            cols, rows = query.run_query(entries, opts, beanquery)
            cols, rows = numberify.numberify_results(cols, rows)

            if len(rows_end) == 0 and len(rows_start) == 0:
                # This instrument was not active in that time interval
                performance_account[date["desc"]] = "-"
            else:
                # if rows_end is not empty, we have to negate the value
                rows_end[0][1] = -1 * rows_end[0][1]
                all_rows = rows_start + rows + rows_end
                ic(all_rows)
                performance_account[date["desc"]] = round(xirr(all_rows) * 100, 2)

        performance_overview.append(performance_account)

    ic(performance_overview)


def _get_list_of_start_end_dates(config):
    """FIXME"""

    result = [  # {'start_day': datetime.date.fromisoformat('2022-01-01'),
        #  'end_day': datetime.date.fromisoformat('2023-01-01'),
        #  'desc':'2022'},
        # {'start_day': datetime.date.fromisoformat('2023-01-01'),
        #  'end_day': datetime.date.fromisoformat('2024-01-01'),
        #  'desc':'2023'},
        # {'start_day': datetime.date.fromisoformat('2024-01-01'),
        #  'end_day': datetime.date.fromisoformat('2025-01-01'),
        #  'desc': '2024'},
        # {'start_day': datetime.date.fromisoformat('2024-03-01'),
        #  'end_day': datetime.date.fromisoformat('2025-03-01'),
        #  'desc': 'last 12m'}# ,
        {
            "start_day": datetime.date.fromisoformat("2023-01-01"),
            "end_day": datetime.date.today(),
            "desc": "Insgesamt",
        },
    ]

    return result


def _get_list_of_accounts_for_performanceoverview(config):
    """FIXME"""

    result = [  # {'account_desc':'SP500 x2','account_name':'Vermögen:Aktien:TR:DBPG'},
        {
            "account_desc": "DKB-MSCIW",
            "account_name": "Vermögen:Aktien:DKB:ISHSIII-MSCIW",
        },
        # {'account_desc':'DKB-MSCIW Div.','account_name':'Vermögen:Aktien:DKB:HSBC-MSCIW'},
        # {'account_desc':'TR-MSCIW','account_name':'Vermögen:Aktien:TR:MSCIW'},
        # {'account_desc':'TR-MSCI-SC','account_name':'Vermögen:Aktien:TR:MSCI-SC'},
        # {'account_desc':'Alle Aktien','account_name':'Vermögen:Aktien'},
        # {'account_desc':'TR Cash','account_name':'Vermögen:Cash:TR'},
        # {'account_desc':'Bond GG Uli','account_name':'Vermögen:Cash:Bondora:GG-Uli'},
        # {'account_desc':'Bond GG Katrin','account_name':'Vermögen:Cash:Bondora:GG-Katrin'},
        # {'account_desc':'Bond P2P','account_name':'Vermögen:P2P:Bondora'},
    ]

    return result
