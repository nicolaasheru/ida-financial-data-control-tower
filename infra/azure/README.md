# Azure infrastructure boundary

This directory documents the intended infrastructure-as-code boundary for the
IDA Financial Data Control Tower. No Azure resources are created by this
repository today.

When implementation is authorized, infrastructure should be defined with Bicep
or Terraform rather than manual portal steps. Suggested modules:

```text
infra/azure/
  main.bicep
  modules/
    identities.bicep
    storage.bicep
    data-factory.bicep
    machine-learning.bicep
    sql.bicep
    service-bus.bicep
    container-apps.bicep
    monitoring.bicep
    key-vault.bicep
  parameters/
    dev.bicepparam
    test.bicepparam
    prod.bicepparam
```

Implementation requirements:

- environment-specific resource groups and parameters;
- managed identity and least-privilege RBAC;
- diagnostic settings enabled at creation;
- private networking in institutional environments;
- outputs limited to non-secret endpoints and resource identifiers;
- no plaintext credentials in parameters, state, or CI logs;
- validation and policy checks in CI before deployment.

See:

- [`../../docs/azure_target_architecture.md`](../../docs/azure_target_architecture.md)
- [`../../docs/productionization_plan.md`](../../docs/productionization_plan.md)
- [`../../docs/operations_runbook.md`](../../docs/operations_runbook.md)

