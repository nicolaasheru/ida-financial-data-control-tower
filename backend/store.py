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
    """Transactional analyst-review store keyed by stable financial grain."""

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
        self._alerts = self._load_alerts()
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

    def _load_alerts(self) -> dict[str, int]:
        with self.alerts_path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        if rows and "record_key" not in rows[0]:
            raise ReviewValidationError(
                "alerts.csv does not contain stable record_key values; rerun the pipeline"
            )
        return {
            str(row["record_key"]): int(row["row_id"])
            for row in rows
            if row.get("record_key") and row.get("row_id")
        }

    def _legacy_key_for_row_id(self, row_id: int | str) -> str | None:
        target = int(row_id)
        return next(
            (key for key, current_row_id in self._alerts.items() if current_row_id == target),
            None,
        )

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS review_records (
                    record_key TEXT PRIMARY KEY,
                    row_id INTEGER NOT NULL,
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

                CREATE TABLE IF NOT EXISTS review_events_v2 (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_key TEXT NOT NULL,
                    previous_status TEXT NOT NULL,
                    new_status TEXT NOT NULL,
                    previous_outcome TEXT NOT NULL DEFAULT '',
                    new_outcome TEXT NOT NULL DEFAULT '',
                    actor TEXT NOT NULL,
                    event_note TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    resulting_version INTEGER NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_review_events_record
                    ON review_events_v2 (record_key, event_id);
                """
            )
            connection.commit()
        self._migrate_legacy_tables()
        self.seed_from_csv()

    def _migrate_legacy_tables(self) -> None:
        """Copy v1 integer-keyed local reviews into the stable-key schema once."""
        with self.connect() as connection:
            tables = {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            if "reviews" not in tables:
                return
            legacy_reviews = connection.execute("SELECT * FROM reviews").fetchall()
            for row in legacy_reviews:
                values = dict(row)
                record_key = self._legacy_key_for_row_id(values["row_id"])
                if not record_key:
                    continue
                connection.execute(
                    """
                    INSERT OR IGNORE INTO review_records (
                        record_key, row_id, review_status, review_outcome,
                        reviewer, review_notes, reviewed_at, review_confidence,
                        evidence_url, version, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record_key,
                        self._alerts[record_key],
                        values["review_status"],
                        values["review_outcome"],
                        values["reviewer"],
                        values["review_notes"],
                        values["reviewed_at"],
                        values["review_confidence"],
                        values["evidence_url"],
                        values["version"],
                        values["created_at"],
                        values["updated_at"],
                    ),
                )
            if "review_events" in tables:
                legacy_events = connection.execute(
                    "SELECT * FROM review_events ORDER BY event_id"
                ).fetchall()
                for row in legacy_events:
                    values = dict(row)
                    record_key = self._legacy_key_for_row_id(values["row_id"])
                    if not record_key:
                        continue
                    connection.execute(
                        """
                        INSERT OR IGNORE INTO review_events_v2 (
                            event_id, record_key, previous_status, new_status,
                            previous_outcome, new_outcome, actor, event_note,
                            created_at, resulting_version
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            values["event_id"],
                            record_key,
                            values["previous_status"],
                            values["new_status"],
                            values["previous_outcome"],
                            values["new_outcome"],
                            values["actor"],
                            values["event_note"],
                            values["created_at"],
                            values["resulting_version"],
                        ),
                    )
            connection.commit()

    def seed_from_csv(self) -> None:
        if not self.seed_reviews_path or not self.seed_reviews_path.exists():
            return
        with self.seed_reviews_path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        now = utc_now()
        with self.connect() as connection:
            for row in rows:
                record_key = row.get("record_key") or self._legacy_key_for_row_id(
                    row.get("row_id", "")
                )
                if not record_key or record_key not in self._alerts:
                    continue
                connection.execute(
                    """
                    INSERT OR IGNORE INTO review_records (
                        record_key, row_id, review_status, review_outcome,
                        reviewer, review_notes, reviewed_at, review_confidence,
                        evidence_url, version, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (
                        record_key,
                        self._alerts[record_key],
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

    def _default_review(self, record_key: str) -> dict:
        if record_key not in self._alerts:
            raise ReviewNotFoundError(f"Alert {record_key} does not exist")
        return {
            "record_key": record_key,
            "row_id": self._alerts[record_key],
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

    def get_review(self, record_key: str) -> dict:
        if record_key not in self._alerts:
            raise ReviewNotFoundError(f"Alert {record_key} does not exist")
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM review_records WHERE record_key = ?", (record_key,)
            ).fetchone()
        if not row:
            return self._default_review(record_key)
        result = dict(row)
        result["row_id"] = self._alerts[record_key]
        return result

    def list_reviews(self) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM review_records ORDER BY updated_at DESC, record_key"
            ).fetchall()
        results = []
        for row in rows:
            result = dict(row)
            if result["record_key"] in self._alerts:
                result["row_id"] = self._alerts[result["record_key"]]
                results.append(result)
        return results

    def get_history(self, record_key: str) -> list[dict]:
        if record_key not in self._alerts:
            raise ReviewNotFoundError(f"Alert {record_key} does not exist")
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM review_events_v2
                WHERE record_key = ?
                ORDER BY event_id DESC
                """,
                (record_key,),
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
            raise ReviewValidationError("Final outcomes require resolved status")
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

    def update_review(self, record_key: str, update: dict) -> dict:
        if record_key not in self._alerts:
            raise ReviewNotFoundError(f"Alert {record_key} does not exist")
        previous = self.get_review(record_key)
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
                "SELECT version FROM review_records WHERE record_key = ?",
                (record_key,),
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
                INSERT INTO review_records (
                    record_key, row_id, review_status, review_outcome, reviewer,
                    review_notes, reviewed_at, review_confidence, evidence_url,
                    version, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(record_key) DO UPDATE SET
                    row_id = excluded.row_id,
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
                    record_key,
                    self._alerts[record_key],
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
                INSERT INTO review_events_v2 (
                    record_key, previous_status, new_status, previous_outcome,
                    new_outcome, actor, event_note, created_at,
                    resulting_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_key,
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
        return self.get_review(record_key)
