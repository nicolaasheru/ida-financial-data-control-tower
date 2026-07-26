import unittest

import pandas as pd

from src.detect import MODEL_FEATURES, detect_isolation_forest, detect_statistical
from src.features import engineer_features
from src.pipeline import build_analyst_queue
from src.review import merge_review_state
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

    def test_record_key_is_stable_when_source_order_changes(self):
        first = self.base_record()
        second = self.base_record()
        second["country"] = "Another Economy"
        original = validate_and_clean(pd.DataFrame([first, second])).clean
        reordered = validate_and_clean(pd.DataFrame([second, first])).clean
        original_keys = original.set_index("country")["record_key"].to_dict()
        reordered_keys = reordered.set_index("country")["record_key"].to_dict()
        self.assertEqual(original_keys, reordered_keys)

    def test_record_key_is_stable_when_a_new_record_is_appended(self):
        original_record = self.base_record()
        original = validate_and_clean(pd.DataFrame([original_record])).clean
        appended_record = self.base_record()
        appended_record["country"] = "New Economy"
        appended = validate_and_clean(
            pd.DataFrame([original_record, appended_record])
        ).clean
        self.assertEqual(
            original.iloc[0]["record_key"],
            appended.loc[appended["country"].eq("Test Economy"), "record_key"].iloc[0],
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
                    "record_key": "ida_test",
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
                    "record_key": "ida_test",
                    "severity": "medium",
                    "reason_code": "A",
                    "detector": "isolation_forest",
                    "anomaly_score": 0.7,
                    "materiality_percentile": 0.5,
                },
                {
                    "row_id": 1,
                    "record_key": "ida_test",
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
                    "record_key": "ida_test",
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

    def test_review_fields_exist_in_analyst_queue(self):
        signal = pd.DataFrame(
            [
                {
                    "row_id": 1,
                    "record_key": "ida_test",
                    "severity": "medium",
                    "reason_code": "A",
                    "detector": "rule",
                    "anomaly_score": None,
                    "materiality_percentile": 0.5,
                }
            ]
        )
        queue = build_analyst_queue(signal)
        for column in [
            "review_status",
            "review_outcome",
            "review_confidence",
            "evidence_url",
        ]:
            self.assertIn(column, queue.columns)

    def test_empty_review_store_preserves_queue(self):
        signal = pd.DataFrame(
            [
                {
                    "row_id": 1,
                    "record_key": "ida_test",
                    "severity": "medium",
                    "reason_code": "A",
                    "detector": "rule",
                    "anomaly_score": None,
                    "materiality_percentile": 0.5,
                }
            ]
        )
        queue = build_analyst_queue(signal)
        merged = merge_review_state(queue)
        self.assertEqual(merged.iloc[0]["review_status"], "pending")

    def test_isolation_forest_is_deterministic_for_identical_input(self):
        rows = []
        for index in range(40):
            row = {
                "row_id": index,
                "record_key": f"ida_fixture_{index}",
                "entity_type": "country",
                "period_type": "annual",
                "category": "Commitments",
                "materiality_percentile": index / 39,
            }
            for feature_index, feature in enumerate(MODEL_FEATURES):
                row[feature] = float(index + feature_index) / 10
            rows.append(row)
        rows[-1]["relative_change"] = 500.0
        fixture = pd.DataFrame(rows)

        first, _ = detect_isolation_forest(fixture)
        second, _ = detect_isolation_forest(fixture)
        columns = ["record_key", "anomaly_score", "model_segment"]
        pd.testing.assert_frame_equal(
            first[columns].reset_index(drop=True),
            second[columns].reset_index(drop=True),
        )

    def test_statistical_control_flags_material_country_shift(self):
        features = pd.DataFrame(
            [
                {
                    "row_id": 1,
                    "record_key": "ida_shift",
                    "entity_type": "country",
                    "period_type": "annual",
                    "category": "Commitments",
                    "total": 220.0,
                    "previous_year_total": 20.0,
                    "year_over_year_change": 10.0,
                }
            ]
        )
        alerts = detect_statistical(features)
        self.assertEqual(alerts.iloc[0]["reason_code"], "YEAR_OVER_YEAR_SHIFT")

    def test_statistical_control_excludes_aggregate_shift(self):
        features = pd.DataFrame(
            [
                {
                    "row_id": 1,
                    "record_key": "ida_aggregate_shift",
                    "entity_type": "aggregate_or_institution",
                    "period_type": "annual",
                    "category": "Commitments",
                    "total": 220.0,
                    "previous_year_total": 20.0,
                    "year_over_year_change": 10.0,
                }
            ]
        )
        self.assertTrue(detect_statistical(features).empty)


if __name__ == "__main__":
    unittest.main()
