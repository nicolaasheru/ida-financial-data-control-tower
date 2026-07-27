param location string
param suffix string
param allowPublicNetwork bool
param entraAdminName string
param entraAdminObjectId string
param apiContainerImage string
param logAnalyticsCustomerId string
@secure()
param logAnalyticsSharedKey string
param serviceBusNamespaceName string
param serviceBusQueueName string
param tags object

resource sqlServer 'Microsoft.Sql/servers@2023-08-01-preview' = {
  name: 'sql-${suffix}-ida'
  location: location
  tags: tags
  properties: {
    administrators: {
      administratorType: 'ActiveDirectory'
      azureADOnlyAuthentication: true
      login: entraAdminName
      principalType: 'Group'
      sid: entraAdminObjectId
      tenantId: tenant().tenantId
    }
    minimalTlsVersion: '1.2'
    publicNetworkAccess: allowPublicNetwork ? 'Enabled' : 'Disabled'
    restrictOutboundNetworkAccess: 'Enabled'
  }
}

resource sqlDatabase 'Microsoft.Sql/servers/databases@2023-08-01-preview' = {
  parent: sqlServer
  name: 'ida-control'
  location: location
  tags: tags
  sku: {
    name: 'Basic'
    tier: 'Basic'
  }
  properties: {
    collation: 'SQL_Latin1_General_CP1_CI_AS'
    zoneRedundant: false
  }
}

resource containerEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-${suffix}-ida'
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsCustomerId
        sharedKey: logAnalyticsSharedKey
      }
    }
  }
}

resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: 'ca-${suffix}-ida-api'
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    environmentId: containerEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        allowInsecure: false
        external: allowPublicNetwork
        targetPort: 8000
        transport: 'auto'
      }
    }
    template: {
      containers: [
        {
          name: 'review-api'
          image: apiContainerImage
          env: [
            {
              name: 'AZURE_SQL_SERVER'
              value: sqlServer.properties.fullyQualifiedDomainName
            }
            {
              name: 'AZURE_SQL_DATABASE'
              value: sqlDatabase.name
            }
            {
              name: 'SERVICE_BUS_NAMESPACE'
              value: serviceBusNamespaceName
            }
            {
              name: 'SERVICE_BUS_QUEUE'
              value: serviceBusQueueName
            }
            {
              name: 'DEPLOYMENT_STATUS'
              value: 'target-design'
            }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
      scale: {
        maxReplicas: 3
        minReplicas: 0
      }
    }
  }
}

output sqlServerName string = sqlServer.name
output sqlDatabaseName string = sqlDatabase.name
output containerAppName string = containerApp.name
output containerAppPrincipalId string = containerApp.identity.principalId
output containerAppUrl string = allowPublicNetwork ? 'https://${containerApp.properties.configuration.ingress.fqdn}' : 'Private ingress only'
