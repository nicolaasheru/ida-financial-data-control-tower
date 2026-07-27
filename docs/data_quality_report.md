# Data-quality report: IDA Financial Data Control Tower

> **Report status:** portfolio evaluation of a public-data snapshot  
> **Report version:** 1.0  
> **Last updated:** 2026-07-27  
> **Pipeline run evaluated:** 2026-07-26 06:33:31 UTC  
> **Owner:** Nicolaas Heru Dreandachrista

## 1. Executive summary

The evaluated snapshot contains 3,420 IDA commitment and gross-disbursement
records retrieved from the public WBG Finances API. The extraction count matched
the API-declared count, all required fields were populated after type
conversion, no duplicate reporting grain was found, and all categories and
periods conformed to the supported formats.

The snapshot is suitable for this portfolio's anomaly-detection and analyst
review workflow, subject to documented financial and contextual caveats:

- 51 negative-value signals occur across 29 records and may represent legitimate
  corrections or reversals;
- two `World` aggregate FY17 records do not reconcile under country-style
  component logic and require confirmation of aggregate reporting semantics;
- historical features are unavailable for first observations or zero-valued
  prior periods;
- the disbursement-to-commitment ratio is deliberately suppressed when the
  commitment denominator is below USD 10 million; and
- only four sampled alerts have reached a resolved human-review outcome, which
  is insufficient to estimate real-world precision or false-positive behavior.

No composite “data-quality score” is reported. Combining distinct dimensions
into one percentage would conceal the difference between structural validity,
financial interpretation, model readiness, and domain confirmation.

## 2. Scope and provenance

| Attribute | Value |
|---|---|
| Dataset | IDA Commitments and Disbursements — Country/Economy Summary |
| Dataset ID | `DS01557` |
| Resource ID | `RS00964` |
| Source | Public WBG Finances API |
| Unit | USD millions |
| Source records received | 3,420 |
| IDA records retained | 3,420 |
| Named entities represented | 202 |
| Reporting periods | 14 |
| Annual coverage | FY14–FY25 |
| Quarterly coverage | 2025-Q3 and 2026-Q3 |

The current raw file contains the declared record count and source records. It
does not yet contain a full ingestion manifest with retrieval timestamps, page
hashes, source headers, schema fingerprints, or a pipeline commit. These are
specified in the Azure productionization design but are not claimed as locally
implemented evidence.

## 3. Quality dimensions

| Dimension | Current status | Evidence | Interpretation |
|---|---|---|---|
| Extraction completeness | Pass for evaluated snapshot | 3,420 received of 3,420 declared | No missing API page detected by count |
| Required-field completeness | Pass | 0 missing values across required keys and financial fields after conversion | Suitable for current controls |
| Reporting-grain uniqueness | Pass | 0 duplicate rows at organization/country/category/period grain | No duplicate consolidation required |
| Category conformity | Pass | 1,846 commitments and 1,574 gross disbursements; no unsupported category | Controlled vocabulary holds |
| Period conformity | Pass | All rows parse as `FYnn` or `YYYY-Qn` | Annual and quarterly segmentation is available |
| Financial sign validity | Review required | 51 negative-value signals across 29 records | May be correction/reversal or source issue |
| Component reconciliation | Contextual caveat | 3,418 of 3,420 rows within tolerance; two `World` aggregate exceptions | Aggregate semantics require confirmation |
| Historical feature availability | Expected limitation | 1,930 of 3,420 rows have finite relative and year-over-year change | First/zero-prior observations cannot support change features |
| Ratio feature availability | Controlled limitation | 1,908 rows have a calculated disbursement/commitment ratio | Tiny denominators are suppressed |
| Domain validation | Insufficient | 4 resolved review cases | Specialist-reviewed evidence remains limited |

“Pass” means that the implemented control found no failure in this particular
snapshot. It does not guarantee correctness of the originating system or future
extracts.

## 4. Ingestion integrity

The ingestion function:

1. requests the official API in pages of up to 1,000 records;
2. stores the first declared source count;
3. accumulates every returned page;
4. stops only when a page is shorter than the requested page size; and
5. raises an error when received and declared counts differ.

For the evaluated snapshot:

| Check | Result |
|---|---:|
| API-declared count | 3,420 |
| Records received | 3,420 |
| Count difference | 0 |
| IDA records retained | 3,420 |

### Remaining ingestion gaps

The current local implementation does not yet:

- retry with bounded exponential backoff;
- persist a per-page checksum;
- verify that the declared count remains stable throughout pagination;
- compare source schema fingerprints between runs;
- write to a temporary landing location before atomic promotion; or
- quarantine incomplete pages separately from validated records.

The Azure target architecture assigns those responsibilities to Data Factory,
Data Lake Storage, and last-known-good publication gates.

## 5. Schema and conformity

### Required fields

The pipeline requires:

- category;
- country;
- organization;
- region;
- time period;
- development-policy financing;
- investment lending;
- other financing;
- program-for-results financing; and
- reported total.

All 3,420 validated IDA rows contain usable values for those fields after
whitespace normalization and numeric conversion.

### Controlled categories

| Category | Records | Share |
|---|---:|---:|
| Commitments | 1,846 | 54.0% |
| Gross disbursements | 1,574 | 46.0% |
| **Total** | **3,420** | **100.0%** |

No record falls outside the supported vocabulary.

### Period formats

The pipeline supports:

- annual periods formatted as `FYnn`; and
- quarterly periods formatted as `YYYY-Qn`.

All current rows parse successfully. Annual periods are assigned quarter 4 only
for chronological feature ordering; this does not convert an annual observation
into a quarterly one.

## 6. Completeness and uniqueness

### Required-field missingness

The validated dataset contains zero missing values across:

- all source key fields;
- all source financial fields;
- parsed fiscal year and quarter;
- derived period type; and
- component sum and reconciliation difference.

Derived historical and ratio features are treated separately because their
absence can be structurally expected.

### Grain uniqueness

Expected reporting grain:

```text
organization + country + category + time_period
```

No duplicate grain was observed in the evaluated source snapshot.

The fault-injection harness confirms that an introduced duplicate is detected
with `DUPLICATE_GRAIN`.

## 7. Financial validity

### Negative values

The current rules treat negative values as reviewable, not automatically
erroneous, because they may represent corrections or reversals.

| Field | Negative rows | Observed minimum |
|---|---:|---:|
| Development-policy financing | 6 | -1.3 |
| Investment lending | 21 | -19.0 |
| Other financing | 2 | -0.3 |
| Program-for-results financing | 0 | 0.0 |
| Reported total | 22 | -19.0 |

Because one record can contain multiple negative fields, these produce 51
signals across 29 unique records.

Required analyst action:

1. confirm whether the value represents an approved correction or reversal;
2. compare the record with source documentation and adjacent periods;
3. retain the sign when legitimate rather than forcing it to zero; and
4. record a review outcome and evidence link.

### Component-to-total reconciliation

The control compares:

```text
reported total
versus
development policy + investment lending + others + program for results
```

Tolerance is the larger of:

- USD 1.01 million; or
- 0.1% of the absolute reported total.

The tolerance accommodates historical annual values rounded to USD millions.

| Result | Records | Share |
|---|---:|---:|
| Within tolerance | 3,418 | 99.94% |
| Outside tolerance | 2 | 0.06% |

Both exceptions are `World` aggregate records for FY17:

| Category | Reported total | Component sum | Difference |
|---|---:|---:|---:|
| Commitments | 50.0 | 0.0 | 50.0 |
| Gross disbursements | 50.0 | 0.0 | 50.0 |

The pipeline reduces these aggregate exceptions to medium severity because
aggregate reporting semantics may not follow country-style component
reconciliation. They must not be labeled source errors without domain
confirmation.

## 8. Coverage and segmentation

### Period/category coverage

| Segment | Records |
|---|---:|
| Annual commitments | 1,460 |
| Annual gross disbursements | 1,328 |
| Quarterly commitments | 386 |
| Quarterly gross disbursements | 246 |

### Entity classification

| Entity type | Records | Current detector treatment |
|---|---:|---|
| Country | 3,158 | Eligible for statistical and ML detectors |
| Aggregate or institution | 262 | Rule validation and display only |

This separation prevents regional, global, IFC, or MIGA-style records from
distorting country peer distributions. The aggregate list is currently
configuration-based and should be replaced or validated against authoritative
metadata before production.

## 9. Derived-feature readiness

Derived-feature missingness is not equivalent to source missingness.

| Feature | Available rows | Availability | Main reason unavailable |
|---|---:|---:|---|
| Previous total | 2,779 | 81.26% | First observation in a series |
| Previous-year total | 2,779 | 81.26% | No comparable earlier observation |
| Relative change | 1,930 | 56.43% | Missing or zero prior amount |
| Year-over-year change | 1,930 | 56.43% | Missing or zero comparable prior amount |
| Disbursement/commitment ratio | 1,908 | 55.79% | Missing pair or suppressed denominator |

The ratio denominator is eligible for 1,924 rows. A ratio may still remain
unavailable when its paired commitment or disbursement value is absent for the
same country and period.

Recommendations:

- retain explicit missingness/eligibility indicators;
- monitor feature availability by segment and run;
- do not substitute zero for an unavailable financial ratio; and
- investigate material changes in feature availability as potential schema or
  coverage drift.

## 10. Alert profile

The evaluated run generated 176 detector signals consolidated into 143
record-level alerts.

### Signals by reason

| Reason code | Signals |
|---|---:|
| `MULTIVARIATE_ANOMALY` | 65 |
| `YEAR_OVER_YEAR_SHIFT` | 58 |
| `NEGATIVE_AMOUNT` | 51 |
| `TOTAL_MISMATCH` | 2 |
| **Total** | **176** |

### Consolidated alerts

| Severity | Alerts | Share of alerts |
|---|---:|---:|
| Medium | 121 | 84.6% |
| High | 14 | 9.8% |
| Critical | 8 | 5.6% |
| **Total** | **143** | **100.0%** |

Additional context:

- 11 alerts are corroborated by at least two detector families;
- 88 alerts concern commitments;
- 55 concern gross disbursements;
- 110 concern annual records;
- 33 concern quarterly records; and
- alerts span 73 named entities.

An alert rate of 143/3,420 (4.18%) does not represent an error rate. Alerts
include unusual but potentially legitimate financial activity and multiple
independent control types.

## 11. Controlled evaluation

The fault-injection harness detected all five selected scenarios:

1. missing amount;
2. broken reconciliation;
3. negative component;
4. duplicate reporting grain; and
5. an internally reconciled historical spike.

Observed recall was 1.00 for the selected rule, statistical, and ML behaviors.
This verifies that the implemented controls respond to those deterministic test
cases. It does not measure real-world source accuracy, model precision, or
false-negative behavior.

## 12. Human-review evidence

The current stratified review sample contains 30 alerts:

| Outcome | Cases |
|---|---:|
| Legitimate exception | 4 |
| Needs more information | 26 |
| Confirmed data issue | 0 |
| False positive | 0 |

Actionable precision and false-positive rate remain null until at least 10 cases
are resolved. The present evidence cannot support a reliable performance claim.

Priority next step: obtain review by a financial-data specialist and resolve a
larger, segment-aware sample containing rules, statistical shifts, ML-only
alerts, and corroborated alerts.

## 13. Remediation priorities

| Priority | Improvement | Acceptance evidence |
|---:|---|---|
| 1 | Add immutable ingestion manifests and per-page hashes | Every run traces to complete source evidence |
| 2 | Add atomic landing-to-publication promotion | Failed runs preserve the last known-good dashboard |
| 3 | Replace manual aggregate configuration with authoritative metadata | Entity classification coverage is reviewed and versioned |
| 4 | Expand specialist-labeled review sample | Precision and false-positive estimates pass the minimum evidence threshold |
| 5 | Monitor schema, population, and feature drift | Run-level trend report and alert thresholds exist |
| 6 | Persist model, environment, feature schema, and code lineage | A scored alert traces to a reproducible model run |
| 7 | Add bounded API retry and explicit quarantine | Source interruptions do not create partial publications |
| 8 | Calibrate materiality and contamination assumptions | Threshold changes are supported by reviewed outcomes |

## 14. Reproducibility

Generate the current source, processed data, signals, alerts, and summaries:

```bash
python -m src.pipeline
python -m src.evaluate
python -m src.review --summarize
```

Primary evidence:

- `data/raw/ida_commitments_disbursements.json`;
- `data/processed/ida_commitments_disbursements.csv`;
- `data/processed/ida_model_features.csv`;
- `artifacts/alert_signals.csv`;
- `artifacts/alerts.csv`;
- `artifacts/evaluation_summary.json`;
- `artifacts/run_summary.json`; and
- `artifacts/review_summary.json`.

## 15. Responsible interpretation

This report evaluates the behavior of an independent portfolio prototype using
public WBG data. It is not an official World Bank Group data-quality
certification. Financial exceptions require confirmation against authoritative
definitions, source documentation, and specialist judgment before correction or
downstream use.
