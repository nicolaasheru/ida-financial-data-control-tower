import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import create_app
from backend.store import (
    ReviewConflictError,
    ReviewNotFoundError,
    ReviewStore,
    ReviewValidationError,
)


class ReviewStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.alerts_path = root / "alerts.csv"
        with self.alerts_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=["record_key", "row_id", "country"]
            )
            writer.writeheader()
            writer.writerow(
                {
                    "record_key": "ida_test_economy",
                    "row_id": 101,
                    "country": "Test Economy",
                }
            )
        self.store = ReviewStore(
            database_path=root / "reviews.sqlite3",
            alerts_path=self.alerts_path,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def payload(self, **overrides) -> dict:
        payload = {
            "review_status": "in_review",
            "review_outcome": "needs_more_information",
            "reviewer": "Test Analyst",
            "review_notes": "Checking supporting records.",
            "review_confidence": "medium",
            "evidence_url": "",
            "expected_version": 0,
        }
        payload.update(overrides)
        return payload

    def test_unknown_alert_is_rejected(self):
        with self.assertRaises(ReviewNotFoundError):
            self.store.get_review("ida_missing")

    def test_pending_alert_can_enter_review(self):
        result = self.store.update_review("ida_test_economy", self.payload())
        self.assertEqual(result["review_status"], "in_review")
        self.assertEqual(result["version"], 1)

    def test_pending_alert_cannot_resolve_directly(self):
        with self.assertRaises(ReviewValidationError):
            self.store.update_review(
                "ida_test_economy",
                self.payload(
                    review_status="resolved",
                    review_outcome="legitimate_exception",
                    expected_version=0,
                ),
            )

    def test_resolved_alert_requires_notes_and_confidence(self):
        in_review = self.store.update_review("ida_test_economy", self.payload())
        with self.assertRaises(ReviewValidationError):
            self.store.update_review(
                "ida_test_economy",
                self.payload(
                    review_status="resolved",
                    review_outcome="confirmed_data_issue",
                    review_notes="",
                    review_confidence="",
                    expected_version=in_review["version"],
                ),
            )

    def test_final_outcome_requires_resolved_status(self):
        with self.assertRaises(ReviewValidationError):
            self.store.update_review(
                "ida_test_economy",
                self.payload(review_outcome="false_positive"),
            )

    def test_stale_version_is_rejected(self):
        self.store.update_review("ida_test_economy", self.payload())
        with self.assertRaises(ReviewConflictError):
            self.store.update_review(
                "ida_test_economy", self.payload(expected_version=0)
            )

    def test_audit_history_records_every_update(self):
        first = self.store.update_review("ida_test_economy", self.payload())
        self.store.update_review(
            "ida_test_economy",
            self.payload(
                review_status="resolved",
                review_outcome="legitimate_exception",
                review_notes="Official source confirms the value.",
                review_confidence="high",
                evidence_url="https://example.com/evidence",
                expected_version=first["version"],
            ),
        )
        history = self.store.get_history("ida_test_economy")
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["new_status"], "resolved")
        self.assertEqual(history[1]["new_status"], "in_review")

    def test_legacy_integer_review_migrates_to_stable_record_key(self):
        root = Path(self.temp_dir.name)
        legacy_database = root / "legacy.sqlite3"
        with sqlite3.connect(legacy_database) as connection:
            connection.execute(
                """
                CREATE TABLE reviews (
                    row_id INTEGER PRIMARY KEY,
                    review_status TEXT NOT NULL,
                    review_outcome TEXT NOT NULL,
                    reviewer TEXT NOT NULL,
                    review_notes TEXT NOT NULL,
                    reviewed_at TEXT NOT NULL,
                    review_confidence TEXT NOT NULL,
                    evidence_url TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                INSERT INTO reviews VALUES (
                    101, 'resolved', 'legitimate_exception',
                    'Legacy Analyst', 'Verified legacy decision.',
                    '2026-07-26T00:00:00Z', 'high', '', 2,
                    '2026-07-26T00:00:00Z', '2026-07-26T00:00:00Z'
                )
                """
            )
        migrated = ReviewStore(
            database_path=legacy_database,
            alerts_path=self.alerts_path,
        )
        record = migrated.get_review("ida_test_economy")
        self.assertEqual(record["review_status"], "resolved")
        self.assertEqual(record["reviewer"], "Legacy Analyst")


class ReviewApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        database_path = root / "api-reviews.sqlite3"
        alerts_path = root / "alerts.csv"
        with alerts_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=["record_key", "row_id", "country"]
            )
            writer.writeheader()
            writer.writerow(
                {
                    "record_key": "ida_api_test",
                    "row_id": 2159,
                    "country": "Test Economy",
                }
            )
        reviews_path = root / "reviews.csv"
        with reviews_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "record_key",
                    "row_id",
                    "review_status",
                    "review_outcome",
                    "reviewer",
                    "review_notes",
                    "reviewed_at",
                    "review_confidence",
                    "evidence_url",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "record_key": "ida_api_test",
                    "row_id": 2159,
                    "review_status": "resolved",
                    "review_outcome": "legitimate_exception",
                    "reviewer": "Fixture Analyst",
                    "review_notes": "Verified fixture.",
                    "reviewed_at": "2026-07-26T00:00:00Z",
                    "review_confidence": "high",
                    "evidence_url": "",
                }
            )
        self.client = TestClient(
            create_app(database_path, alerts_path, reviews_path)
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "healthy")

    def test_root_describes_service(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["documentation"], "/docs")

    def test_missing_alert_returns_404(self):
        response = self.client.get("/api/reviews/ida_missing")
        self.assertEqual(response.status_code, 404)

    def test_seeded_review_is_available(self):
        response = self.client.get("/api/reviews/ida_api_test")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["review_status"], "resolved")


if __name__ == "__main__":
    unittest.main()
