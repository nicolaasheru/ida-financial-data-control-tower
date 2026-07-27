# Azure infrastructure package

This directory contains a deployable **target-state** Bicep design for the IDA
Financial Data Control Tower. It has not been deployed by this repository and
must not be described as a live World Bank or Azure environment.

## What it provisions

- hierarchical-namespace StorageV2 account with `landing`, `standardized`,
  `curated`, and `quarantine` containers;
- Azure Key Vault with RBAC authorization and purge protection;
- Log Analytics and Application Insights;
- Azure Service Bus Standard namespace and completed-run queue;
- Azure Data Factory with a system-assigned managed identity;
- Azure Machine Learning workspace;
- Entra-only Azure SQL server and a development-sized database;
- Azure Container Apps environment and FastAPI application placeholder.

The package deliberately does not create an Azure ML compute cluster, private
endpoints, DNS zones, an image registry, or organization-specific role
assignments. Those choices require subscription, network, identity, and budget
decisions that cannot be inferred safely from a portfolio prototype.

## Prerequisites

1. Azure CLI with Bicep support;
2. an Azure subscription and permission to validate resource-group deployments;
3. registered resource providers for the services in `main.bicep`; and
4. a Microsoft Entra group to administer Azure SQL.

## Local syntax validation

```bash
az bicep build --file infra/main.bicep
```

## Subscription preparation

```bash
az login
az account set --subscription "<subscription-id>"

az provider register --namespace Microsoft.Storage
az provider register --namespace Microsoft.KeyVault
az provider register --namespace Microsoft.OperationalInsights
az provider register --namespace Microsoft.Insights
az provider register --namespace Microsoft.ServiceBus
az provider register --namespace Microsoft.DataFactory
az provider register --namespace Microsoft.MachineLearningServices
az provider register --namespace Microsoft.Sql
az provider register --namespace Microsoft.App
```

Replace the placeholder Entra object ID in `environments/dev.bicepparam`, then
validate without creating resources:

```bash
az deployment group validate \
  --resource-group "<resource-group>" \
  --template-file infra/main.bicep \
  --parameters infra/environments/dev.bicepparam
```

Preview the proposed changes:

```bash
az deployment group what-if \
  --resource-group "<resource-group>" \
  --template-file infra/main.bicep \
  --parameters infra/environments/dev.bicepparam
```

Deployment is intentionally a separate, explicit action:

```bash
az deployment group create \
  --name "ida-control-dev-$(date +%Y%m%d%H%M)" \
  --resource-group "<resource-group>" \
  --template-file infra/main.bicep \
  --parameters infra/environments/dev.bicepparam
```

## Required hardening before production

- set `allowPublicNetwork = false`;
- add private endpoints and private DNS for Storage, Key Vault, Azure ML, SQL,
  Service Bus, and Container Apps;
- assign least-privilege data-plane roles to each managed identity;
- build, scan, and publish the FastAPI image to an approved registry;
- add Entra authentication and application roles to the API and dashboard;
- move from the Basic SQL tier to a workload-tested service objective;
- configure resource-specific diagnostic settings and operational alerts;
- define data retention and immutability with financial-data owners;
- run the pipeline and application test suites as deployment gates; and
- obtain technical and financial-data-owner approval before promotion.

## Rollback boundaries

Application revisions, model versions, and curated data publications are
independently reversible. Review decisions and append-only audit events must
never be rolled back with a model or application revision.
