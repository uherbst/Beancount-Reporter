#!/usr/bin/env python3

from icecream import ic
import beancount as bc
from beanquery import query

beancount_file='test.beancount'
entries, _, opts = bc.loader.load_file(beancount_file)
beanquery = f'SELECT   account,   YEAR(date) AS year,\
MONTH(date) as month,\
value(SUM(position)) as amount, \
currency \
GROUP BY account, year, month,currency \
ORDER BY account, year, month,currency '

cols, rows = query.run_query(entries, opts, beanquery)

ic(cols)
ic(rows)
