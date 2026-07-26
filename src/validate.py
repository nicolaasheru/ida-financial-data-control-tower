from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

import numpy as np
import pandas as pd

from .config import (
    AMOUNT_COLUMNS,
    COMPONENT_COLUMNS,
    GRAIN_COLUMNS,
    REQUIRED_COLUMNS,
    VALID_CATEGORIES,
)


@dataclass
class ValidationResult:
    clean: pd.DataFrame
    alerts: pd.DataFrame


def stable_record_key(row: pd.Series) -> str:
    """Return a deterministic identifier for the documented financial grain."""
    normalized = [
        str(row.get(column, "")).strip().casefold()
        for column in GRAIN_COLUMNS
    ]
    digest = sha256("\x1f".join(normalized).encode("utf-8")).hexdigest()
    return f"ida_{digest[:20]}"


def _alert(
    row_id: int | str,
    record_key: str,
    severity: str,
    reason_code: str,
    message: str,
    evidence: str,
    recommended_action: str,
    detector: str = "rule",
) -> dict:
    return {
        "row_id": row_id,
        "record_key": record_key,
        "severity": severity,
        "reason_code": reason_code,
        "detector": detector,
        "message": message,
        "evidence": evidence,
        "recommended_action": recommended_action,
    }


def validate_and_clean(source: pd.DataFrame) -> ValidationResult:
    df = source.copy()
    alerts: list[dict] = []

    missing_columns = sorted(set(REQUIRED_COLUMNS) - set(df.columns))
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    df = df[REQUIRED_COLUMNS].copy()
    df.insert(0, "row_id", np.arange(len(df)))

    key_columns = ["category", "country", "organization", "region", "time_period"]
    for column in key_columns:
        df[column] = df[column].astype("string").str.strip()
    df.insert(1, "record_key", df.apply(stable_record_key, axis=1))

    for column in AMOUNT_COLUMNS:
        original = df[column]
        df[column] = pd.to_numeric(original, errors="coerce")
        invalid = df[column].isna()
        for row in df.loc[
            invalid, ["row_id", "record_key"]
        ].itertuples(index=False):
            alerts.append(
                _alert(
                    row.row_id,
                    row.record_key,
                    "critical",
                    "INVALID_AMOUNT",
                    f"{column} is missing or non-numeric.",
                    f"field={column}",
                    "Confirm the source value and reload the affected record.",
                )
            )

    for column in key_columns:
        missing = df[column].isna() | df[column].eq("")
        for row in df.loc[
            missing, ["row_id", "record_key"]
        ].itertuples(index=False):
            alerts.append(
                _alert(
                    row.row_id,
                    row.record_key,
                    "critical",
                    "MISSING_KEY",
                    f"Required key field {column} is blank.",
                    f"field={column}",
                    "Recover the key from the source system before downstream use.",
                )
            )

    invalid_category = ~df["category"].isin(VALID_CATEGORIES)
    for row in df.loc[
        invalid_category, ["row_id", "record_key", "category"]
    ].itertuples(index=False):
        alerts.append(
            _alert(
                row.row_id,
                row.record_key,
                "high",
                "INVALID_CATEGORY",
                "Financial category is outside the controlled vocabulary.",
                f"category={row.category}",
                "Map the value to Commitments or Gross Disbursements.",
            )
        )

    duplicate_mask = df.duplicated(GRAIN_COLUMNS, keep=False)
    for row in df.loc[
        duplicate_mask, ["row_id", "record_key", *GRAIN_COLUMNS]
    ].itertuples(index=False):
        evidence = ", ".join(
            f"{column}={getattr(row, column)}" for column in GRAIN_COLUMNS
        )
        alerts.append(
            _alert(
                row.row_id,
                row.record_key,
                "critical",
                "DUPLICATE_GRAIN",
                "Multiple records share the expected reporting grain.",
                evidence,
                "Reconcile duplicate records before aggregation or reporting.",
            )
        )

    for column in AMOUNT_COLUMNS:
        negative = df[column] < 0
        for row in df.loc[
            negative, ["row_id", "record_key", column]
        ].itertuples(index=False):
            alerts.append(
                _alert(
                    row.row_id,
                    row.record_key,
                    "medium",
                    "NEGATIVE_AMOUNT",
                    f"{column} is negative and may represent a correction or reversal.",
                    f"{column}={getattr(row, column):,.2f}",
                    "Confirm the adjustment against source documentation before reporting.",
                )
            )

    component_sum = df[COMPONENT_COLUMNS].sum(axis=1, min_count=1)
    difference = (df["total"] - component_sum).abs()
    # Historical annual values are rounded to USD millions. A one-million
    # difference can therefore be present without indicating a broken control.
    tolerance = np.maximum(1.01, df["total"].abs() * 0.001)
    mismatch = difference > tolerance
    for idx in df.index[mismatch]:
        alerts.append(
            _alert(
                df.at[idx, "row_id"],
                df.at[idx, "record_key"],
                "critical",
                "TOTAL_MISMATCH",
                "Reported total does not reconcile to financing components.",
                (
                    f"reported={df.at[idx, 'total']:,.2f}; "
                    f"components={component_sum.at[idx]:,.2f}; "
                    f"difference={difference.at[idx]:,.2f}"
                ),
                "Recalculate the total or trace the missing financing component.",
            )
        )

    quarterly = df["time_period"].str.extract(
        r"^(?P<fiscal_year>\d{4})-Q(?P<quarter>[1-4])$"
    )
    annual = df["time_period"].str.extract(r"^FY(?P<short_year>\d{2})$")
    period_parts = quarterly.copy()
    annual_mask = annual["short_year"].notna()
    period_parts.loc[annual_mask, "fiscal_year"] = (
        2000 + pd.to_numeric(annual.loc[annual_mask, "short_year"])
    ).astype("string")
    period_parts.loc[annual_mask, "quarter"] = "4"
    invalid_period = period_parts.isna().any(axis=1)
    for row in df.loc[
        invalid_period, ["row_id", "record_key", "time_period"]
    ].itertuples(index=False):
        alerts.append(
            _alert(
                row.row_id,
                row.record_key,
                "high",
                "INVALID_PERIOD",
                "Time period does not follow YYYY-Qn.",
                f"time_period={row.time_period}",
                "Correct the fiscal period before time-series analysis.",
            )
        )

    df["fiscal_year"] = pd.to_numeric(period_parts["fiscal_year"], errors="coerce")
    df["quarter"] = pd.to_numeric(period_parts["quarter"], errors="coerce")
    df["period_type"] = annual_mask.map({True: "annual", False: "quarterly"})
    df["component_sum"] = component_sum
    df["reconciliation_difference"] = df["total"] - component_sum

    ida = df.loc[df["organization"].eq("IDA")].reset_index(drop=True)
    return ValidationResult(clean=ida, alerts=pd.DataFrame(alerts))
