targetScope = 'resourceGroup'

@description('Short deployment environment name.')
@allowed([
  'dev'
  'test'
  'prod'
])
param environment string = 'dev'

@description('Azure region for resources.')
param location string = resourceGroup().location

@description('Globally unique lowercase prefix. Use letters and numbers only.')
@minLength(5)
@maxLength(12)
param namePrefix string

@description('Microsoft Entra group display name used as Azure SQL administrator.')
param entraAdminName string

@description('Microsoft Entra group object ID used as Azure SQL administrator.')
param entraAdminObjectId string

@description('Container image for the FastAPI review service.')
param apiContainerImage string = 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'

@description('Deploy resources with public endpoints for portfolio/dev validation. Production should use private endpoints.')
param allowPublicNetwork bool = true

@description('Common resource tags.')
param tags object = {
  project: 'ida-financial-data-control-tower'
  environment: environment
  owner: 'Nicolaas'
  deploymentStatus: 'target-design'
}

var suffix = toLower('${namePrefix}${environment}')

module foundation './modules/foundation.bicep' = {
  name: 'foundation-${environment}'
  params: {
    location: location
    suffix: suffix
    allowPublicNetwork: allowPublicNetwork
    tags: tags
  }
}

module dataPlatform './modules/data-platform.bicep' = {
  name: 'data-platform-${environment}'
  params: {
    location: location
    suffix: suffix
    allowPublicNetwork: allowPublicNetwork
    storageAccountId: foundation.outputs.storageAccountId
    keyVaultId: foundation.outputs.keyVaultId
    applicationInsightsId: foundation.outputs.applicationInsightsId
    tags: tags
  }
}

module application './modules/application.bicep' = {
  name: 'application-${environment}'
  params: {
    location: location
    suffix: suffix
    allowPublicNetwork: allowPublicNetwork
    entraAdminName: entraAdminName
    entraAdminObjectId: entraAdminObjectId
    apiContainerImage: apiContainerImage
    logAnalyticsCustomerId: foundation.outputs.logAnalyticsCustomerId
    logAnalyticsSharedKey: foundation.outputs.logAnalyticsSharedKey
    serviceBusNamespaceName: foundation.outputs.serviceBusNamespaceName
    serviceBusQueueName: foundation.outputs.serviceBusQueueName
    tags: tags
  }
}

output storageAccountName string = foundation.outputs.storageAccountName
output keyVaultName string = foundation.outputs.keyVaultName
output dataFactoryName string = dataPlatform.outputs.dataFactoryName
output machineLearningWorkspaceName string = dataPlatform.outputs.machineLearningWorkspaceName
output serviceBusNamespaceName string = foundation.outputs.serviceBusNamespaceName
output sqlServerName string = application.outputs.sqlServerName
output containerAppName string = application.outputs.containerAppName
output containerAppUrl string = application.outputs.containerAppUrl
