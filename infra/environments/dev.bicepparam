using '../main.bicep'

param environment = 'dev'
param location = 'eastus2'
param namePrefix = 'nicida'

// Replace both values with a Microsoft Entra group you control before validation.
param entraAdminName = 'ida-control-admins'
param entraAdminObjectId = '00000000-0000-0000-0000-000000000000'

// Replace with the published FastAPI image when one exists.
param apiContainerImage = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

// Development-only convenience. Set false and add private endpoints for production.
param allowPublicNetwork = true
