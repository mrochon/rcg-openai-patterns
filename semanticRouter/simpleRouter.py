import os
from dotenv import load_dotenv
from semantic_router import Route
from semantic_router.encoders import OpenAIEncoder
from semantic_router.layer import RouteLayer

# Load environment variables from .env file
load_dotenv(override=True)

# Retrieve credentials from environment
azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")


os.environ["OPENAI_API_KEY"] = os.getenv("AZURE_OPENAI_API_KEY")
os.environ["OPENAI_API_BASE"] = os.getenv("AZURE_OPENAI_ENDPOINT")
os.environ["OPENAI_API_VERSION"] = "2024-06-01"  # Use the appropriate API version
os.environ["OPENAI_API_VERSION"] = (
    "2024-06-01"  # Replace with your specific API version
)
os.environ["OPENAI_DEPLOYMENT_NAME"] = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
# Define routes
politics = Route(
    name="politics",
    utterances=[
        "isn't politics the best thing ever",
        "tell me your political opinions",
    ],
)
weather = Route(
    name="weather",
    utterances=["how's the weather today?", "tell me about today's forecast"],
)

# Initialize encoder with Azure OpenAI
encoder = OpenAIEncoder()


# Set up RouteLayer
route_layer = RouteLayer(encoder=encoder, routes=[politics, weather])

# Test routing
print(route_layer("How is the weather today?").name)  # Expected output: 'weather'
print(
    route_layer("What do you think of the new law?").name
)  # Expected output: 'politics'
