# Processed feature data dictionary

## Identity and reporting grain

| Field | Meaning |
| --- | --- |
| `record_key` | Stable SHA-256-derived identifier for organization × country × category × time period. |
| `row_id` | Positional source-row reference for display and traceability; not used for review identity. |
| `organization` | Financing organization; the current prototype filters to IDA. |
| `country` | Country, region, or institutional entity reported by the source. |
| `region` | Source geographic grouping. |
| `category` | Commitments or Gross Disbursements. |
| `time_period` | Fiscal-year (`FYnn`) or quarterly (`YYYY-Qn`) reporting period. |
| `period_type` | Derived annual or quarterly classification. |
| `fiscal_year` | Normalized four-digit fiscal year. |
| `quarter` | Fiscal quarter; annual observations use quarter 4 for modeling. |
| `entity_type` | Country or aggregate/institution classification. |

## Financial values and reconciliation

| Field | Meaning |
| --- | --- |
| `development_policy` | Development-policy financing amount, USD millions. |
| `investment_lending` | Investment-lending amount, USD millions. |
| `others` | Other financing amount, USD millions. |
| `program_for_results` | Program-for-results amount, USD millions. |
| `total` | Reported financial total, USD millions. |
| `component_sum` | Sum of the four financing components. |
| `reconciliation_difference` | Reported total minus component sum. |

## Engineered model features

| Field | Meaning |
| --- | --- |
| `*_share` | Component amount divided by total for each financing component. |
| `log1p_*` | Signed-safe logarithmic scale for amounts; `log1p_total` enters the ML model. |
| `previous_total` | Previous observation within the same entity, category, and period type. |
| `absolute_change` | Current total minus previous total. |
| `relative_change` | Change relative to the previous observation. |
| `previous_year_total` | Comparable prior-year value. |
| `year_over_year_change` | Relative change from the comparable prior year. |
| `commitment_total` | Country-period commitment total used for contextual comparison. |
| `disbursement_total` | Country-period gross-disbursement total used for contextual comparison. |
| `ratio_denominator_eligible` | Whether commitments meet the USD 10M minimum denominator. |
| `disbursement_commitment_ratio` | Disbursements divided by commitments when denominator-eligible. |
| `absolute_total` | Absolute reported total used for materiality ranking. |
| `materiality_percentile` | Within-category and period-type percentile of absolute total. |
| `materiality_band` | Descriptive materiality tier used in prioritization. |
