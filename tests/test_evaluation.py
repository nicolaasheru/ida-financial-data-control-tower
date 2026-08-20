import unittest

from src.evaluate import evaluate_sensitivity, inject_controlled_anomalies
from src.ingest import load_raw


class EvaluationRobustnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = load_raw(refresh=False)

    def test_same_seed_selects_identical_targets(self):
        _, first = inject_controlled_anomalies(
            self.source,
            random_state=42,
        )
        _, second = inject_controlled_anomalies(
            self.source,
            random_state=42,
        )
        self.assertEqual(first, second)

    def test_different_seeds_vary_target_records(self):
        _, first = inject_controlled_anomalies(
            self.source,
            random_state=11,
        )
        _, second = inject_controlled_anomalies(
            self.source,
            random_state=73,
        )
        first_targets = [tuple(item["row_ids"]) for item in first]
        second_targets = [tuple(item["row_ids"]) for item in second]
        self.assertNotEqual(first_targets, second_targets)

    def test_each_run_covers_all_control_families(self):
        _, labels = inject_controlled_anomalies(
            self.source,
            random_state=101,
        )
        expected_codes = {
            code
            for label in labels
            for code in label["expected_codes"]
        }
        self.assertIn("TOTAL_MISMATCH", expected_codes)
        self.assertIn("YEAR_OVER_YEAR_SHIFT", expected_codes)
        self.assertIn("MULTIVARIATE_ANOMALY", expected_codes)

    def test_sensitivity_grid_reports_recall_and_workload(self):
        rows = evaluate_sensitivity(
            self.source,
            seeds=(11,),
            contamination_grid=(0.01, 0.02),
        )
        self.assertEqual([row["contamination"] for row in rows], [0.01, 0.02])
        self.assertTrue(rows[0]["selected"])
        self.assertGreater(rows[1]["ml_alerts"], rows[0]["ml_alerts"])
        self.assertIn("controlled_fault_recall", rows[0])
        self.assertIn("moderate_spike_recall", rows[0])
        self.assertIn("severe_spike_recall", rows[0])
        self.assertIn("alert_change_vs_selected", rows[0])


if __name__ == "__main__":
    unittest.main()
