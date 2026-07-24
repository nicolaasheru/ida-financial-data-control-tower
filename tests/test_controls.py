import unittest

import pandas as pd

from src.features import engineer_features
from src.pipeline import build_analyst_queue
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

    def test_annual_and_quarterly_history_do_not_mix(self):
        records = []
        for period, total in [("FY24", 100.0), ("2025-Q1", 20.0), ("FY25", 120.0)]:
            record = self.base_record()
            record["time_period"] = period
            record["total"] = total
            record["investment_lending"] = total - 10.0
            records.append(record)
        features = engineer_features(validate_and_clean(pd.DataFrame(records)).clean)
        annual_2025 = features.loc[features["time_period"].eq("FY25")].iloc[0]
        self.assertEqual(annual_2025["previous_total"], 100.0)

    def test_tiny_commitment_suppresses_ratio(self):
        commitment = self.base_record()
        commitment["total"] = 0.19
        commitment["development_policy"] = 0.19
        commitment["investment_lending"] = 0.0
        disbursement = commitment.copy()
        disbursement["category"] = "Gross Disbursements"
        disbursement["total"] = 18.0
        disbursement["development_policy"] = 18.0
        features = engineer_features(
            validate_and_clean(pd.DataFrame([commitment, disbursement])).clean
        )
        self.assertTrue(features["disbursement_commitment_ratio"].isna().all())
        self.assertFalse(features["ratio_denominator_eligible"].any())

    def test_material_commitment_calculates_ratio(self):
        commitment = self.base_record()
        disbursement = commitment.copy()
        disbursement["category"] = "Gross Disbursements"
        disbursement["total"] = 60.0
        disbursement["investment_lending"] = 50.0
        features = engineer_features(
            validate_and_clean(pd.DataFrame([commitment, disbursement])).clean
        )
        self.assertTrue((features["disbursement_commitment_ratio"] == 2.0).all())

    def test_institutional_aggregate_is_labeled(self):
        record = self.base_record()
        record["country"] = "MIGA"
        features = engineer_features(validate_and_clean(pd.DataFrame([record])).clean)
        self.assertEqual(features.iloc[0]["entity_type"], "aggregate_or_institution")

    def test_ml_only_signal_cannot_be_critical(self):
        signal = pd.DataFrame(
            [
                {
                    "row_id": 1,
                    "severity": "high",
                    "reason_code": "MULTIVARIATE_ANOMALY",
                    "detector": "isolation_forest",
                    "anomaly_score": 1.0,
                    "materiality_percentile": 1.0,
                }
            ]
        )
        queue = build_analyst_queue(signal)
        self.assertEqual(queue.iloc[0]["severity"], "high")

    def test_detector_agreement_elevates_alert(self):
        signals = pd.DataFrame(
            [
                {
                    "row_id": 1,
                    "severity": "medium",
                    "reason_code": "A",
                    "detector": "isolation_forest",
                    "anomaly_score": 0.7,
                    "materiality_percentile": 0.5,
                },
                {
                    "row_id": 1,
                    "severity": "medium",
                    "reason_code": "B",
                    "detector": "statistical_process_control",
                    "anomaly_score": 0.6,
                    "materiality_percentile": 0.5,
                },
            ]
        )
        queue = build_analyst_queue(signals)
        self.assertEqual(queue.iloc[0]["severity"], "high")
        self.assertTrue(queue.iloc[0]["corroborated"])

    def test_aggregate_reconciliation_does_not_remain_critical(self):
        signal = pd.DataFrame(
            [
                {
                    "row_id": 1,
                    "severity": "medium",
                    "reason_code": "TOTAL_MISMATCH",
                    "detector": "rule",
                    "anomaly_score": None,
                    "materiality_percentile": 1.0,
                    "entity_type": "aggregate_or_institution",
                }
            ]
        )
        queue = build_analyst_queue(signal)
        self.assertEqual(queue.iloc[0]["severity"], "medium")


if __name__ == "__main__":
    unittest.main()
