import unittest

import pandas as pd

from src.validate import validate_and_clean


class FinancialControlTests(unittest.TestCase):
    def base_record(self) -> dict:
        return {
            "category": "Commitments",
            "country": "Test Economy",
            "development_policy": 10.0,
            "investment_lending": 20.0,
            "organization": "IDA",
            "others": 0.0,
            "program_for_results": 0.0,
            "region": "TEST REGION",
            "time_period": "2026-Q3",
            "total": 30.0,
        }

    def test_reconciled_record_passes_total_control(self):
        result = validate_and_clean(pd.DataFrame([self.base_record()]))
        self.assertNotIn(
            "TOTAL_MISMATCH",
            result.alerts.get("reason_code", pd.Series(dtype=str)).tolist(),
        )

    def test_broken_total_is_flagged(self):
        record = self.base_record()
        record["total"] = 50.0
        result = validate_and_clean(pd.DataFrame([record]))
        self.assertIn("TOTAL_MISMATCH", result.alerts["reason_code"].tolist())

    def test_duplicate_grain_is_flagged(self):
        record = self.base_record()
        result = validate_and_clean(pd.DataFrame([record, record]))
        self.assertEqual(
            result.alerts["reason_code"].tolist().count("DUPLICATE_GRAIN"), 2
        )


if __name__ == "__main__":
    unittest.main()
