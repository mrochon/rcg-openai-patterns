import os
import io
import requests
import json
from azure.core.credentials import AzureKeyCredential
from openai import AzureOpenAI
from dotenv import load_dotenv
from tenacity import retry, wait_random_exponential, stop_after_attempt
import re

# Load environment variables for Azure services
service_endpoint = os.getenv("AZURE_SEARCH_SERVICE_ENDPOINT")
credential = AzureKeyCredential(os.getenv("AZURE_SEARCH_ADMIN_KEY"))
index_name = os.getenv("AZURE_SEARCH_INDEX3")

azure_openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
azure_openai_api_key = os.getenv("AZURE_OPENAI_API_KEY")
embedding_model_deployment_name = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME")
embedding_model_name = os.getenv("AZURE_OPENAI_EMBEDDING_MODEL_NAME")
azure_openai_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01")

