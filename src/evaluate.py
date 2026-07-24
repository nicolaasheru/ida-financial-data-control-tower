from __future__ import annotations

import json

import pandas as pd

from .config import ARTIFACT_DIR
from .detect import detect_isolation_forest, detect_statistical
from .features import engineer_features
from .ingest import load_raw
from .validate import validate_and_clean


EVALUATION_FILE = ARTIFACT_DIR / "evaluation_summary.json"


def inject_controlled_anomalies(source: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """Inject deterministic faults into copies of otherwise valid IDA records."""
    df = source.copy().reset_index(drop=True)
    candidates = df.index[
        df["organization"].eq("IDA")
        & pd.to_numeric(df["total"], errors="coerce").gt(100)
        & pd.to_numeric(df["investment_lending"], errors="coerce").gt(0)
    ].tolist()
    if len(candidates) < 4:
        raise RuntimeError("Not enough eligible records for controlled evaluation.")

    labels: list[dict] = []

    missing_idx = candidates[0]
    df.at[missing_idx, "total"] = None
    labels.append(
        {
            "injection": "missing_amount",
            "row_ids": [int(missing_idx)],
            "expected_codes": ["INVALID_AMOUNT"],
        }
    )

    mismatch_idx = candidates[1]
    df.at[mismatch_idx, "total"] = float(df.at[mismatch_idx, "total"]) + 500.0
    labels.append(
        {
            "injection": "broken_reconciliation",
            "row_ids": [int(mismatch_idx)],
            "expected_codes": ["TOTAL_MISMATCH"],
        }
    )

    negative_idx = candidates[2]
    df.at[negative_idx, "investment_lending"] = -abs(
        float(df.at[negative_idx, "investment_lending"])
    )
    labels.append(
        {
            "injection": "negative_component",
            "row_ids": [int(negative_idx)],
            "expected_codes": ["NEGATIVE_AMOUNT", "TOTAL_MISMATCH"],
        }
    )

    duplicate_idx = candidates[3]
    duplicate = df.loc[[duplicate_idx]].copy()
    duplicate_row_id = len(df)
    df = pd.concat([df, duplicate], ignore_index=True)
    labels.append(
        {
            "injection": "duplicate_grain",
            "row_ids": [int(duplicate_idx), int(duplicate_row_id)],
            "expected_codes": ["DUPLICATE_GRAIN"],
        }
    )
    return df, labels


def evaluate() -> dict:
    source = load_raw(refresh=False)
    injected, labels = inject_controlled_anomalies(source)
    validation = validate_and_clean(injected)
    features = engineer_features(validation.clean)
    statistical = detect_statistical(features)
    ml_alerts, _ = detect_isolation_forest(features)

    frames = [
        frame
        for frame in [validation.alerts, statistical, ml_alerts]
        if not frame.empty
    ]
    alerts = pd.concat(frames, ignore_index=True, sort=False)

    outcomes = []
    for label in labels:
        relevant = alerts.loc[alerts["row_id"].isin(label["row_ids"])]
        observed = sorted(relevant["reason_code"].dropna().unique().tolist())
        expected = label["expected_codes"]
        detected = all(code in observed for code in expected)
        outcomes.append(
            {
                **label,
                "observed_codes": observed,
                "detected": detected,
            }
        )

    summary = {
        "injections": len(outcomes),
        "fully_detected": sum(item["detected"] for item in outcomes),
        "control_recall": (
            sum(item["detected"] for item in outcomes) / len(outcomes)
            if outcomes
            else 0.0
        ),
        "outcomes": outcomes,
        "method_note": (
            "Controlled fault injection evaluates known structural and financial "
            "failure modes; it does not estimate production false-positive rates."
        ),
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    EVALUATION_FILE.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2))
