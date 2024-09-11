import os
import json
from openai import AzureOpenAI
from tenacity import retry, wait_random_exponential, stop_after_attempt
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.models import Vector
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

# print all environment variables
print("Service Endpoint: ", service_endpoint)
print("Credential: ", credential)
print("Index Name: ", index_name)
print("Azure OpenAI Endpoint: ", azure_openai_endpoint)
print("Azure OpenAI Key: ", azure_openai_key)
print("Azure OpenAI Embedding Deployment: ", azure_openai_embedding_deployment)
print("Embedding Model Name: ", embedding_model_name)
print("GPT Model Name: ", gpt_model_name)
print("Azure OpenAI API Version: ", azure_openai_api_version)


# Configure OpenAI environment variables
client = AzureOpenAI(
    azure_endpoint=azure_openai_endpoint,  # The base URL for your Azure OpenAI resource. e.g. "https://<your resource name>.openai.azure.com"
    api_key=azure_openai_key,  # The API key for your Azure OpenAI resource.
    api_version=azure_openai_api_version,  # This version supports function calling
)

# Create the Azure Cognitive Search client to issue queries
search_client = SearchClient(
    endpoint=service_endpoint, index_name=index_name, credential=credential
)


# Function to generate embeddings for title and content fields, also used for query embeddings
@retry(wait=wait_random_exponential(min=1, max=20), stop=stop_after_attempt(6))
def generate_embeddings(text):
    response = client.embeddings.create(
        input=text, model=azure_openai_embedding_deployment
    )
    embeddings = response.data[0].embedding
    return embeddings


model_name = gpt_model_name

messages = [{"role": "user", "content": "Help me find a good lasagna recipe."}]

tools = [
    {
        "type": "function",
        "function": {
            "name": "query_recipes",
            "description": "Retrieve recipes from the Azure Cognitive Search index",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The query string to search for recipes",
                    },
                    "ingredients_filter": {
                        "type": "string",
                        "description": "The odata filter to apply for the ingredients field. Only actual ingredient names should be used in this filter. If you're not sure something is an ingredient, don't include this filter. Example: ingredients/any(i: i eq 'salt' or i eq 'pepper')",
                    },
                    "time_filter": {
                        "type": "string",
                        "description": "The odata filter to apply for the total_time field. If a user asks for a quick or easy recipe, you should filter down to recipes that will take less than 30 minutes. Example: total_time lt 25",
                    },
                },
                "required": ["query"],
            },
        },
    }
]

response = client.chat.completions.create(
    model=model_name,
    messages=messages,
    tools=tools,
    temperature=0.2,
    tool_choice="auto",
)

print(response.choices[0].message)


def query_recipes(query, ingredients_filter=None, time_filter=None):
    print("I am in a function")
    # print all inputs
    print("Query: ", query)
    print("Ingredients Filter: ", ingredients_filter)
    print("Time Filter: ", time_filter)
    filter = ""
    if ingredients_filter and time_filter:
        filter = f"{time_filter} and {ingredients_filter}"
    elif ingredients_filter:
        filter = ingredients_filter
    elif time_filter:
        filter = time_filter
    print("I am looking for results")
    print("-----------------")
    results = search_client.search(
        query_type="semantic",
        query_language="en-us",
        semantic_configuration_name="my-semantic-config",
        search_text=query,
        vectors=[Vector(value=generate_embeddings(query), k=3, fields="recipe_vector")],
        filter=filter,
        select=["recipe_id", "recipe", "recipe_category", "recipe_name", "description"],
        top=3,
    )
    print("-----------------")
    print("I am DONE looking for results")
    n = 1
    recipes_for_prompt = ""
    for result in results:
        recipes_for_prompt += f"Recipe {result['recipe_id']}: {result['recipe_name']}: {result['description']}\n"
        n += 1
    print("I ended the Function")
    return recipes_for_prompt


def run_conversation(messages, tools, available_functions):

    # Step 1: send the conversation and available functions to GPT
    response = client.chat.completions.create(
        model=model_name,
        messages=messages,
        tools=tools,
        tool_choice="auto",
        temperature=0.2,
    )
    response_message = response.choices[0].message

    # Step 2: check if the model wants to call a function
    if response_message.tool_calls:
        print("Recommended Function call:")
        print(response_message.tool_calls[0])
        print()

        # Step 3: call the function
        # Note: the JSON response may not always be valid; be sure to handle errors
        function_name = response_message.tool_calls[0].function.name

        # verify function exists
        if function_name not in available_functions:
            return "Function " + function_name + " does not exist"
        function_to_call = available_functions[function_name]

        function_args = json.loads(response_message.tool_calls[0].function.arguments)
        function_response = function_to_call(**function_args)

        print("Output of function call:")
        print(function_response)
        print()

        # Step 4: send the info on the function call and function response to the model

        # adding assistant response to messages
        messages.append(
            {
                "role": response_message.role,
                "function_call": {
                    "name": response_message.tool_calls[0].function.name,
                    "arguments": response_message.tool_calls[0].function.arguments,
                },
                "content": None,
            }
        )

        # adding function response to messages
        messages.append(
            {
                "role": "function",
                "name": function_name,
                "content": function_response,
            }
        )  # extend conversation with function response

        print("Messages in second request:")
        for message in messages:
            print(message)
        print()
        print("HERE")
        second_response = client.chat.completions.create(
            model=model_name,
            messages=messages,
        )  # get a new response from GPT where it can see the function response

        return second_response
    else:
        return response


system_message = """Assistant is a large language model designed to help users find and create recipes.

You have access to an Azure Cognitive Search index with hundreds of recipes. You can search for recipes by name, ingredient, or cuisine.

You are designed to be an interactive assistant, so you can ask users clarifying questions to help them find the right recipe. It's better to give more detailed queries to the search index rather than vague one.
"""

messages = [
    {"role": "system", "content": system_message},
    {
        "role": "user",
        "content": "I want to make a pasta dish that takes less than 60 minutes to make.",
    },
]

available_functions = {"query_recipes": query_recipes}

result = run_conversation(messages, tools, available_functions)

print("Final response:")
print(result.choices[0].message.content)
