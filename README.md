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
- Coverage: FY2014 onward, with annual history and recent quarterly observations
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
- `artifacts/reviews.csv`: durable review decisions preserved across pipeline runs.
- `artifacts/review_summary.json`: review coverage and caveated rate estimates.
- `artifacts/run_summary.json`: run-level volumes and severity distribution.

## Analyst dashboard

Phase 1 adds a functional dashboard in `dashboard/`. It reads the actual pipeline
artifacts and supports:

- portfolio-level monitoring and severity summaries;
- a searchable, filterable, and sortable analyst alert queue;
- current-versus-prior financial comparisons;
- detector evidence, corroboration, and recommended actions;
- public-evidence review context; and
- model, evaluation, and review-quality monitoring.

After running the Python pipeline, synchronize its latest outputs:

```bash
bash scripts/sync-dashboard-data.sh
```

Run the dashboard locally:

```bash
cd dashboard
npm ci
npm run dev
```

The dashboard is an investigation interface. It does not autonomously classify
alerts as errors or replace review by an IDA financial-data specialist.

Create the manual-review sample with:

```bash
python -m src.review
```

After entering review outcomes in the sample, persist them and summarize review
behavior:

```bash
python -m src.review --sync-sample --summarize
```

## Current validation

The controlled fault-injection harness tests five scenarios: missing amount,
broken reconciliation, negative component, duplicate grain, and an internally
reconciled historical spike. The spike must exercise both the statistical and ML
layers. Detection of these selected injections does not imply 100% real-world
accuracy.

The manual-review workflow estimates false-positive behavior on untouched alerts.
Rates remain suppressed until at least ten cases are resolved. The initial
critical-alert review is AI-assisted and based on public evidence; it is not a
substitute for validation by an IDA financial-data specialist.

## Independent-project disclaimer

This is an independent portfolio prototype using publicly available World Bank
data. It is not an official World Bank Group system and does not use internal WBG
infrastructure or non-public financial records.
