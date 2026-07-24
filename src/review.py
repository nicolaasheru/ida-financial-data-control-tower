from __future__ import annotations

import argparse
import json

import pandas as pd

from .config import ALERT_FILE, ARTIFACT_DIR, REVIEW_SAMPLE_FILE


VALID_OUTCOMES = {
    "confirmed_data_issue",
    "legitimate_exception",
    "false_positive",
    "needs_more_information",
}


def create_review_sample(
    sample_size: int = 30,
    random_state: int = 42,
) -> pd.DataFrame:
    alerts = pd.read_csv(ALERT_FILE)
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

    resolved = outcomes.isin(
        {"confirmed_data_issue", "legitimate_exception", "false_positive"}
    )
    actionable = outcomes.isin(
        {"confirmed_data_issue", "legitimate_exception"}
    )
    reviewed = outcomes.ne("")
    return {
        "sample_size": int(len(sample)),
        "reviewed": int(reviewed.sum()),
        "resolved": int(resolved.sum()),
        "confirmed_data_issues": int((outcomes == "confirmed_data_issue").sum()),
        "legitimate_exceptions": int((outcomes == "legitimate_exception").sum()),
        "false_positives": int((outcomes == "false_positive").sum()),
        "needs_more_information": int((outcomes == "needs_more_information").sum()),
        "actionable_precision": (
            float(actionable.sum() / resolved.sum()) if resolved.any() else None
        ),
        "false_positive_rate": (
            float((outcomes == "false_positive").sum() / resolved.sum())
            if resolved.any()
            else None
        ),
        "method_note": (
            "Rates remain null until a human labels resolved cases. A legitimate "
            "exception counts as actionable because the alert is valid even when "
            "the underlying transaction is not erroneous."
        ),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--summarize",
        action="store_true",
        help="Summarize the existing labeled sample without replacing it.",
    )
    args = parser.parse_args()
    sample = (
        pd.read_csv(REVIEW_SAMPLE_FILE)
        if args.summarize
        else create_review_sample()
    )
    print(json.dumps(summarize_review(sample), indent=2))
