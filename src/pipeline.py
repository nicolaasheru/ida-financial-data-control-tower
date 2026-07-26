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
    SIGNAL_FILE,
)
from .detect import (
    ISOLATION_FOREST_CONTAMINATION,
    ISOLATION_FOREST_ESTIMATORS,
    ISOLATION_FOREST_RANDOM_STATE,
    MODEL_FEATURES,
    detect_isolation_forest,
    detect_statistical,
)
from .features import engineer_features
from .ingest import load_raw
from .review import merge_review_state
from .validate import validate_and_clean


CONTEXT_COLUMNS = [
    "row_id",
    "record_key",
    "country",
    "region",
    "entity_type",
    "category",
    "period_type",
    "time_period",
    "total",
    "previous_total",
    "previous_year_total",
    "absolute_change",
    "relative_change",
    "year_over_year_change",
    "commitment_total",
    "disbursement_total",
    "ratio_denominator_eligible",
    "disbursement_commitment_ratio",
    "materiality_percentile",
    "materiality_band",
]

SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _add_context(signals: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    if signals.empty:
        return signals
    context = features[
        CONTEXT_COLUMNS
    ].drop_duplicates(["row_id", "record_key"])
    enriched = signals.merge(context, on=["row_id", "record_key"], how="inner")
    enriched["current_amount_usd_m"] = enriched["total"]
    enriched["comparison_amount_usd_m"] = enriched["previous_year_total"]
    enriched["change_amount_usd_m"] = (
        enriched["current_amount_usd_m"] - enriched["comparison_amount_usd_m"]
    )
    enriched["change_percent"] = enriched["year_over_year_change"]
    aggregate_reconciliation = (
        enriched["entity_type"].eq("aggregate_or_institution")
        & enriched["reason_code"].eq("TOTAL_MISMATCH")
    )
    enriched.loc[aggregate_reconciliation, "severity"] = "medium"
    enriched.loc[aggregate_reconciliation, "message"] = (
        "Aggregate total does not reconcile to country-style financing components; "
        "the aggregate reporting semantics may differ."
    )
    enriched.loc[aggregate_reconciliation, "recommended_action"] = (
        "Confirm the aggregate definition before treating this as a data-quality error."
    )
    return enriched


def _join_unique(series: pd.Series) -> str:
    return " | ".join(dict.fromkeys(str(value) for value in series.dropna()))


def _column(group: pd.DataFrame, name: str) -> pd.Series:
    return group[name] if name in group else pd.Series(dtype="object")


def _final_severity(group: pd.DataFrame) -> str:
    base_rank = max(
        (SEVERITY_RANK.get(value, 1) for value in group["severity"]),
        default=1,
    )
    detectors = group["detector"].dropna().nunique()
    materiality = group["materiality_percentile"].max()
    has_critical_rule = bool(
        (
            group["detector"].eq("rule")
            & group["severity"].eq("critical")
        ).any()
    )

    if has_critical_rule:
        return "critical"
    if detectors >= 2:
        if base_rank >= SEVERITY_RANK["high"] and materiality >= 0.75:
            return "critical"
        return "high"
    return next(
        severity
        for severity, rank in SEVERITY_RANK.items()
        if rank == base_rank
    )


def build_analyst_queue(signals: pd.DataFrame) -> pd.DataFrame:
    if signals.empty:
        return signals

    records = []
    for record_key, group in signals.groupby("record_key", sort=False):
        first = group.iloc[0]
        record = {
            column: first.get(column)
            for column in CONTEXT_COLUMNS
            if column not in {"row_id", "record_key"}
        }
        record.update(
            {
                "row_id": int(first.get("row_id")),
                "record_key": str(record_key),
                "severity": _final_severity(group),
                "reason_codes": _join_unique(group["reason_code"]),
                "detectors": _join_unique(group["detector"]),
                "signal_count": int(len(group)),
                "detector_count": int(group["detector"].dropna().nunique()),
                "corroborated": bool(group["detector"].dropna().nunique() >= 2),
                "anomaly_score": group["anomaly_score"].max(),
                "model_segments": _join_unique(_column(group, "model_segment")),
                "messages": _join_unique(_column(group, "message")),
                "evidence": _join_unique(_column(group, "evidence")),
                "recommended_actions": _join_unique(
                    _column(group, "recommended_action")
                ),
                "current_amount_usd_m": first.get("current_amount_usd_m"),
                "comparison_amount_usd_m": first.get("comparison_amount_usd_m"),
                "change_amount_usd_m": first.get("change_amount_usd_m"),
                "change_percent": first.get("change_percent"),
                "review_status": "pending",
                "review_outcome": "",
                "reviewer": "",
                "review_notes": "",
                "reviewed_at": "",
                "review_confidence": "",
                "evidence_url": "",
            }
        )
        records.append(record)

    queue = pd.DataFrame(records)
    queue["_rank"] = queue["severity"].map(SEVERITY_RANK).fillna(0)
    return queue.sort_values(
        ["_rank", "corroborated", "anomaly_score"],
        ascending=[False, False, False],
        na_position="last",
    ).drop(columns="_rank")


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
    signals = pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()
    signals = _add_context(signals, features)
    alerts = build_analyst_queue(signals)
    alerts = merge_review_state(alerts)

    validation.clean.to_csv(CLEAN_FILE, index=False)
    features.to_csv(FEATURE_FILE, index=False)
    signals.to_csv(SIGNAL_FILE, index=False)
    alerts.to_csv(ALERT_FILE, index=False)

    summary = {
        "run_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source_records": int(len(source)),
        "ida_records": int(len(validation.clean)),
        "countries": int(validation.clean["country"].nunique()),
        "periods": int(validation.clean["time_period"].nunique()),
        "detector_signals": int(len(signals)),
        "alerts": int(len(alerts)),
        "corroborated_alerts": (
            int(alerts["corroborated"].sum()) if not alerts.empty else 0
        ),
        "reviewed_alerts": (
            int(alerts["review_outcome"].fillna("").astype(str).str.strip().ne("").sum())
            if not alerts.empty
            else 0
        ),
        "resolved_alerts": (
            int(alerts["review_status"].fillna("").eq("resolved").sum())
            if not alerts.empty
            else 0
        ),
        "alerts_by_severity": (
            alerts["severity"].value_counts().to_dict() if not alerts.empty else {}
        ),
        "alerts_by_detector": (
            signals["detector"].value_counts().to_dict() if not signals.empty else {}
        ),
        "model_run": {
            "algorithm": "IsolationForest",
            "segments": "period_type × category; country records only",
            "features": MODEL_FEATURES,
            "n_estimators": ISOLATION_FOREST_ESTIMATORS,
            "contamination": ISOLATION_FOREST_CONTAMINATION,
            "random_state": ISOLATION_FOREST_RANDOM_STATE,
            "score_scope": "batch-relative within each segment",
        },
    }
    RUN_SUMMARY_FILE.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(run(refresh=True), indent=2))
