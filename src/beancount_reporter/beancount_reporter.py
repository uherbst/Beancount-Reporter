"""Different report types for Beancount data"""

from icecream import ic
import datetime
import os
from typing import cast

# from beancount_reporter.config import Config
# from beancount.loader import load_file
# from beanquery.query import run_query
# from beanquery.numberify import numberify_results
import beancount as bc

# import beanquery as bq
from beanquery import query
from beanquery import numberify

# FIXME: Verschiebe ich Berechnungen in andere Module ?
import polars as pl


def get_list_of_dates_for_query(config):
    """Return list of points in the past to query for a balance."""
    # FIXME: start_date = datetime.date.fromisoformat("2014-01-01")
    start_date = datetime.date.fromisoformat("2024-01-01")
    if hasattr(config.common, "start"):
        start_date = datetime.date.fromisoformat(config.common.start)
    end_date = datetime.date.today()
    if hasattr(config.common, "end"):
        end_date = datetime.date.fromisoformat(config.common.end)

    # FIXME: Das ist nur monatlich und optimiert
    # jährlich fehlt noch
    dates = []
    date = start_date
    while date < end_date:
        if date.day == 1:
            dates.append(date)
        date += datetime.timedelta(days=1)

    # if args.zeitachse == "optimiert":
    for i in range(len(dates) - 13, 0, -1):
        if dates[i].month != 1:
            del dates[i]

    # den aktuellen Tag noch dazufügen
    dates.append(end_date)
    return dates


def get_financial_overview_dataframe(config):
    """return dataset with financial overview per month."""

    # read ledger file
    if not os.path.isfile(config.common.beancount_file):
        # FIXME: Better error output ? logger ? ic ?
        print(f"File not found: {config.common.beancount_file}")
        exit(-1)

    entries, _, opts = bc.loader.load_file(config.common.beancount_file)
    ## ic(opts)
    currency = opts["operating_currency"][0]
    name_assets = opts["name_assets"]
    name_liabilities = opts["name_liabilities"]

    dates = get_list_of_dates_for_query(config)

    where_clause = f"account ~ '{name_assets}' " f"or account ~ '{name_liabilities}'"
    ledger_entries = "undefined"
    for date in dates:
        beanquery = f"SELECT   account,   YEAR(date) AS year,\
        MONTH(date) as month,\
        SUM(convert(position, 'EUR', date)) AS amount\
        FROM OPEN ON {date.isoformat()} CLOSE ON {date.isoformat()} \
        WHERE {where_clause} \
        GROUP BY account, year, month\
        ORDER BY account, year, month"

        cols, rows = query.run_query(entries, opts, beanquery)
        # For later calcs, I need month with leading 0
        my_rows = []
        for row in rows:
            my_row = list(row)
            my_row[2] = "{:02d}".format(my_row[2])
            my_rows.append(my_row)

        if ledger_entries == "undefined":
            ledger_entries = my_rows
        else:
            for entry in my_rows:
                ledger_entries.append(entry)

    cols, ledger_entries = numberify.numberify_results(cols, ledger_entries)

    # FIXME: Spalten-Namen konfigurierbar machen
    df = pl.DataFrame(
        ledger_entries,
        strict=False,
        orient="row",
        schema={"Konto": str, "Jahr": str, "Monat": str, "Betrag": float},
    )
    df = df[["Konto", "Jahr", "Monat", "Betrag"]].fill_nan(0)

    # Ich brauche 2023-04 als eindeutiges Feld für Jahr + Monat
    df = (
        df.with_columns(
            pl.concat_str(
                [pl.col("Jahr"), pl.col("Monat")],
                separator="-",
            ).alias("JahrMonat")
        )
        .drop(
            # I don't need Year / Month anymore
            "Jahr",
            "Monat",
        )
        .pivot(
            # Translate table
            on="JahrMonat",
            index="Konto",
            aggregate_function="sum",
        )
    )
    dummy = df.sum()
    dummy[0, "Konto"] = "Summe"
    df = pl.concat([df, dummy])
    return df


def output_df(df):
    """Output datafram as table."""

    print(df)
