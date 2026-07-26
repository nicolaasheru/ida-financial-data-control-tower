from __future__ import annotations

import csv
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


VALID_STATUSES = {"pending", "in_review", "resolved"}
FINAL_OUTCOMES = {
    "confirmed_data_issue",
    "legitimate_exception",
    "false_positive",
}
VALID_OUTCOMES = FINAL_OUTCOMES | {"needs_more_information"}
VALID_CONFIDENCE = {"high", "medium", "low"}
ALLOWED_TRANSITIONS = {
    "pending": {"pending", "in_review"},
    "in_review": {"in_review", "resolved"},
    "resolved": {"resolved", "in_review"},
}


class ReviewValidationError(ValueError):
    pass


class ReviewConflictError(RuntimeError):
    pass


class ReviewNotFoundError(LookupError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ReviewStore:
    def __init__(
        self,
        database_path: Path,
        alerts_path: Path,
        seed_reviews_path: Path | None = None,
    ) -> None:
        self.database_path = Path(database_path)
        self.alerts_path = Path(alerts_path)
        self.seed_reviews_path = Path(seed_reviews_path) if seed_reviews_path else None
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._alert_ids = self._load_alert_ids()
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
        finally:
            connection.close()

    def _load_alert_ids(self) -> set[int]:
        with self.alerts_path.open(newline="", encoding="utf-8") as handle:
            return {
                int(row["row_id"])
                for row in csv.DictReader(handle)
                if row.get("row_id")
            }

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS reviews (
                    row_id INTEGER PRIMARY KEY,
                    review_status TEXT NOT NULL,
                    review_outcome TEXT NOT NULL DEFAULT '',
                    reviewer TEXT NOT NULL DEFAULT '',
                    review_notes TEXT NOT NULL DEFAULT '',
                    reviewed_at TEXT NOT NULL DEFAULT '',
                    review_confidence TEXT NOT NULL DEFAULT '',
                    evidence_url TEXT NOT NULL DEFAULT '',
                    version INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS review_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    row_id INTEGER NOT NULL,
                    previous_status TEXT NOT NULL,
                    new_status TEXT NOT NULL,
                    previous_outcome TEXT NOT NULL DEFAULT '',
                    new_outcome TEXT NOT NULL DEFAULT '',
                    actor TEXT NOT NULL,
                    event_note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    resulting_version INTEGER NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_review_events_row
                    ON review_events (row_id, event_id);
                """
            )
            connection.commit()
        self.seed_from_csv()

    def seed_from_csv(self) -> None:
        if not self.seed_reviews_path or not self.seed_reviews_path.exists():
            return
        with self.seed_reviews_path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        now = utc_now()
        with self.connect() as connection:
            for row in rows:
                row_id = int(row["row_id"])
                if row_id not in self._alert_ids:
                    continue
                connection.execute(
                    """
                    INSERT OR IGNORE INTO reviews (
                        row_id, review_status, review_outcome, reviewer,
                        review_notes, reviewed_at, review_confidence,
                        evidence_url, version, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (
                        row_id,
                        row.get("review_status") or "pending",
                        row.get("review_outcome") or "",
                        row.get("reviewer") or "",
                        row.get("review_notes") or "",
                        row.get("reviewed_at") or "",
                        row.get("review_confidence") or "",
                        row.get("evidence_url") or "",
                        now,
                        now,
                    ),
                )
            connection.commit()

    def _default_review(self, row_id: int) -> dict:
        if row_id not in self._alert_ids:
            raise ReviewNotFoundError(f"Alert {row_id} does not exist")
        return {
            "row_id": row_id,
            "review_status": "pending",
            "review_outcome": "",
            "reviewer": "",
            "review_notes": "",
            "reviewed_at": "",
            "review_confidence": "",
            "evidence_url": "",
            "version": 0,
            "created_at": "",
            "updated_at": "",
        }

    def get_review(self, row_id: int) -> dict:
        if row_id not in self._alert_ids:
            raise ReviewNotFoundError(f"Alert {row_id} does not exist")
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM reviews WHERE row_id = ?", (row_id,)
            ).fetchone()
        return dict(row) if row else self._default_review(row_id)

    def list_reviews(self) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM reviews ORDER BY updated_at DESC, row_id"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_history(self, row_id: int) -> list[dict]:
        if row_id not in self._alert_ids:
            raise ReviewNotFoundError(f"Alert {row_id} does not exist")
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM review_events
                WHERE row_id = ?
                ORDER BY event_id DESC
                """,
                (row_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def _validate(self, previous: dict, update: dict) -> None:
        status = update["review_status"]
        outcome = update.get("review_outcome", "")
        confidence = update.get("review_confidence", "")
        reviewer = update.get("reviewer", "").strip()
        notes = update.get("review_notes", "").strip()

        if status not in VALID_STATUSES:
            raise ReviewValidationError(f"Invalid status: {status}")
        if status not in ALLOWED_TRANSITIONS[previous["review_status"]]:
            raise ReviewValidationError(
                f"Cannot move from {previous['review_status']} to {status}"
            )
        if outcome and outcome not in VALID_OUTCOMES:
            raise ReviewValidationError(f"Invalid outcome: {outcome}")
        if confidence and confidence not in VALID_CONFIDENCE:
            raise ReviewValidationError(f"Invalid confidence: {confidence}")
        if not reviewer:
            raise ReviewValidationError("Reviewer is required")
        if status == "pending" and outcome:
            raise ReviewValidationError("Pending alerts cannot have an outcome")
        if status == "in_review" and outcome not in {"", "needs_more_information"}:
            raise ReviewValidationError(
                "Final outcomes require resolved status"
            )
        if status == "resolved":
            if outcome not in FINAL_OUTCOMES:
                raise ReviewValidationError(
                    "Resolved alerts require a final outcome"
                )
            if not notes:
                raise ReviewValidationError("Resolved alerts require review notes")
            if not confidence:
                raise ReviewValidationError(
                    "Resolved alerts require a confidence level"
                )

    def update_review(self, row_id: int, update: dict) -> dict:
        if row_id not in self._alert_ids:
            raise ReviewNotFoundError(f"Alert {row_id} does not exist")
        previous = self.get_review(row_id)
        expected_version = int(update.pop("expected_version"))
        if expected_version != previous["version"]:
            raise ReviewConflictError(
                f"Expected version {expected_version}; current version is "
                f"{previous['version']}"
            )

        normalized = {
            "review_status": update.get("review_status", "").strip(),
            "review_outcome": update.get("review_outcome", "").strip(),
            "reviewer": update.get("reviewer", "").strip(),
            "review_notes": update.get("review_notes", "").strip(),
            "review_confidence": update.get("review_confidence", "").strip(),
            "evidence_url": update.get("evidence_url", "").strip(),
        }
        self._validate(previous, normalized)
        now = utc_now()
        reviewed_at = now if normalized["review_status"] != "pending" else ""
        new_version = previous["version"] + 1

        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute(
                "SELECT version FROM reviews WHERE row_id = ?", (row_id,)
            ).fetchone()
            current_version = int(current["version"]) if current else 0
            if current_version != expected_version:
                connection.rollback()
                raise ReviewConflictError(
                    f"Expected version {expected_version}; current version is "
                    f"{current_version}"
                )

            connection.execute(
                """
                INSERT INTO reviews (
                    row_id, review_status, review_outcome, reviewer,
                    review_notes, reviewed_at, review_confidence,
                    evidence_url, version, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(row_id) DO UPDATE SET
                    review_status = excluded.review_status,
                    review_outcome = excluded.review_outcome,
                    reviewer = excluded.reviewer,
                    review_notes = excluded.review_notes,
                    reviewed_at = excluded.reviewed_at,
                    review_confidence = excluded.review_confidence,
                    evidence_url = excluded.evidence_url,
                    version = excluded.version,
                    updated_at = excluded.updated_at
                """,
                (
                    row_id,
                    normalized["review_status"],
                    normalized["review_outcome"],
                    normalized["reviewer"],
                    normalized["review_notes"],
                    reviewed_at,
                    normalized["review_confidence"],
                    normalized["evidence_url"],
                    new_version,
                    previous["created_at"] or now,
                    now,
                ),
            )
            connection.execute(
                """
                INSERT INTO review_events (
                    row_id, previous_status, new_status, previous_outcome,
                    new_outcome, actor, event_note, created_at,
                    resulting_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row_id,
                    previous["review_status"],
                    normalized["review_status"],
                    previous["review_outcome"],
                    normalized["review_outcome"],
                    normalized["reviewer"],
                    normalized["review_notes"],
                    now,
                    new_version,
                ),
            )
            connection.commit()
        return self.get_review(row_id)
