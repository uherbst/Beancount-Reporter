#!python

"""
BeancountReporter - create monthly beancount report.

- FIXME Details
"""

# Import the main package
import beancount_reporter as br
from beancount_reporter.config import Config
from icecream import ic

ic.enable()

# Run the function if this is the main file executed
if __name__ == "__main__":
    config = br.Config()
    df = br.get_financial_overview_dataframe(config)
    br.output_df(df)
