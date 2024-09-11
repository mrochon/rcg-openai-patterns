import os
import json
from dotenv import load_dotenv
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SimpleField,
    SearchFieldDataType,
    SearchableField,
    SearchField,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    SemanticConfiguration,
    SemanticPrioritizedFields,
    SemanticField,
    SemanticSearch,
    SearchIndex,
    AzureOpenAIVectorizer,
    AzureOpenAIParameters,
)

# Load environment variables
load_dotenv(override=True)

# Set up the environment variables for Azure Search and OpenAI
endpoint = os.environ["AZURE_SEARCH_SERVICE_ENDPOINT"]
credential = AzureKeyCredential(os.getenv("AZURE_SEARCH_ADMIN_KEY"))
index_name = os.getenv("AZURE_SEARCH_INDEX", "vectest")
azure_openai_endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
azure_openai_key = os.getenv("AZURE_OPENAI_API_KEY")
azure_openai_embedding_deployment = os.getenv(
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME", "text-embedding-ada-002"
)
azure_openai_embedding_dimensions = int(
    os.getenv("AZURE_OPENAI_EMBEDDING_DIMENSIONS", 1536)
)
embedding_model_name = os.getenv(
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002"
)
azure_openai_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01")

# Initialize the AzureOpenAI client
client = AzureOpenAI(
    azure_deployment=azure_openai_embedding_deployment,
    api_version=azure_openai_api_version,
    azure_endpoint=azure_openai_endpoint,
    api_key=azure_openai_key,
)

# Create a search index client
index_client = SearchIndexClient(endpoint=endpoint, credential=credential)

# Define the fields for the search index
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
        vector_search_dimensions=azure_openai_embedding_dimensions,
        vector_search_profile_name="myHnswProfile",
    ),
]

# Configure the vector search algorithm and profile
vector_search = VectorSearch(
    algorithms=[HnswAlgorithmConfiguration(name="myHnsw")],
    profiles=[
        VectorSearchProfile(
            name="myHnswProfile",
            algorithm_configuration_name="myHnsw",
            vectorizer="myVectorizer",
        )
    ],
    vectorizers=[
        AzureOpenAIVectorizer(
            name="myVectorizer",
            azure_open_ai_parameters=AzureOpenAIParameters(
                resource_uri=azure_openai_endpoint,
                deployment_id=azure_openai_embedding_deployment,
                model_name=embedding_model_name,
                api_key=azure_openai_key,
            ),
        )
    ],
)

# Semantic configuration for re-ranking
semantic_config = SemanticConfiguration(
    name="my-semantic-config",
    prioritized_fields=SemanticPrioritizedFields(
        title_field=SemanticField(field_name="recipe_name"),
        keywords_fields=[SemanticField(field_name="recipe_category")],
        content_fields=[SemanticField(field_name="recipe")],
    ),
)

# Create the search index with semantic search
index = SearchIndex(
    name=index_name,
    fields=fields,
    vector_search=vector_search,
    semantic_search=SemanticSearch(configurations=[semantic_config]),
)

# Delete existing index (if exists) and create new index
try:
    index_client.delete_index(index_name)
    print(f"{index_name} deleted")
except Exception as e:
    print(f"Error deleting index: {e}")

result = index_client.create_or_update_index(index)
print(f"{result.name} created")

# Generate embeddings and upload documents
from azure.search.documents import SearchClient


# Define a function to generate document embeddings
def generate_embeddings(text):
    response = client.embeddings.create(input=text, model=embedding_model_name)
    embeddings = response.data[0].embedding
    return embeddings


# Load your data, generate embeddings, and prepare documents for upload from JSONL file
input_file = "recipes.jsonl"
documents = []
with open(input_file, "r", encoding="utf-8") as file:
    for line in file:
        json_recipe = json.loads(line)
        json_recipe["total_time"] = int(json_recipe["total_time"].split(" ")[0])
        json_recipe["recipe_vector"] = generate_embeddings(json_recipe["recipe"])
        json_recipe["@search.action"] = "upload"
        documents.append(json_recipe)

# Upload the documents to the search index
search_client = SearchClient(
    endpoint=endpoint, index_name=index_name, credential=credential
)
result = search_client.upload_documents(documents)
print(f"Uploaded {len(documents)} documents")
