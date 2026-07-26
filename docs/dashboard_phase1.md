# Phase 1 — Functional analyst dashboard

## Purpose

The Phase 1 dashboard is a deliberately functional first pass used to test the
information architecture before visual refinement in Figma. It turns generated
pipeline artifacts into an analyst investigation workflow.

## Primary questions

1. What requires attention now?
2. Why was a record flagged?
3. What financial context supports the alert?
4. Do independent detector families agree?
5. What evidence and review outcome already exist?
6. How well have the controls and review process been evaluated?

## Implemented views

### Alert operations

- run health and source-record volume;
- alerts by severity;
- corroborated-alert count;
- review-resolution progress;
- search by entity, region, category, or reason;
- severity, reporting-period, and review-state filters;
- priority, materiality, and amount sorting;
- current-versus-comparable-prior amounts;
- alert reasons and detector evidence;
- anomaly score, materiality percentile, and detector count;
- recommended analyst action; and
- review outcome, confidence, notes, and supporting evidence.

### Model and data quality

- controlled fault-injection coverage by detector layer;
- detector signal mix;
- review-evidence maturity and rate-suppression threshold; and
- the principal segmentation and severity safeguards.

### Portfolio visualizations

1. An annual stacked alert trend by severity.
2. Regional concentration of critical and high alerts, with associated current
   financial amounts.
3. Detector-family intersections separating standalone from corroborated
   alerts.
4. A review funnel from generated alerts to sampled and resolved cases.

These views describe the alert and review populations. They do not represent
financial losses, causal model explanations, or production accuracy.

## Phase 1 limitations

- The interface reads synchronized artifact snapshots and does not write review
  decisions back to `reviews.csv`.
- It is not connected to an orchestrated cloud pipeline.
- Its visual system is provisional and should be reconsidered in Figma.
- Detection success on controlled injections is not presented as real-world
  model accuracy.
- Analyst-review rates remain suppressed until sufficient cases are resolved.

## Questions for the Figma pass

- Should the investigation panel remain persistent or open as a full-page case?
- Which queue columns can be removed without losing decision context?
- Should the first viewport prioritize severity, financial materiality, or
  review backlog?
- How should corroboration across rules, statistics, and ML be visualized?
- Does model quality belong in the primary navigation or a secondary settings
  area?
- Which evidence fields need progressive disclosure for nontechnical reviewers?
