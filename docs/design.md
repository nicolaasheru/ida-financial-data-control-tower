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
