from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler

from .config import COMPONENT_COLUMNS


MODEL_FEATURES = [
    "log1p_total",
    *[f"{column}_share" for column in COMPONENT_COLUMNS],
    "relative_change",
    "year_over_year_change",
    "disbursement_commitment_ratio",
    "quarter",
]
ISOLATION_FOREST_CONTAMINATION = 0.01
ISOLATION_FOREST_ESTIMATORS = 300
ISOLATION_FOREST_RANDOM_STATE = 42


def _severity(score: float) -> str:
    if score >= 0.80:
        return "critical"
    if score >= 0.60:
        return "high"
    return "medium"


def detect_statistical(features: pd.DataFrame) -> pd.DataFrame:
    df = features.copy()
    absolute_yoy_change = (df["total"] - df["previous_year_total"]).abs()
    flagged = (
        df["entity_type"].eq("country")
        &
        df["previous_year_total"].abs().ge(20)
        & absolute_yoy_change.ge(100)
        & df["year_over_year_change"].abs().ge(2.5)
    )

    rows = []
    for idx in df.index[flagged]:
        relative = abs(float(df.at[idx, "year_over_year_change"]))
        score = min(relative / 8.0, 1.0)
        rows.append(
            {
                "row_id": int(df.at[idx, "row_id"]),
                "record_key": str(df.at[idx, "record_key"]),
                "severity": "high" if score >= 0.75 else "medium",
                "reason_code": "YEAR_OVER_YEAR_SHIFT",
                "detector": "statistical_process_control",
                "message": "Total changed materially from the comparable prior-year period.",
                "evidence": (
                    f"total={df.at[idx, 'total']:,.2f}; "
                    f"prior_year={df.at[idx, 'previous_year_total']:,.2f}; "
                    f"change={df.at[idx, 'year_over_year_change']:.1%}"
                ),
                "recommended_action": (
                    "Confirm whether the shift reflects approved financing activity or a data issue."
                ),
                "anomaly_score": score,
                "model_segment": (
                    f"{df.at[idx, 'period_type']}|{df.at[idx, 'category']}|"
                    f"{df.at[idx, 'entity_type']}"
                ),
            }
        )
    return pd.DataFrame(rows)


def detect_isolation_forest(
    features: pd.DataFrame,
    contamination: float = ISOLATION_FOREST_CONTAMINATION,
    random_state: int = ISOLATION_FOREST_RANDOM_STATE,
) -> tuple[pd.DataFrame, dict[str, Pipeline]]:
    country_records = features.loc[features["entity_type"].eq("country")].copy()
    segment_columns = ["period_type", "category"]
    rows = []
    models: dict[str, Pipeline] = {}

    for segment_values, segment in country_records.groupby(
        segment_columns,
        dropna=False,
    ):
        period_type, category = segment_values
        segment_name = f"{period_type}|{category}|country"
        if len(segment) < 30:
            continue

        model = Pipeline(
            steps=[
                ("imputer", SimpleImputer(strategy="median")),
                ("scaler", RobustScaler()),
                (
                    "detector",
                    IsolationForest(
                        n_estimators=ISOLATION_FOREST_ESTIMATORS,
                        contamination=contamination,
                        random_state=random_state,
                    ),
                ),
            ]
        )
        matrix = segment[MODEL_FEATURES].replace([np.inf, -np.inf], np.nan)
        predictions = model.fit_predict(matrix)
        raw_scores = -model.decision_function(matrix)
        normalized = (raw_scores - raw_scores.min()) / (
            raw_scores.max() - raw_scores.min() + 1e-12
        )
        transformed = model[:-1].transform(matrix)
        models[segment_name] = model

        flagged_positions = np.flatnonzero(predictions == -1)
        for position in flagged_positions:
            idx = segment.index[position]
            normalized_deviations = {
                feature: abs(float(transformed[position, feature_position]))
                for feature_position, feature in enumerate(MODEL_FEATURES)
            }
            largest = sorted(
                normalized_deviations.items(),
                key=lambda item: item[1],
                reverse=True,
            )[:3]
            evidence = "; ".join(
                f"{name} normalized_deviation={value:.2f}"
                for name, value in largest
            )
            score = float(normalized[position])
            materiality = float(segment.at[idx, "materiality_percentile"])
            provisional_severity = (
                "high" if score >= 0.85 and materiality >= 0.75 else "medium"
            )
            rows.append(
                {
                    "row_id": int(segment.at[idx, "row_id"]),
                    "record_key": str(segment.at[idx, "record_key"]),
                    "severity": provisional_severity,
                    "reason_code": "MULTIVARIATE_ANOMALY",
                    "detector": "isolation_forest",
                    "message": (
                        "Record has an unusual financial profile within its "
                        "period-and-category peer segment."
                    ),
                    "evidence": evidence,
                    "recommended_action": (
                        "Review current versus prior values, financing mix, and "
                        "supporting source records."
                    ),
                    "anomaly_score": score,
                    "model_segment": segment_name,
                }
            )
    return pd.DataFrame(rows), models
