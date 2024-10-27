"""Nice output for different beancount reports"""

from icecream import ic
import polars as pl
import polars.selectors as cs
from great_tables import GT, md, html

import polars as pl


def output_financial_overview(df):
    """Output financial overview df as table."""

    (
        GT(df)
        .tab_header(
            title="Uli's Finanzübersicht", subtitle="Wo steh ich Monat für Monat ?"
        )
        .fmt_currency(columns=cs.by_dtype(pl.Float64), locale="de", placement="right")
        .show()
    )
