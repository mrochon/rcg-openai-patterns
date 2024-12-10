// @description('This is the base name for each Azure resource name (6-8 chars)')
// @minLength(6)
// @maxLength(8)
// param baseName string

var baseName = 'openaiarektest'

@description('The resource group location')
param location string = resourceGroup().location

// @description('The name of the workload\'s existing Log Analytics workspace.')
// param logWorkspaceName string

//variables
var openaiName = 'oai-${baseName}'



// resource logWorkspace 'Microsoft.OperationalInsights/workspaces@2022-10-01' existing = {
//   name: logWorkspaceName
// }

resource openAiAccount 'Microsoft.CognitiveServices/accounts@2024-06-01-preview' = {
  name: openaiName
  location: location
  kind: 'OpenAI'
  properties: {
    customSubDomainName: 'oai${baseName}'
    publicNetworkAccess: 'Disabled'
    networkAcls: {
      defaultAction: 'Deny'
    }
    disableLocalAuth: true
    restrictOutboundNetworkAccess: true
    allowedFqdnList: []
  }
  sku: {
    name: 'S0'
  }



  @description('Add a gpt-3.5 turbo deployment.')
  resource gpt35 'deployments' = {
    name: 'modelnamehere' //change the name of the deployment
    sku: {
      name: 'Standard'
      capacity: 25
    }
    properties: {
      model: {
        format: 'OpenAI'
        name: 'gpt-4o-mini' // exact name of the model being deployed gpt-4o-mini, gpt-4o, gpt-4
        version: '2024-07-18' // If your selected region doesn't support this version, please change it. gpt-4o-mini version 2024-07-18, gpt-4o version 2024-05-13, gpt-4 version turbo-2024-04-09
      }
      versionUpgradeOption: 'NoAutoUpgrade'  // Always pin your dependencies, be intentional about updates.
    }
  }
}

// //OpenAI diagnostic settings
// resource openAIDiagSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
//   name: 'default'
//   scope: openAiAccount
//   properties: {
//     workspaceId: logWorkspace.id
//     logs: [
//       {
//         categoryGroup: 'allLogs'  // All logs is a good choice for production on this resource.
//         enabled: true
//         retentionPolicy: {
//           enabled: false
//           days: 0
//         }
//       }
//     ]
//     logAnalyticsDestinationType: null
//   }
// }

// 

// ---- Outputs ----

output openAiResourceName string = openAiAccount.name
