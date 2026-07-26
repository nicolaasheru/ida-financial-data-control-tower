from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone

import pandas as pd

from .config import (
    ALERT_FILE,
    ARTIFACT_DIR,
    REVIEW_FILE,
    REVIEW_DATABASE_FILE,
    REVIEW_SAMPLE_FILE,
    REVIEW_SUMMARY_FILE,
)


VALID_OUTCOMES = {
    "confirmed_data_issue",
    "legitimate_exception",
    "false_positive",
    "needs_more_information",
}
VALID_CONFIDENCE = {"high", "medium", "low"}
REVIEW_COLUMNS = [
    "row_id",
    "review_status",
    "review_outcome",
    "reviewer",
    "review_notes",
    "reviewed_at",
    "review_confidence",
    "evidence_url",
]


def load_review_store() -> pd.DataFrame:
    if REVIEW_DATABASE_FILE.exists():
        with sqlite3.connect(REVIEW_DATABASE_FILE) as connection:
            reviews = pd.read_sql_query(
                """
                SELECT
                    row_id,
                    review_status,
                    review_outcome,
                    reviewer,
                    review_notes,
                    reviewed_at,
                    review_confidence,
                    evidence_url
                FROM reviews
                """,
                connection,
                dtype={"row_id": "Int64"},
            )
        for column in REVIEW_COLUMNS:
            if column not in reviews:
                reviews[column] = ""
        return reviews[REVIEW_COLUMNS].drop_duplicates("row_id", keep="last")
    if not REVIEW_FILE.exists():
        return pd.DataFrame(columns=REVIEW_COLUMNS)
    reviews = pd.read_csv(REVIEW_FILE, dtype={"row_id": "Int64"})
    for column in REVIEW_COLUMNS:
        if column not in reviews:
            reviews[column] = ""
    return reviews[REVIEW_COLUMNS].drop_duplicates("row_id", keep="last")


def merge_review_state(alerts: pd.DataFrame) -> pd.DataFrame:
    if alerts.empty:
        return alerts
    reviews = load_review_store()
    if reviews.empty:
        return alerts

    output = alerts.copy()
    review_lookup = reviews.set_index("row_id")
    for column in REVIEW_COLUMNS[1:]:
        output[column] = output.get(
            column, pd.Series("", index=output.index)
        ).fillna("").astype("string")
        mapped = output["row_id"].map(review_lookup[column])
        populated = mapped.notna() & mapped.astype("string").str.strip().ne("")
        output.loc[populated, column] = mapped.loc[populated].astype("string")
    return output


def sync_sample_to_review_store(sample: pd.DataFrame) -> pd.DataFrame:
    missing = [column for column in REVIEW_COLUMNS if column not in sample]
    if missing:
        raise ValueError(f"Review sample is missing columns: {missing}")

    updates = sample[REVIEW_COLUMNS].copy()
    updates["review_outcome"] = updates["review_outcome"].fillna("").str.strip()
    updates["review_status"] = updates["review_status"].fillna("").str.strip()
    updates = updates.loc[
        updates["review_outcome"].ne("") | updates["review_status"].ne("pending")
    ]

    existing = load_review_store()
    combined = pd.concat([existing, updates], ignore_index=True)
    combined = combined.drop_duplicates("row_id", keep="last")
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    combined.to_csv(REVIEW_FILE, index=False)
    return combined


def create_review_sample(
    sample_size: int = 30,
    random_state: int = 42,
    regenerate: bool = False,
) -> pd.DataFrame:
    if REVIEW_SAMPLE_FILE.exists() and not regenerate:
        sample = pd.read_csv(REVIEW_SAMPLE_FILE)
        for column in REVIEW_COLUMNS[1:]:
            if column not in sample:
                sample[column] = ""
        sample = merge_review_state(sample)
        sample.to_csv(REVIEW_SAMPLE_FILE, index=False)
        return sample

    alerts = pd.read_csv(ALERT_FILE)
    alerts = merge_review_state(alerts)
    if alerts.empty:
        sample = alerts
    else:
        sampled_parts = []
        per_severity = max(1, sample_size // alerts["severity"].nunique())
        for _, group in alerts.groupby("severity"):
            sampled_parts.append(
                group.sample(
                    n=min(per_severity, len(group)),
                    random_state=random_state,
                )
            )
        sample = pd.concat(sampled_parts).drop_duplicates("row_id")
        remaining = alerts.loc[~alerts["row_id"].isin(sample["row_id"])]
        if len(sample) < sample_size and not remaining.empty:
            sample = pd.concat(
                [
                    sample,
                    remaining.sample(
                        n=min(sample_size - len(sample), len(remaining)),
                        random_state=random_state,
                    ),
                ]
            )
        sample = sample.head(sample_size).copy()
        sample.insert(0, "review_sample_id", range(1, len(sample) + 1))
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    sample.to_csv(REVIEW_SAMPLE_FILE, index=False)
    return sample


def summarize_review(sample: pd.DataFrame | None = None) -> dict:
    if sample is None:
        sample = pd.read_csv(REVIEW_SAMPLE_FILE)
    outcomes = sample["review_outcome"].fillna("").str.strip()
    invalid = sorted(set(outcomes) - VALID_OUTCOMES - {""})
    if invalid:
        raise ValueError(f"Invalid review outcomes: {invalid}")
    confidence = sample.get(
        "review_confidence", pd.Series("", index=sample.index)
    ).fillna("").str.strip()
    invalid_confidence = sorted(set(confidence) - VALID_CONFIDENCE - {""})
    if invalid_confidence:
        raise ValueError(f"Invalid review confidence values: {invalid_confidence}")

    resolved = outcomes.isin(
        {"confirmed_data_issue", "legitimate_exception", "false_positive"}
    )
    actionable = outcomes.isin(
        {"confirmed_data_issue", "legitimate_exception"}
    )
    reviewed = outcomes.ne("")
    minimum_resolved_for_rate = 10
    enough_resolved = int(resolved.sum()) >= minimum_resolved_for_rate
    summary = {
        "sample_size": int(len(sample)),
        "reviewed": int(reviewed.sum()),
        "resolved": int(resolved.sum()),
        "confirmed_data_issues": int((outcomes == "confirmed_data_issue").sum()),
        "legitimate_exceptions": int((outcomes == "legitimate_exception").sum()),
        "false_positives": int((outcomes == "false_positive").sum()),
        "needs_more_information": int((outcomes == "needs_more_information").sum()),
        "actionable_precision": (
            float(actionable.sum() / resolved.sum()) if enough_resolved else None
        ),
        "false_positive_rate": (
            float((outcomes == "false_positive").sum() / resolved.sum())
            if enough_resolved
            else None
        ),
        "minimum_resolved_for_rate": minimum_resolved_for_rate,
        "high_confidence_reviews": int((confidence == "high").sum()),
        "medium_confidence_reviews": int((confidence == "medium").sum()),
        "low_confidence_reviews": int((confidence == "low").sum()),
        "method_note": (
            "Rates remain null until at least 10 cases are resolved. A legitimate "
            "exception counts as actionable because surfacing unusual but valid "
            "activity can still justify analyst review. This portfolio review is "
            "not a substitute for validation by an IDA financial-data specialist."
        ),
    }
    REVIEW_SUMMARY_FILE.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--summarize",
        action="store_true",
        help="Summarize the existing labeled sample without replacing it.",
    )
    parser.add_argument(
        "--regenerate",
        action="store_true",
        help="Replace the deterministic sample; existing labels may be lost.",
    )
    parser.add_argument(
        "--sync-sample",
        action="store_true",
        help="Persist labeled sample rows into the durable review store.",
    )
    args = parser.parse_args()
    sample = create_review_sample(regenerate=args.regenerate)
    if args.sync_sample:
        sync_sample_to_review_store(sample)
    print(json.dumps(summarize_review(sample), indent=2))
