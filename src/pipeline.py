from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd

from .config import (
    ALERT_FILE,
    ARTIFACT_DIR,
    CLEAN_FILE,
    FEATURE_FILE,
    PROCESSED_DIR,
    RUN_SUMMARY_FILE,
)
from .detect import detect_isolation_forest, detect_statistical
from .features import engineer_features
from .ingest import load_raw
from .validate import validate_and_clean


def _add_context(alerts: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    if alerts.empty:
        return alerts
    context = features[
        [
            "row_id",
            "country",
            "region",
            "category",
            "time_period",
            "total",
        ]
    ].drop_duplicates("row_id")
    return alerts.merge(context, on="row_id", how="left")


def run(refresh: bool = False) -> dict:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    source = load_raw(refresh=refresh)
    validation = validate_and_clean(source)
    features = engineer_features(validation.clean)
    statistical = detect_statistical(features)
    machine_learning, _ = detect_isolation_forest(features)

    frames = [
        frame
        for frame in [validation.alerts, statistical, machine_learning]
        if not frame.empty
    ]
    alerts = pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()
    alerts = _add_context(alerts, features)
    if not alerts.empty:
        rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        alerts["_rank"] = alerts["severity"].map(rank).fillna(9)
        alerts = alerts.sort_values(
            ["_rank", "anomaly_score"], ascending=[True, False], na_position="last"
        ).drop(columns="_rank")

    validation.clean.to_csv(CLEAN_FILE, index=False)
    features.to_csv(FEATURE_FILE, index=False)
    alerts.to_csv(ALERT_FILE, index=False)

    summary = {
        "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source_records": int(len(source)),
        "ida_records": int(len(validation.clean)),
        "countries": int(validation.clean["country"].nunique()),
        "periods": int(validation.clean["time_period"].nunique()),
        "alerts": int(len(alerts)),
        "alerts_by_severity": (
            alerts["severity"].value_counts().to_dict() if not alerts.empty else {}
        ),
        "alerts_by_detector": (
            alerts["detector"].value_counts().to_dict() if not alerts.empty else {}
        ),
    }
    RUN_SUMMARY_FILE.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(run(refresh=True), indent=2))
