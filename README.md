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

## Run

```bash
python -m src.pipeline
```

Outputs are written to `artifacts/` and cleaned data to `data/processed/`.

## Status

Foundation build. Dashboard and cloud-oriented orchestration follow after the
control pipeline and evaluation harness are stable.
