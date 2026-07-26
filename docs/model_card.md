# Model card — segmented Isolation Forest

## Intended use

The model prioritizes unusual country-level IDA commitment and gross
disbursement records for analyst review. It is one control family within a
hybrid system and does not classify records as errors.

## Configuration

- Algorithm: Isolation Forest
- Segments: annual commitments, annual gross disbursements, quarterly
  commitments, and quarterly gross disbursements
- Population: country records only
- Estimators: 300
- Contamination: 2% starting assumption, pending expert-review calibration
- Random state: 42
- Preprocessing: median imputation and robust scaling
- Score scope: batch-relative within each segment

## Features

The model uses log total, financing-component shares, relative and year-over-year
change, the denominator-controlled disbursement-to-commitment ratio, and fiscal
quarter. Exact feature names are recorded in every `run_summary.json`.

## Decision policy

An Isolation Forest signal cannot receive critical severity by itself.
Critical priority requires either a deterministic critical rule or corroboration
from multiple detector families combined with sufficient financial materiality.

## Evaluation

Controlled fault injection checks selected failure modes and deterministic
reproducibility. It does not estimate production accuracy. False-positive and
actionable-rate estimates remain suppressed until at least ten sampled cases
have final review outcomes.

## Limitations

- The model is refit in batch mode; normalized scores are not comparable across
  separate runs without run context.
- The contamination rate is not yet expert-calibrated.
- Public data does not include internal forecasting, approval, lineage, or
  downstream-reporting metadata.
- No causal explanation or automatic error confirmation is produced.
- Production monitoring, drift thresholds, and registry controls remain target
  architecture rather than implemented infrastructure.
