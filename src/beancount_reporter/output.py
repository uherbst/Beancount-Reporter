"""Nice output for different beancount reports"""

from icecream import ic
import polars as pl
import polars.selectors as cs
from great_tables import GT, md, html, style, loc

# Rows that carry a subtotal / net worth and should stand out.
SUMMARY_ROWS = ["Summe Vermögen", "Summe Verbindlichkeiten", "Nettovermögen"]


def output_financial_overview(df):
    """Output financial overview df as table."""

    konten = df["Konto"].to_list()
    summary_idx = [i for i, k in enumerate(konten) if k in SUMMARY_ROWS]
    networth_idx = [i for i, k in enumerate(konten) if k == "Nettovermögen"]

    (
        GT(df, rowname_col="Konto")
        .tab_header(
            title="Uli's Finanzübersicht", subtitle="Wo steh ich Monat für Monat ?"
        )
        .fmt_currency(columns=cs.by_dtype(pl.Float64), locale="de", placement="right")
        .tab_style(
            style=style.text(weight="bold"),
            locations=loc.body(rows=summary_idx),
        )
        .tab_style(
            style=style.borders(sides="top", color="#888888", weight="1px"),
            locations=loc.body(rows=summary_idx),
        )
        .tab_style(
            style=style.fill(color="#eef3fb"),
            locations=loc.body(rows=networth_idx),
        )
        .show()
    )
