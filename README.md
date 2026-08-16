# Beancount-Reporter
Create PDF reports from your beancount data

I'm a great fan of beancount - but I miss my monthly reports, that I could check in the ages before beancount with excel.

I've checked the existing beancount-reporting solutions:
- fava
- beancount-multiperiod-reports

... but somehow they don't match my requirements.

Dont get me wrong: Fava is great for day-to-day use, but not to generate PDF reports.

## Run the example

The repository includes a small, anonymized EUR ledger and configuration that
exercise the financial-overview report. Install the project and run:

```bash
pip install -e .
python src/BeancountReporter.py -f examples/monthly-report.toml
```

The report opens in a browser through Great Tables. Copy the example TOML file
and replace `beancount_file` with the path to your own ledger; keep personal
configuration in `localconfig/`, which is ignored by Git.

## Test

After installing the project, run the regression suite with:

```bash
python -m unittest discover -v
```

The tests use the bundled anonymized ledger and check the grouped balances and
net worth at its configured end date.
