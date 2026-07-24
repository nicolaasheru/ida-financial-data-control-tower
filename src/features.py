from __future__ import annotations

import numpy as np
import pandas as pd

from .config import (
    AGGREGATE_ENTITIES,
    COMPONENT_COLUMNS,
    MIN_RATIO_DENOMINATOR_USD_M,
)


def engineer_features(clean: pd.DataFrame) -> pd.DataFrame:
    df = clean.copy()
    df["entity_type"] = np.where(
        df["country"].isin(AGGREGATE_ENTITIES),
        "aggregate_or_institution",
        "country",
    )
    total_safe = df["total"].where(df["total"].abs() > 1e-9)

    for column in COMPONENT_COLUMNS:
        df[f"{column}_share"] = (df[column] / total_safe).fillna(0.0)
        df[f"log1p_{column}"] = np.log1p(df[column].clip(lower=0))
    df["log1p_total"] = np.log1p(df["total"].clip(lower=0))

    df = df.sort_values(
        ["country", "category", "period_type", "fiscal_year", "quarter"]
    ).reset_index(drop=True)
    group = df.groupby(
        ["country", "category", "period_type"],
        dropna=False,
    )

    df["previous_total"] = group["total"].shift(1)
    df["absolute_change"] = df["total"] - df["previous_total"]
    df["relative_change"] = (
        df["absolute_change"] / df["previous_total"].abs().replace(0, np.nan)
    ).replace([np.inf, -np.inf], np.nan)

    same_quarter_group = df.groupby(
        ["country", "category", "period_type", "quarter"], dropna=False
    )
    df["previous_year_total"] = same_quarter_group["total"].shift(1)
    df["year_over_year_change"] = (
        (df["total"] - df["previous_year_total"])
        / df["previous_year_total"].abs().replace(0, np.nan)
    ).replace([np.inf, -np.inf], np.nan)

    commitment = df.loc[
        df["category"].eq("Commitments"),
        ["country", "time_period", "total"],
    ].rename(columns={"total": "commitment_total"})
    disbursement = df.loc[
        df["category"].eq("Gross Disbursements"),
        ["country", "time_period", "total"],
    ].rename(columns={"total": "disbursement_total"})
    ratios = commitment.merge(disbursement, on=["country", "time_period"], how="outer")
    ratios["ratio_denominator_eligible"] = (
        ratios["commitment_total"].abs() >= MIN_RATIO_DENOMINATOR_USD_M
    )
    ratios["disbursement_commitment_ratio"] = np.where(
        ratios["ratio_denominator_eligible"],
        ratios["disbursement_total"] / ratios["commitment_total"].abs(),
        np.nan,
    )
    df = df.merge(
        ratios[
            [
                "country",
                "time_period",
                "commitment_total",
                "disbursement_total",
                "ratio_denominator_eligible",
                "disbursement_commitment_ratio",
            ]
        ],
        on=["country", "time_period"],
        how="left",
    )

    segment_keys = ["period_type", "category", "entity_type"]
    df["materiality_percentile"] = df.groupby(segment_keys)["total"].rank(
        method="average",
        pct=True,
    )
    df["absolute_total"] = df["total"].abs()
    df["materiality_band"] = pd.cut(
        df["absolute_total"],
        bins=[-np.inf, 10, 100, 500, np.inf],
        labels=["limited", "moderate", "significant", "major"],
    ).astype("string")
    return df
