# MVP design

## Expected reporting grain

One row per:

`organization × country × category × fiscal quarter`

where category is either `Commitments` or `Gross Disbursements`.

## Failure modes

| Failure mode | Control | Analyst value |
|---|---|---|
| Missing key or amount | Schema validation | Stops unusable records |
| Duplicate reporting grain | Uniqueness rule | Prevents double counting |
| Negative amount | Domain rule | Separates corrections from errors |
| Components do not equal total | Reconciliation | Protects report integrity |
| Abnormal peer magnitude | Robust statistics | Finds unusual country-quarter values |
| Unusual multivariate profile | Isolation Forest | Detects interactions missed by rules |
| Extreme change from history | Engineered change features | Surfaces temporal breaks |

## Model choice

Isolation Forest is intentionally lightweight and suitable for mostly unlabeled
data. It is not treated as an autonomous decision-maker. Rules retain precedence,
and every model alert is routed to human review.

Four independent Isolation Forest models are fit:

1. annual commitments;
2. annual gross disbursements;
3. quarterly commitments; and
4. quarterly gross disbursements.

This prevents different reporting cadences and financial meanings from competing
inside one anomaly distribution. Regional and institutional aggregate rows are
retained for rule-based reconciliation but excluded from the country ML models.
Aggregate reconciliation signals are kept visible but downgraded from critical
until their reporting semantics are confirmed; they must not outrank corroborated
country-level alerts merely because aggregate components follow a different
presentation.
The initial contamination assumption remains 2% within each segment and must be
recalibrated from manual-review evidence.

## Financial interpretation

The ratio is:

`gross disbursements / absolute commitments`

It is only calculated when commitments are at least USD 10 million. The threshold
is a stability floor for the denominator, not a statement that smaller operations
are unimportant.

Materiality percentiles compare a record only with peers in the same period type,
category, and entity type. Dollar bands are prioritization aids and are not WBG
policy thresholds.

The ML evidence lists the largest normalized feature deviations. These values help
an analyst orient the review, but they are not causal feature contributions.

## Severity and corroboration

- A standalone ML signal is medium, or high only when both its anomaly score and
  materiality percentile are elevated. It is never critical by itself.
- Agreement by at least two detector families elevates a medium case to high.
- A high case becomes critical only when detector families agree and materiality
  is in the top quartile.
- Deterministic critical controls, such as failed reconciliation or duplicate
  reporting grain, remain critical.

Detector signals are preserved separately from the consolidated analyst queue so
the evidence trail remains auditable.

## Evaluation plan

Because the public source has no anomaly labels, evaluation will use:

1. controlled injection of missing values, duplicates, broken totals, and spikes;
2. detector recall by anomaly type;
3. alert volume and false-positive review on untouched records;
4. stability across time-based train/test windows;
5. analyst-oriented explanations and reason codes.

## Production-oriented handoff

The pipeline separates ingestion, validation, feature engineering, detection,
and alert generation. This supports later orchestration in Azure Data Factory or
Databricks and model registration/monitoring in Azure Machine Learning.
