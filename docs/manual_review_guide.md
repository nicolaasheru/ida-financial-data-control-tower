# Manual alert review

The review sample is a deterministic, severity-stratified sample of up to 30
alerts. Reviewers should inspect source records and supporting business context,
then populate `review_outcome`, `reviewer`, `review_notes`, `reviewed_at`,
`review_confidence`, and `evidence_url`.

Allowed outcomes:

- `confirmed_data_issue`: the source or pipeline value should be corrected.
- `legitimate_exception`: the movement is valid, but unusual enough that surfacing
  it was useful.
- `false_positive`: the alert was neither erroneous nor useful for review.
- `needs_more_information`: available evidence is insufficient.

`actionable_precision` is calculated as confirmed issues plus legitimate
exceptions divided by resolved reviews. `false_positive_rate` is false positives
divided by resolved reviews. Cases needing more information are reported but
excluded from both rates.

Rates remain null until at least ten cases are resolved. Do not interpret an
AI-assisted public-evidence review as equivalent to validation by an IDA
financial-data specialist, and do not treat internal reconciliation alone as
proof that the source record is correct.

Review status should follow:

`pending → in_review → resolved`

Use `needs_more_information` when public evidence cannot support a responsible
classification. Review decisions are stored in `artifacts/reviews.csv` separately
from regenerated detector outputs, preserving the audit trail across pipeline
runs.
