param location string
param suffix string
param allowPublicNetwork bool
param tags object

var storageName = take(replace('st${suffix}ida', '-', ''), 24)
var keyVaultName = take('kv-${suffix}-ida', 24)
var logAnalyticsName = 'log-${suffix}-ida'
var appInsightsName = 'appi-${suffix}-ida'
var serviceBusName = take('sb-${suffix}-ida', 50)

resource storage 'Microsoft.Storage/storageAccounts@2025-01-01' = {
  name: storageName
  location: location
  tags: tags
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false
    defaultToOAuthAuthentication: true
    isHnsEnabled: true
    minimumTlsVersion: 'TLS1_2'
    publicNetworkAccess: allowPublicNetwork ? 'Enabled' : 'Disabled'
    supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2025-01-01' = {
  parent: storage
  name: 'default'
  properties: {
    containerDeleteRetentionPolicy: {
      enabled: true
      days: 7
    }
    deleteRetentionPolicy: {
      enabled: true
      days: 7
    }
  }
}

resource dataContainers 'Microsoft.Storage/storageAccounts/blobServices/containers@2025-01-01' = [for containerName in [
  'landing'
  'standardized'
  'curated'
  'quarantine'
]: {
  parent: blobService
  name: containerName
  properties: {
    publicAccess: 'None'
  }
}]

resource keyVault 'Microsoft.KeyVault/vaults@2024-11-01' = {
  name: keyVaultName
  location: location
  tags: tags
  properties: {
    enablePurgeProtection: true
    enableRbacAuthorization: true
    enableSoftDelete: true
    publicNetworkAccess: allowPublicNetwork ? 'Enabled' : 'Disabled'
    sku: {
      family: 'A'
      name: 'standard'
    }
    softDeleteRetentionInDays: 7
    tenantId: tenant().tenantId
  }
}

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: logAnalyticsName
  location: location
  tags: tags
  properties: {
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
    retentionInDays: 30
    sku: {
      name: 'PerGB2018'
    }
  }
}

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  tags: tags
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

resource serviceBus 'Microsoft.ServiceBus/namespaces@2024-01-01' = {
  name: serviceBusName
  location: location
  tags: tags
  sku: {
    name: 'Standard'
    tier: 'Standard'
  }
  properties: {
    disableLocalAuth: true
    minimumTlsVersion: '1.2'
    publicNetworkAccess: allowPublicNetwork ? 'Enabled' : 'Disabled'
  }
}

resource alertsQueue 'Microsoft.ServiceBus/namespaces/queues@2024-01-01' = {
  parent: serviceBus
  name: 'completed-alert-runs'
  properties: {
    deadLetteringOnMessageExpiration: true
    defaultMessageTimeToLive: 'P14D'
    enablePartitioning: true
    lockDuration: 'PT1M'
    maxDeliveryCount: 10
  }
}

output storageAccountId string = storage.id
output storageAccountName string = storage.name
output keyVaultId string = keyVault.id
output keyVaultName string = keyVault.name
output applicationInsightsId string = applicationInsights.id
output logAnalyticsCustomerId string = logAnalytics.properties.customerId
@secure()
output logAnalyticsSharedKey string = logAnalytics.listKeys().primarySharedKey
output serviceBusNamespaceName string = serviceBus.name
output serviceBusQueueName string = alertsQueue.name
