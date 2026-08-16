"""Regression tests for the bundled financial-overview example."""

from pathlib import Path
from types import SimpleNamespace
import unittest

from beancount_reporter.beancount_reporter import get_financial_overview_dataframe


EXAMPLE_LEDGER = (
    Path(__file__).resolve().parents[1] / "examples" / "monthly-report.beancount"
)


def example_config():
    """Return the fixed configuration used by the public example ledger."""
    return SimpleNamespace(
        common=SimpleNamespace(
            beancount_file=str(EXAMPLE_LEDGER),
            start="2025-01-01",
            end="2025-05-31",
        ),
        groups=SimpleNamespace(
            _raw={
                "Liquid funds": ["Assets:Bank"],
                "Home": ["Assets:Home"],
                "Mortgage": ["Liabilities:Mortgage"],
            }
        ),
    )


class FinancialOverviewTests(unittest.TestCase):
    def test_example_reports_grouped_final_balances_and_net_worth(self):
        overview = get_financial_overview_dataframe(example_config())
        rows = {
            row["Konto"]: row
            for row in overview.to_dicts()
        }

        # The report has the last 12 completed months and an explicit end-date
        # column; the configured end date makes this stable regardless of today.
        self.assertIn("2025-05", overview.columns)
        self.assertIn("2025-05-31", overview.columns)

        self.assertEqual(rows["Liquid funds"]["2025-05-31"], 17600.0)
        self.assertEqual(rows["Home"]["2025-05-31"], 180000.0)
        self.assertEqual(rows["Summe Vermögen"]["2025-05-31"], 197600.0)
        self.assertEqual(rows["Mortgage"]["2025-05-31"], -118400.0)
        self.assertEqual(rows["Summe Verbindlichkeiten"]["2025-05-31"], -118400.0)
        self.assertEqual(rows["Nettovermögen"]["2025-05-31"], 79200.0)

    def test_example_end_date_is_queried_inclusively(self):
        overview = get_financial_overview_dataframe(example_config())
        rows = {row["Konto"]: row for row in overview.to_dicts()}

        # CLOSE ON is exclusive; the implementation asks for 2025-06-01 to
        # represent the balance after all postings through 2025-05-31.
        self.assertEqual(
            rows["Nettovermögen"]["2025-05-31"],
            rows["Nettovermögen"]["2025-05"],
        )


if __name__ == "__main__":
    unittest.main()
