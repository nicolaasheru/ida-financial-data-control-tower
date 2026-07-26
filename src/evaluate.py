from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Sequence

import numpy as np
import pandas as pd

from .config import ARTIFACT_DIR, COMPONENT_COLUMNS
from .detect import detect_isolation_forest, detect_statistical
from .features import engineer_features
from .ingest import load_raw
from .validate import validate_and_clean


EVALUATION_FILE = ARTIFACT_DIR / "evaluation_summary.json"
DEFAULT_EVALUATION_SEEDS = (11, 23, 42, 73, 101)

LAYER_BY_CODE = {
    "INVALID_AMOUNT": "structural_or_financial_rule",
    "TOTAL_MISMATCH": "structural_or_financial_rule",
    "NEGATIVE_AMOUNT": "structural_or_financial_rule",
    "DUPLICATE_GRAIN": "structural_or_financial_rule",
    "YEAR_OVER_YEAR_SHIFT": "statistical",
    "MULTIVARIATE_ANOMALY": "machine_learning",
}


def inject_controlled_anomalies(
    source: pd.DataFrame,
    *,
    random_state: int = 42,
) -> tuple[pd.DataFrame, list[dict]]:
    """Inject the same failure modes into varied, reproducibly selected records."""
    df = source.copy().reset_index(drop=True)
    rng = np.random.default_rng(random_state)
    numeric_total = pd.to_numeric(df["total"], errors="coerce")
    numeric_investment = pd.to_numeric(
        df["investment_lending"], errors="coerce"
    )
    structural_candidates = df.index[
        df["organization"].eq("IDA")
        & numeric_total.gt(100)
        & numeric_investment.gt(0)
    ].to_numpy()
    if len(structural_candidates) < 4:
        raise RuntimeError("Not enough eligible records for controlled evaluation.")
    selected = rng.choice(structural_candidates, size=4, replace=False)

    labels: list[dict] = []

    missing_idx = int(selected[0])
    df.at[missing_idx, "total"] = None
    labels.append(
        {
            "injection": "missing_amount",
            "row_ids": [missing_idx],
            "expected_codes": ["INVALID_AMOUNT"],
        }
    )

    mismatch_idx = int(selected[1])
    df.at[mismatch_idx, "total"] = float(df.at[mismatch_idx, "total"]) + 500.0
    labels.append(
        {
            "injection": "broken_reconciliation",
            "row_ids": [mismatch_idx],
            "expected_codes": ["TOTAL_MISMATCH"],
        }
    )

    negative_idx = int(selected[2])
    df.at[negative_idx, "investment_lending"] = -abs(
        float(df.at[negative_idx, "investment_lending"])
    )
    labels.append(
        {
            "injection": "negative_component",
            "row_ids": [negative_idx],
            "expected_codes": ["NEGATIVE_AMOUNT", "TOTAL_MISMATCH"],
        }
    )

    duplicate_idx = int(selected[3])
    duplicate = df.loc[[duplicate_idx]].copy()
    duplicate_row_id = len(df)
    df = pd.concat([df, duplicate], ignore_index=True)
    labels.append(
        {
            "injection": "duplicate_grain",
            "row_ids": [duplicate_idx, int(duplicate_row_id)],
            "expected_codes": ["DUPLICATE_GRAIN"],
        }
    )

    baseline_features = engineer_features(validate_and_clean(source).clean)
    spike_candidates = baseline_features.index[
        baseline_features["entity_type"].eq("country")
        & baseline_features["period_type"].eq("annual")
        & baseline_features["previous_year_total"].abs().ge(20)
        & baseline_features["total"].abs().ge(20)
        & ~baseline_features["row_id"].isin(selected)
    ].to_numpy()
    if not len(spike_candidates):
        raise RuntimeError("No eligible historical spike targets are available.")
    spike_feature_index = int(rng.choice(spike_candidates))
    spike_idx = int(baseline_features.at[spike_feature_index, "row_id"])
    for column in [*COMPONENT_COLUMNS, "total"]:
        df.at[spike_idx, column] = float(df.at[spike_idx, column]) * 50.0
    labels.append(
        {
            "injection": "reconciled_historical_spike",
            "row_ids": [spike_idx],
            "expected_codes": [
                "YEAR_OVER_YEAR_SHIFT",
                "MULTIVARIATE_ANOMALY",
            ],
        }
    )
    return df, labels


def evaluate_seed(source: pd.DataFrame, seed: int) -> list[dict]:
    injected, labels = inject_controlled_anomalies(
        source,
        random_state=seed,
    )
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
        outcomes.append(
            {
                "seed": seed,
                **label,
                "observed_codes": observed,
                "detected": all(code in observed for code in expected),
            }
        )
    return outcomes


def evaluate(seeds: Sequence[int] = DEFAULT_EVALUATION_SEEDS) -> dict:
    if not seeds:
        raise ValueError("At least one evaluation seed is required.")
    source = load_raw(refresh=False)
    all_outcomes = [
        outcome
        for seed in seeds
        for outcome in evaluate_seed(source, int(seed))
    ]

    layer_results: dict[str, list[bool]] = defaultdict(list)
    scenario_results: dict[str, list[bool]] = defaultdict(list)
    seed_results: dict[int, list[bool]] = defaultdict(list)
    for outcome in all_outcomes:
        scenario_results[outcome["injection"]].append(outcome["detected"])
        seed_results[outcome["seed"]].append(outcome["detected"])
        for code in outcome["expected_codes"]:
            layer_results[LAYER_BY_CODE[code]].append(
                code in outcome["observed_codes"]
            )

    scenario_recall = {
        scenario: sum(results) / len(results)
        for scenario, results in scenario_results.items()
    }
    seed_recall = {
        str(seed): sum(results) / len(results)
        for seed, results in seed_results.items()
    }
    detected_trials = sum(item["detected"] for item in all_outcomes)
    summary = {
        "injections": len(scenario_results),
        "fully_detected": sum(
            recall == 1.0 for recall in scenario_recall.values()
        ),
        "seed_runs": len(seeds),
        "seeds": [int(seed) for seed in seeds],
        "trials": len(all_outcomes),
        "detected_trials": detected_trials,
        "control_recall": detected_trials / len(all_outcomes),
        "minimum_seed_recall": min(seed_recall.values()),
        "recall_by_seed": seed_recall,
        "recall_by_scenario": scenario_recall,
        "recall_by_layer": {
            layer: sum(results) / len(results)
            for layer, results in layer_results.items()
        },
        "outcomes": all_outcomes,
        "method_note": (
            f"Controlled fault injection evaluated {len(scenario_results)} "
            f"failure modes across {len(seeds)} reproducible target selections. "
            "It verifies selected control behavior and target robustness; it "
            "does not estimate production accuracy or false-positive rates."
        ),
    }
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    EVALUATION_FILE.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2))
