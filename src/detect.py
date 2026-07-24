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
            }
        )
    return pd.DataFrame(rows)


def detect_isolation_forest(
    features: pd.DataFrame,
    contamination: float = 0.02,
    random_state: int = 42,
) -> tuple[pd.DataFrame, Pipeline]:
    df = features.copy()
    model = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", RobustScaler()),
            (
                "detector",
                IsolationForest(
                    n_estimators=300,
                    contamination=contamination,
                    random_state=random_state,
                ),
            ),
        ]
    )
    matrix = df[MODEL_FEATURES].replace([np.inf, -np.inf], np.nan)
    predictions = model.fit_predict(matrix)
    raw_scores = -model.decision_function(matrix)
    normalized = (raw_scores - raw_scores.min()) / (
        raw_scores.max() - raw_scores.min() + 1e-12
    )

    rows = []
    for idx in df.index[predictions == -1]:
        values = {
            feature: df.at[idx, feature]
            for feature in MODEL_FEATURES
            if pd.notna(df.at[idx, feature])
        }
        largest = sorted(
            values.items(),
            key=lambda item: abs(float(item[1])),
            reverse=True,
        )[:3]
        evidence = "; ".join(f"{name}={value:.3f}" for name, value in largest)
        score = float(normalized[idx])
        rows.append(
            {
                "row_id": int(df.at[idx, "row_id"]),
                "severity": _severity(score),
                "reason_code": "MULTIVARIATE_ANOMALY",
                "detector": "isolation_forest",
                "message": "Record has an unusual financial profile across multiple signals.",
                "evidence": evidence,
                "recommended_action": (
                    "Review component mix, period changes, and supporting source records."
                ),
                "anomaly_score": score,
            }
        )
    return pd.DataFrame(rows), model
