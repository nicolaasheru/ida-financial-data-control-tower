# Manual alert review

The review sample is a deterministic, severity-stratified sample of up to 30
alerts. Reviewers should inspect source records and supporting business context,
then populate `review_outcome`, `reviewer`, `review_notes`, and `reviewed_at`.

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

Do not interpret the initial unlabeled sample as evidence of model accuracy.
