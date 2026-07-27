# Model card: IDA Financial Data Control Tower

> **Model status:** portfolio prototype; not approved for production use  
> **Card version:** 1.0  
> **Last updated:** 2026-07-27  
> **Owner:** Nicolaas Heru Dreandachrista  
> **Repository scope:** public World Bank Group data only

## 1. Model overview

The IDA Financial Data Control Tower uses segmented Isolation Forest models to
prioritize financially unusual commitment and gross-disbursement records for
human review. Machine-learning signals operate alongside deterministic
structural and financial rules and a transparent year-over-year statistical
control.

The system is an **analyst decision-support tool**, not an automated
classification system. An anomaly means that a record is unusual relative to
its peer segment; it does not mean the record is erroneous, fraudulent, or
improper.

| Attribute | Implementation |
|---|---|
| Model family | Isolation Forest |
| Learning approach | Unsupervised anomaly detection |
| Library | scikit-learn |
| Estimators | 300 trees per segment |
| Expected anomaly share | `contamination=0.02` |
| Random state | 42 |
| Preprocessing | Median imputation followed by robust scaling |
| Scoring mode | Batch; model is fitted and scored during each pipeline run |
| Decision authority | Human analyst |
| Current model persistence | Models are held in memory and are not registered or serialized |

## 2. Intended purpose

The model is designed to:

- identify unusual multivariate financial profiles that deterministic controls
  may not capture;
- prioritize records for review using amount, composition, change, ratio, and
  period signals;
- complement—not replace—financial validation rules and statistical controls;
- provide interpretable evidence by surfacing the three most unusual
  standardized feature deviations; and
- demonstrate a reproducible pathway for integrating anomaly detection into a
  governed financial-data pipeline.

### Intended users

- financial-data analysts reviewing unusual IDA reporting patterns;
- data engineers operating ingestion and data-quality controls;
- model and platform owners evaluating detector behavior; and
- technical stakeholders assessing a productionization pathway.

### Out-of-scope uses

The model must not be used to:

- automatically alter, suppress, or publish financial records;
- allege fraud, misconduct, or policy non-compliance;
- rank countries by financial performance or institutional quality;
- determine funding, replenishment, or disbursement decisions;
- replace source-system reconciliation or specialist review; or
- claim access to internal World Bank systems or non-public financial data.

## 3. Data

### Source

- **Dataset:** IDA Commitments and Disbursements — Country/Economy Summary
- **WBG Finances dataset ID:** `DS01557`
- **Resource ID:** `RS00964`
- **Unit:** USD millions
- **Coverage represented in the current run:** 3,420 IDA records, 202 named
  entities, and 14 reporting periods
- **Access:** public WBG Finances API

The pipeline retains only records whose organization is `IDA`. Regional and
institutional aggregates remain available for rule-based validation and
display, but only country records enter the current statistical and
machine-learning detectors.

### Analytical segmentation

Separate Isolation Forest models are fitted for:

| Segment | Country records | Current ML signals |
|---|---:|---:|
| Annual commitments | 1,346 | 27 |
| Annual gross disbursements | 1,234 | 25 |
| Quarterly commitments | 354 | 8 |
| Quarterly gross disbursements | 224 | 5 |

A segment is skipped when it contains fewer than 30 observations. Segmentation
prevents annual and quarterly patterns or commitments and disbursements from
being treated as directly comparable.

### Data preparation

Before model fitting, the pipeline:

1. validates required columns and controlled categories;
2. converts financial fields to numeric values;
3. parses annual and quarterly fiscal periods;
4. identifies duplicate reporting grain;
5. calculates component-to-total reconciliation;
6. labels country versus aggregate/institution records;
7. engineers chronological change and composition features; and
8. replaces infinite values with missing values for median imputation.

## 4. Model features

The model uses the following feature groups:

| Feature group | Features | Purpose |
|---|---|---|
| Magnitude | `log1p_total` | Reduces amount skew while retaining relative scale |
| Financing composition | development-policy, investment-lending, other, and program-for-results shares | Identifies unusual component mixes |
| Sequential movement | `relative_change` | Compares the record with the preceding observation in the same country/category/period-type series |
| Comparable-year movement | `year_over_year_change` | Compares with the same-quarter prior year, or the prior annual observation |
| Cross-category ratio | `disbursement_commitment_ratio` | Identifies unusual disbursement relative to commitment levels |
| Period context | `quarter` | Retains within-year timing information |

### Ratio safeguard

The disbursement-to-commitment ratio is calculated only when the absolute
commitment amount is at least USD 10 million. Below this prototype threshold,
the ratio is suppressed because a very small denominator can create an extreme
but economically misleading value.

This threshold is a documented calibration assumption, not World Bank policy.

### Preprocessing

For every segment:

1. non-finite values are converted to missing;
2. missing features are imputed with the segment median;
3. features are transformed with `RobustScaler`; and
4. Isolation Forest is fitted on the transformed matrix.

Robust scaling reduces sensitivity to extreme values when producing
human-readable deviation evidence. Isolation Forest itself remains a
multivariate, tree-based detector.

## 5. Model behavior and scoring

Isolation Forest repeatedly partitions the feature space. Records that can be
isolated with fewer random splits receive more unusual raw scores.

The implementation:

1. fits one model per eligible segment;
2. uses `fit_predict` to identify the approximately 2% most unusual records
   implied by the contamination assumption;
3. converts the negative decision function into a raw anomaly measure;
4. min-max normalizes that measure to a 0–1 score within each segment; and
5. reports the three largest absolute robust-scaled feature deviations as
   explanatory evidence.

The normalized score is **relative within a particular run and segment**. A
score of 0.90 in one segment is not guaranteed to represent the same financial
risk or error probability as 0.90 in another.

### Why 2% contamination?

`contamination=0.02` is a workload-management assumption used to create a
reviewable alert volume in an unlabeled prototype. It instructs each model to
flag approximately 2% of its segment as unusual. It does not mean:

- 2% of the source data is erroneous;
- the true error rate is 2%; or
- every flagged record requires correction.

The value must be recalibrated using specialist-reviewed outcomes, operational
review capacity, alert stability, and the relative costs of missed issues and
unnecessary reviews.

## 6. Interaction with other controls

The control tower contains three detector families:

1. **Rules:** missing/non-numeric amounts, missing keys, invalid categories,
   duplicate grain, negative values, and total reconciliation;
2. **Statistical process control:** large year-over-year movements meeting
   minimum prior-value, absolute-change, and relative-change thresholds; and
3. **Machine learning:** multivariate Isolation Forest signals.

The current run produced:

| Detector family | Signals |
|---|---:|
| Deterministic rules | 53 |
| Statistical process control | 58 |
| Isolation Forest | 65 |
| **Total detector signals** | **176** |

Signals referring to the same source record are consolidated into one analyst
alert. The current run contains 143 alerts, including 11 corroborated by at
least two detector families.

## 7. Severity and prioritization

Severity is not the same as anomaly score.

For an ML-only signal:

- it is **high** only when the normalized score is at least 0.85 and the record
  is at or above the 75th materiality percentile within its
  period/category/entity segment;
- otherwise it is **medium**; and
- it cannot independently become **critical**.

When signals are consolidated:

- an explicitly critical deterministic rule remains critical;
- agreement by at least two detector families becomes critical only when the
  base signal is already high and materiality is at least the 75th percentile;
- other corroborated alerts become high; and
- aggregate reconciliation mismatches are reduced to medium because aggregate
  component semantics may differ from country reporting.

The queue is ordered by severity, corroboration, and anomaly score. This policy
prioritizes financially material, independently supported evidence over an
opaque ML score.

## 8. Evaluation

### Controlled fault injection

The evaluation harness injects five deterministic scenarios into copies of
otherwise valid records:

| Scenario | Expected behavior | Current result |
|---|---|---|
| Missing amount | `INVALID_AMOUNT` | Detected |
| Broken reconciliation | `TOTAL_MISMATCH` | Detected |
| Negative financing component | `NEGATIVE_AMOUNT` and `TOTAL_MISMATCH` | Detected |
| Duplicate reporting grain | `DUPLICATE_GRAIN` | Detected |
| Internally reconciled historical spike | Statistical and ML signals | Detected |

All five selected scenarios were fully detected, with observed recall of 1.00
for the tested rule, statistical, and ML behaviors.

This is a **software/control-behavior test**, not an estimate of production
accuracy. The injected cases are known, deterministic, and limited in scope.

### Human review evidence

The current stratified sample contains 30 alerts:

- 4 resolved as legitimate exceptions;
- 26 requiring more information;
- 0 confirmed data issues; and
- 0 labeled false positives.

Actionable precision and false-positive rate remain intentionally unreported
until at least 10 cases are resolved. Four resolved cases are insufficient to
estimate model quality, and the portfolio review is not a substitute for
validation by an IDA financial-data specialist.

### Metrics not yet supported

The project does not currently claim:

- supervised accuracy, precision, recall, F1, or ROC-AUC on real-world labels;
- a reliable false-positive or false-negative rate;
- cross-period stability or drift performance;
- causal explanations for detected anomalies; or
- production service-level performance.

## 9. Limitations and risks

1. **No authoritative ground truth.** The public dataset does not label data
   errors, legitimate exceptions, or approved financing events.
2. **Contamination determines alert volume.** A fixed 2% assumption may under-
   or over-alert as segment distributions change.
3. **Model refitting changes the baseline.** Adding new periods can change
   scores and flags for the full segment.
4. **Small quarterly segments.** Quarterly models have fewer observations and
   therefore less stable peer distributions.
5. **Min-max score instability.** Scores are normalized using the current
   segment's observed minimum and maximum and are not calibrated probabilities.
6. **Median imputation can hide missingness.** Structural controls should catch
   missing source amounts, but derived feature gaps are imputed for model use.
7. **Aggregate classification is maintained manually.** An incomplete aggregate
   entity list could place a non-country record into a country model.
8. **Temporal and policy context is absent.** The model cannot independently
   understand crises, replenishment decisions, approved operations, or reporting
   changes that explain legitimate movements.
9. **Component semantics may vary.** Reconciliation expectations may differ for
   aggregate or institutional records.
10. **No persisted model artifact locally.** The present pipeline does not yet
    retain a serialized model, environment, feature-schema hash, or model
    registry entry.

## 10. Human oversight

Every alert must be reviewed with:

- current and comparable prior amounts;
- the applicable rule, statistical, and ML evidence;
- supporting source or public documentation;
- a recorded outcome and confidence level; and
- an attributable audit event.

Supported review outcomes are:

- `confirmed_data_issue`;
- `legitimate_exception`;
- `false_positive`; and
- `needs_more_information`.

The system should fail safely: if the review API is unavailable, the dashboard
remains readable but must reject writes explicitly.

## 11. Monitoring and recalibration

A production owner should monitor:

- population and feature distribution by model segment;
- anomaly-score and alert-volume stability;
- percentage flagged and detector agreement;
- unresolved-alert age and reviewer workload;
- confirmed issue, legitimate exception, and false-positive outcomes;
- feature missingness and schema drift;
- model, code, environment, and source-snapshot lineage; and
- reproducibility against a last-known-good publication.

Recalibration should require documented thresholds, specialist-reviewed
outcomes, before/after evaluation, and approval from both technical and
financial-data owners.

## 12. Reproducibility

Run the pipeline and controlled evaluation:

```bash
python -m src.pipeline
python -m src.evaluate
```

Relevant implementation and evidence:

- `src/features.py` — feature engineering and segmentation context;
- `src/detect.py` — statistical and Isolation Forest detectors;
- `src/pipeline.py` — signal consolidation and severity policy;
- `src/evaluate.py` — controlled fault injection;
- `artifacts/evaluation_summary.json` — evaluation results;
- `artifacts/run_summary.json` — run-level alert volumes; and
- `artifacts/review_summary.json` — review-evidence status.

For an Azure production pathway, each run should additionally retain the
immutable data reference, Git commit, environment, feature schema, model
artifact, parameters, metrics, and approval status in Azure Machine Learning.

## 13. Responsible-use statement

This is an independent portfolio prototype using public WBG data. It is not an
official World Bank Group model or system, has not been validated by an IDA
financial-data specialist, and must not be used to make operational or financial
decisions without institutional governance and domain-owner approval.
