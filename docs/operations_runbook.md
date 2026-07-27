# Operations runbook

> Proposed operating procedures for the Azure target architecture. The current
> prototype continues to run locally.

## 1. Daily operating view

Operators should confirm:

1. latest scheduled pipeline status;
2. source declared count versus received count;
3. active publication and its age;
4. quarantined records/pages;
5. alert volume and severity change from the prior successful run;
6. model/data-contract gate results;
7. Service Bus active/dead-letter messages;
8. API/database availability;
9. unresolved critical-alert age.

## 2. Run states

| State | Meaning | Dashboard behavior |
|---|---|---|
| `started` | Orchestration accepted the run | Continue showing last good publication |
| `ingested` | Complete source snapshot promoted | Continue showing last good publication |
| `validated` | Schema and financial controls completed | Continue showing last good publication |
| `scored` | Feature and detector outputs completed | Continue showing last good publication |
| `approved` | Publication gates passed | Eligible to publish |
| `published` | Curated outputs and alerts activated | Show new run |
| `failed` | A required stage or gate failed | Show last good run with stale/failure notice |
| `quarantined` | Source evidence retained for investigation | Do not publish |

## 3. Incident priorities

| Priority | Example | Initial response |
|---|---|---|
| P1 | Unauthorized access, corrupted review evidence, or wrong publication replacing active data | Stop writes/publication, preserve evidence, notify security and financial owners |
| P2 | Scheduled run failed, API unavailable, or critical queue blocked | Retain last good run, investigate within agreed support window |
| P3 | Noncritical telemetry gap, delayed low-severity notification, or cosmetic defect | Record and address through normal backlog |

Financial alerts are not application incidents unless the control system itself
behaved incorrectly.

## 4. Ingestion failure

1. Record the ADF run ID and source response status.
2. Confirm whether the failure is connectivity, throttling, malformed content,
   count drift, or schema drift.
3. Verify that no temporary landing path was promoted.
4. Preserve manifest and page evidence in quarantine.
5. If transient, rerun with the same logical date and a new execution ID.
6. If source semantics changed, stop automated publication and raise a data
   contract review.
7. Confirm the dashboard still points to the prior successful publication.

Never manually edit the raw snapshot to force a run through.

## 5. Unexpected alert-volume change

1. Compare source record counts and category/period composition.
2. Check feature null rates and segment population.
3. Confirm code, environment, and model versions.
4. Compare rules, statistical signals, and ML-only signals separately.
5. Review the highest-materiality new alerts.
6. If unexplained, withhold publication or require explicit approval.
7. Record the decision and supporting evidence in the run metadata.

Do not change contamination merely to restore a familiar alert count.

## 6. Review service unavailable

1. Switch or retain the dashboard in read-only mode.
2. Reject writes clearly; never imply they were saved.
3. Check Container Apps revision health and Azure SQL connectivity.
4. Inspect Application Insights failures and database metrics.
5. Restore the previous healthy application revision if the current release is
   causal.
6. Reconcile any Service Bus messages after recovery.
7. Verify audit event continuity before reopening writes.

## 7. Model rollback

1. Freeze further production promotion.
2. Identify the last approved model, environment, and feature schema.
3. Confirm compatibility with the active standardized dataset.
4. run the evaluation and contract suite against the rollback candidate.
5. repoint scoring to the approved version;
6. publish through the normal atomic publication gate;
7. retain the regressed model and incident evidence for analysis.

Do not delete the failed model version. Review decisions remain unchanged.

## 8. Application rollback

1. Identify the previous healthy Container Apps revision.
2. Shift traffic back to that immutable revision.
3. Validate health, authentication, read operations, write/version conflicts,
   and audit-event creation.
4. Confirm dashboard/API compatibility.
5. document the rollback and suspend the faulty release.

Database migrations require a separately tested rollback or forward-fix plan.

## 9. Dead-letter queue handling

1. Inspect message reason, run ID, and retry count.
2. Confirm the referenced curated publication still exists.
3. Resolve the downstream cause before replay.
4. Replay idempotently using `record_key` and publication ID.
5. Confirm no duplicate alert or audit event was created.
6. Retain resolution evidence.

## 10. Evidence retained per incident

- pipeline/application/model run IDs;
- source and curated snapshot references;
- code and environment versions;
- timestamps and actors;
- relevant logs and metrics;
- customer/financial impact assessment;
- mitigation and rollback decision;
- follow-up owner and due date.

## 11. Periodic controls

### Weekly

- review failed and quarantined runs;
- review unresolved critical alerts and dead-letter messages;
- check identity/RBAC changes;
- confirm backups and diagnostic coverage.

### Monthly

- review model and feature drift;
- review analyst outcomes and false-positive evidence;
- test restoration of the last known-good publication;
- inspect cost and idle resources;
- patch application dependencies.

### Quarterly

- rehearse application/model rollback;
- review access groups and service identities;
- revisit materiality and model assumptions with financial owners;
- review retention, recovery objectives, and incident lessons.

