import os
import json
from openai import AzureOpenAI
from tenacity import retry, wait_random_exponential, stop_after_attempt
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.models import Vector
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
    SearchIndex,
    SemanticConfiguration,
    PrioritizedFields,
    SemanticField,
    SearchField,
    SemanticSettings,
    VectorSearch,
    HnswVectorSearchAlgorithmConfiguration,
)
from dotenv import load_dotenv


load_dotenv(override=True)  # take environment variables from .env.
# The following variables from your .env file are used in this notebook
service_endpoint = os.environ["AZURE_SEARCH_SERVICE_ENDPOINT"]
credential = AzureKeyCredential(os.environ["AZURE_SEARCH_ADMIN_KEY"])
index_name = os.environ["AZURE_SEARCH_INDEX"]

azure_openai_endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
azure_openai_key = (
    os.environ["AZURE_OPENAI_API_KEY"]
    if len(os.environ["AZURE_OPENAI_API_KEY"]) > 0
    else None
)
azure_openai_embedding_deployment = os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME"]
embedding_model_name = os.environ["AZURE_OPENAI_EMBEDDING_MODEL_NAME"]
gpt_model_name = os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"]
azure_openai_api_version = os.environ["AZURE_OPENAI_API_VERSION"]

# Create the Azure Cognitive Search client to issue queries
search_client = SearchClient(
    endpoint=service_endpoint, index_name=index_name, credential=credential
)

# Create the index client
index_client = SearchIndexClient(endpoint=service_endpoint, credential=credential)

# Configure OpenAI environment variables
client = AzureOpenAI(
    azure_endpoint=azure_openai_endpoint,  # The base URL for your Azure OpenAI resource. e.g. "https://<your resource name>.openai.azure.com"
    api_key=os.getenv(
        "AZURE_OPENAI_API_KEY"
    ),  # The API key for your Azure OpenAI resource.
    api_version=os.environ[
        "AZURE_OPENAI_API_VERSION"
    ],  # This version supports function calling
    azure_deployment=os.getenv(
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME"
    ),  # The deployment for your Azure OpenAI resource. e.g. "production"
)

# Create a search index
fields = [
    SimpleField(
        name="recipe_id",
        type=SearchFieldDataType.String,
        key=True,
        sortable=True,
        filterable=True,
        facetable=True,
    ),
    SearchableField(
        name="recipe_category",
        type=SearchFieldDataType.String,
        filterable=True,
        analyzer_name="en.microsoft",
    ),
    SearchableField(
        name="recipe_name",
        type=SearchFieldDataType.String,
        facetable=True,
        analyzer_name="en.microsoft",
    ),
    SearchableField(
        name="ingredients",
        collection=True,
        type=SearchFieldDataType.String,
        facetable=True,
        filterable=True,
    ),
    SearchableField(
        name="recipe", type=SearchFieldDataType.String, analyzer_name="en.microsoft"
    ),
    SearchableField(
        name="description",
        type=SearchFieldDataType.String,
        analyzer_name="en.microsoft",
    ),
    SimpleField(
        name="total_time",
        type=SearchFieldDataType.Int32,
        filterable=True,
        facetable=True,
    ),
    SearchField(
        name="recipe_vector",
        type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
        searchable=True,
        vector_search_dimensions=1536,
        vector_search_configuration="my-vector-config",
    ),
]

vector_search = VectorSearch(
    algorithm_configurations=[
        HnswVectorSearchAlgorithmConfiguration(name="my-vector-config", kind="hnsw")
    ]
)

# Semantic Configuration to leverage Bing family of ML models for re-ranking (L2)
semantic_config = SemanticConfiguration(
    name="my-semantic-config",
    prioritized_fields=PrioritizedFields(
        title_field=None,
        prioritized_keywords_fields=[],
        prioritized_content_fields=[SemanticField(field_name="recipe")],
    ),
)
semantic_settings = SemanticSettings(configurations=[semantic_config])

# Create the search index with the semantic settings
index = SearchIndex(
    name=index_name,
    fields=fields,
    vector_search=vector_search,
    semantic_settings=semantic_settings,
)
result = index_client.delete_index(index)
print(f" {index_name} deleted")
result = index_client.create_index(index)
print(f" {result.name} created")


# Function to generate embeddings for title and content fields, also used for query embeddings
@retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(6))
def generate_embeddings(text):
    response = client.embeddings.create(
        input=text,
        model="text-embedding-ada-002",
    )
    embeddings = response.data[0].embedding
    return embeddings


batch_size = 100
counter = 0
documents = []
search_client = SearchClient(
    endpoint=service_endpoint, index_name=index_name, credential=credential
)

with open("recipes.jsonl", "r") as j_in:
    for line in j_in:
        counter += 1
        json_recipe = json.loads(line)
        json_recipe["total_time"] = int(json_recipe["total_time"].split(" ")[0])
        json_recipe["recipe_vector"] = generate_embeddings(json_recipe["recipe"])
        json_recipe["@search.action"] = "upload"
        documents.append(json_recipe)
        if counter % batch_size == 0:
            # Load content into index
            result = search_client.upload_documents(documents)
            print(f"Uploaded {len(documents)} documents")
            documents = []


if documents != []:
    # Load content into index
    result = search_client.upload_documents(
        documents)
    print(f"Uploaded {len(documents)} documents")
