# Azure productionization plan

> **Status:** deployable target design; not deployed  
> **Implemented reference:** local Python pipeline, FastAPI review service,
> SQLite review store, and analyst dashboard

## Purpose

This plan converts the local prototype into a governed Azure workload while
preserving the financial-control logic, reproducibility, analyst accountability,
and last-known-good publication behavior.

## Delivery stages

| Stage | Outcome | Exit gate |
|---|---|---|
| 1. Template validation | Bicep compiles and the resource-group deployment validates | `az bicep build` and `az deployment group validate` pass |
| 2. Development foundation | Storage zones, monitoring, Key Vault, messaging, Azure ML, SQL, and Container Apps exist | Resource outputs and managed identities verified |
| 3. Identity and data access | Workloads use managed identities; people use Entra groups | No application secret is committed or embedded |
| 4. Pipeline migration | Existing ingestion, validation, feature, and scoring code runs as versioned batch jobs | Output contracts match the local reference |
| 5. Review migration | Stable alert keys and audit history are migrated from SQLite to Azure SQL | State-transition and concurrency tests pass |
| 6. Application release | Containerized FastAPI and dashboard are accessible to authorized reviewers | UAT, telemetry, and rollback test pass |
| 7. Controlled promotion | A candidate model and curated publication pass agreed gates | Technical and financial-data-owner approvals recorded |

## Environment strategy

- **Development:** public endpoints may be enabled for controlled validation;
  scale-to-zero application compute and development database sizing.
- **Test:** production-like identity, private networking, representative data,
  fault injection, concurrency testing, and recovery exercises.
- **Production:** private endpoints, approved network topology, workload-tested
  capacity, formal ownership, retention rules, alert routing, and support model.

The included `dev.bicepparam` file is intentionally not a production
configuration.

## Security model

1. ADF, Azure ML, and Container Apps use system-assigned managed identities.
2. Data-plane access is granted through narrowly scoped Azure RBAC assignments.
3. Azure SQL uses Microsoft Entra-only administration; database users must be
   created for the Container Apps identity after provisioning.
4. Key Vault uses RBAC authorization, soft delete, and purge protection.
5. Storage disables anonymous blob access, enforces TLS 1.2, and defaults to
   OAuth authentication.
6. Service Bus disables local SAS-key authentication.
7. Production endpoints are private and resolved through approved private DNS.

## CI/CD gates

The repository workflow compiles Bicep on infrastructure changes without
requiring cloud credentials. An institutional pipeline should add:

1. linting and unit tests;
2. Bicep compile and resource-group validation;
3. `what-if` review with retained output;
4. container build, dependency scan, and image signing;
5. deployment to development;
6. pipeline and review-workflow integration tests;
7. manual approval for test and production;
8. post-deployment smoke tests; and
9. automatic rollback or traffic reversion on failed health gates.

Use workload identity federation for CI/CD. Do not store client secrets in
repository settings when federated identity is available.

## Publication and rollback

Each successful analytical run receives a stable `run_id` and records:

- source snapshot URI and hash;
- Git commit and environment version;
- feature schema;
- model version and parameters;
- validation and fault-injection results;
- record and alert counts; and
- publication timestamp.

The dashboard reads only the active, successfully promoted run. A failed run
must not replace it.

Rollback boundaries are independent:

- **application:** route traffic to the preceding Container Apps revision;
- **model:** repoint scoring to the preceding registered model/environment;
- **data:** repoint the active publication to the last known-good curated run;
- **review evidence:** never roll back accepted decisions or audit events.

## Cost posture

No monthly amount is claimed because cost depends on region, usage, networking,
retention, and institutional agreements. Before deployment, estimate the
parameterized design in the Azure Pricing Calculator and set a resource-group
budget.

Likely cost drivers:

| Service | Main cost driver | Development control |
|---|---|---|
| Azure Machine Learning | compute job duration and selected VM | no always-on compute; batch jobs only |
| Azure SQL | service tier and provisioned capacity | Basic tier in the template |
| Container Apps | active replicas, CPU, memory, and requests | minimum replicas set to zero |
| Log Analytics | ingested telemetry and retention | 30-day retention; avoid verbose payload logging |
| Service Bus | tier and operations | Standard tier and one queue |
| Storage | retained data, transactions, and redundancy | Standard LRS for development |
| Private networking | endpoints, DNS, and data processing | introduce in test/production after topology approval |

Cost controls should include budgets, anomaly alerts, mandatory tags, retention
policies, and explicit approval for non-development SKUs.

## Evidence required before claiming deployment

- successful Bicep build, validation, and `what-if`;
- Azure resource IDs and deployment output;
- pipeline run linked to immutable source and curated data;
- registered model version and evaluation evidence;
- authenticated API and dashboard smoke test;
- audit event written through Azure SQL;
- Azure Monitor telemetry and an exercised alert; and
- documented rollback test.

Until those artifacts exist, portfolio language should remain **“designed an
Azure-oriented production pathway and deployable Bicep templates.”**
