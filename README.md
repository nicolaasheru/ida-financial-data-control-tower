# IDA Financial Data Control Tower

An interpretable anomaly-detection prototype for World Bank IDA commitment and
gross-disbursement data. The system ingests official WBG Finances data, validates
financial controls, engineers time-series and composition features, applies
statistical and machine-learning detectors, and produces analyst-ready alerts.

## MVP question

How can a lightweight control layer detect missing, inconsistent, and unusual
financial records before they propagate into downstream reporting?

## Official source

- Dataset: IDA Commitments and Disbursements — Country / Economy Summary
- WBG Finances dataset ID: `DS01557`
- Resource ID: `RS00964`
- Coverage: FY2014 onward, quarterly
- Unit: USD millions
- License: CC BY 4.0

The analytical pipeline filters the source to IDA records. It does not use or
claim access to internal World Bank systems.

## Controls

1. **Structural:** required fields, data types, valid categories, unique grain.
2. **Financial:** non-negative amounts and component-to-total reconciliation.
3. **Statistical:** robust peer and historical deviations.
4. **Machine learning:** Isolation Forest over interpretable magnitude,
   composition, ratio, and change features.
5. **Explainability:** every alert includes severity, reason codes, evidence,
   and a recommended analyst action.

## Financial calibration

- Annual and quarterly observations are modeled separately.
- Commitments and gross disbursements are modeled separately.
- Country records are separated from regional and institutional aggregates;
  only countries enter the current statistical and ML detectors.
- Disbursement-to-commitment ratios are suppressed when commitments are below
  USD 10 million, because a tiny denominator can create a misleadingly large
  ratio. This is a prototype calibration assumption, not WBG policy.
- ML-only alerts cannot be critical. Severity rises when independent detector
  families agree and the record is financially material.
- The analyst queue displays current, prior-period, and comparable prior-year
  amounts rather than presenting a score without financial context.

## Run

```bash
python -m src.pipeline
```

Outputs are written to `artifacts/` and cleaned data to `data/processed/`.

Key outputs:

- `artifacts/alert_signals.csv`: one row per detector signal.
- `artifacts/alerts.csv`: consolidated analyst queue, one row per source record.
- `artifacts/manual_review_sample.csv`: a stratified review sample.
- `artifacts/run_summary.json`: run-level volumes and severity distribution.

Create the manual-review sample with:

```bash
python -m src.review
```

After entering review outcomes in the CSV, summarize false-positive behavior:

```bash
python -m src.review --summarize
```

## Current validation

The controlled fault-injection harness tests known structural failures. The
manual-review workflow estimates false-positive behavior on untouched alerts.
No accuracy or precision claim is made before a reviewer labels that sample.
