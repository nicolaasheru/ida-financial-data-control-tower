param location string
param suffix string
param allowPublicNetwork bool
param storageAccountId string
param keyVaultId string
param applicationInsightsId string
param tags object

resource dataFactory 'Microsoft.DataFactory/factories@2018-06-01' = {
  name: 'adf-${suffix}-ida'
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    publicNetworkAccess: allowPublicNetwork ? 'Enabled' : 'Disabled'
  }
}

resource machineLearning 'Microsoft.MachineLearningServices/workspaces@2024-10-01' = {
  name: 'mlw-${suffix}-ida'
  location: location
  kind: 'Default'
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    applicationInsights: applicationInsightsId
    description: 'Batch validation, feature engineering, anomaly detection, and controlled model registration.'
    friendlyName: 'IDA Financial Data Control Tower'
    hbiWorkspace: false
    keyVault: keyVaultId
    publicNetworkAccess: allowPublicNetwork ? 'Enabled' : 'Disabled'
    storageAccount: storageAccountId
  }
}

output dataFactoryName string = dataFactory.name
output dataFactoryPrincipalId string = dataFactory.identity.principalId
output machineLearningWorkspaceName string = machineLearning.name
output machineLearningPrincipalId string = machineLearning.identity.principalId
