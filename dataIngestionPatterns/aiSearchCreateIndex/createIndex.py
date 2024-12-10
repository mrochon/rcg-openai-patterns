import os
import io
import requests
import json
from azure.core.credentials import AzureKeyCredential
from openai import AzureOpenAI
from dotenv import load_dotenv
import re

# Load environment variables
load_dotenv(override=True)

# Load environment variables for Azure services
service_endpoint = os.getenv("AZURE_SEARCH_SERVICE_ENDPOINT")
credential = AzureKeyCredential(os.getenv("AZURE_SEARCH_ADMIN_KEY"))
# index_name = os.getenv("AZURE_SEARCH_INDEX3")

azure_openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
azure_openai_api_key = os.getenv("AZURE_OPENAI_API_KEY")
embedding_model_deployment_name = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME")
embedding_model_name = os.getenv("AZURE_OPENAI_EMBEDDING_MODEL_NAME")
azure_openai_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01")

# Create the search index using the AI Search API
def create_or_update_search_index(indexName):
    # Define the payload for the AI Search API
    index_payload = {
        "name": indexName,
        "vectorSearch": {
            "algorithms": [
                {
                    "name": "my-hnsw-config-1",
                    "kind": "hnsw",
                    "hnswParameters": {
                        "m": 4,
                        "efConstruction": 400,
                        "efSearch": 500,
                        "metric": "cosine",
                    },
                },
                {
                    "name": "my-hnsw-config-2",
                    "kind": "hnsw",
                    "hnswParameters": {
                        "m": 8,
                        "efConstruction": 800,
                        "efSearch": 800,
                        "metric": "cosine",
                    },
                },
                {
                    "name": "my-eknn-config",
                    "kind": "exhaustiveKnn",
                    "exhaustiveKnnParameters": {"metric": "cosine"},
                },
            ],
            "vectorizers": [
                {
                    "name": "openai",
                    "kind": "azureOpenAI",
                    "azureOpenAIParameters": {
                        "resourceUri": azure_openai_endpoint,
                        "apiKey": azure_openai_api_key,
                        "deploymentId": embedding_model_deployment_name,
                        "modelName": embedding_model_name,
                    },
                }
            ],
            "profiles": [
                {
                    "name": "my-vector-profile-1",
                    "algorithm": "my-hnsw-config-1",
                    "vectorizer": "openai",
                },
                {
                    "name": "my-vector-profile-2",
                    "algorithm": "my-hnsw-config-2",
                    "vectorizer": "openai",
                },
                {
                    "name": "my-vector-profile-3",
                    "algorithm": "my-eknn-config",
                    "vectorizer": "openai",
                },
            ],
        },
        "semantic": {
            "configurations": [
                {
                    "name": "my-semantic-config",
                    "prioritizedFields": {
                        "titleField": {"fieldName": "title"},
                        "prioritizedContentFields": [{"fieldName": "content"}],
                        "prioritizedKeywordsFields": [],
                    },
                }
            ]
        },
        "fields": [
            {"name": "id", "type": "Edm.String", "key": "true", "filterable": "true"},
            {
                "name": "content",
                "type": "Edm.String",
                "searchable": "true",
                "retrievable": "true",
                "analyzer": "en.microsoft",  # Matches the analyzer_name
            },
            {
                "name": "title",
                "type": "Edm.String",
                "searchable": "true",
                "retrievable": "true",
            },
            {
                "name": "embedding",
                "type": "Collection(Edm.Single)",
                "dimensions": 1536,
                "vectorSearchProfile": "my-vector-profile-1",
                "searchable": "true",
                "retrievable": "false",
            },
            {
                "name": "category",
                "type": "Edm.String",
                "filterable": "true",
                "facetable": "true",
                "retrievable": "true",
            },
        ],
    }

    headers = {
        "Content-Type": "application/json",
        "api-key": os.environ["AZURE_SEARCH_ADMIN_KEY"],
    }

    params = {"api-version": "2024-05-01-Preview"}
    # Send the PUT request to the Azure Search API to create/update the index
    index_url = f"{service_endpoint}/indexes/{indexName}"
    response = requests.put(
        index_url, headers=headers, data=json.dumps(index_payload), params=params
    )

    # Check the response
    if response.status_code == 201 or response.status_code == 204:
        print(f"Search index '{indexName}' created/updated successfully.")
    else:
        print(f"Error creating/updating index: {response.status_code} {response.text}")


def delete_search_index(indexName):
    headers = {
        "Content-Type": "application/json",
        "api-key": os.environ["AZURE_SEARCH_ADMIN_KEY"],
    }

    params = {"api-version": "2024-05-01-Preview"}
    # Send the DELETE request to the Azure Search API to delete the index
    index_url = f"{service_endpoint}/indexes/{indexName}"
    response = requests.delete(index_url, headers=headers, params=params)

    # Check the response
    if response.status_code == 204:
        print(f"Search index '{indexName}' deleted successfully.")
    else:
        print(f"Error deleting index: {response.status_code} {response.text}")


# Run the index creation functions
index_name = os.getenv("AZURE_SEARCH_INDEX3")
delete_search_index(index_name)
create_or_update_search_index(index_name)
