import os
import json
import random
from dotenv import load_dotenv
import logging
import requests
from openai import AzureOpenAI
from azure.cosmos import CosmosClient, PartitionKey
from tools import mytools
import uuid

# Load environment variables from .env file

load_dotenv(
    dotenv_path="./module1/.env"
)
# Retrieve Azure and CosmosDB credentials from the environment variables
azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
api_key = os.getenv("AZURE_OPENAI_API_KEY")
api_version = os.getenv("AZURE_OPENAI_API_VERSION")
deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

cosmos_endpoint = os.getenv("AZURE_COSMOS_ENDPOINT")
cosmos_key = os.getenv("AZURE_COSMOS_KEY")
cosmos_database_name = os.getenv("AZURE_COSMOS_DB_NAME")
cosmos_container_name = os.getenv("AZURE_COSMOS_CONTAINER_NAME")

# Initialize OpenAI client
client = AzureOpenAI(
    azure_endpoint=azure_endpoint,
    api_key=api_key,
    api_version=api_version,
)

# Initialize Cosmos DB client and container
cosmos_client = CosmosClient(cosmos_endpoint, cosmos_key)
database = cosmos_client.create_database_if_not_exists(id=cosmos_database_name)
container = database.create_container_if_not_exists(
    id=cosmos_container_name,
    partition_key=PartitionKey(path="/aadObjectId"),
    offer_throughput=400,
)


def get_stock_price(symbol):
    """Get the current stock information for a given stock symbol."""
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey=demo"
    r = requests.get(url)
    data = r.json()
    return json.dumps(data)


def get_good_feedback(howMany=1, file_path="./feedbackGood.jsonl"):
    """Get good and low-quality feedback."""
    emails = []
    with open(file_path, "r") as f:
        for line in f:
            emails.append(json.loads(line))
    selected_emails = random.sample(emails, min(howMany, len(emails)))
    selected_contents = [email["content"][0] for email in selected_emails]
    return json.dumps({"goodFeedback": selected_contents})


def get_bad_feedback(howMany=1, file_path="./feedbackBad.jsonl"):
    """Get bad and low-quality feedback."""
    emails = []
    with open(file_path, "r") as f:
        for line in f:
            emails.append(json.loads(line))
    selected_emails = random.sample(emails, min(howMany, len(emails)))
    selected_contents = [email["content"][0] for email in selected_emails]
    return json.dumps({"badEmails": selected_contents})


def read_system_prompt(file_path="systemPrompt.txt"):
    """Read the system prompt from a file."""
    with open(file_path, "r") as file:
        return file.read().strip()


def get_conversation_history(aadObjectId, limit=5):
    """Retrieve conversation history from Cosmos DB."""
    query = f"SELECT * FROM c WHERE c.aadObjectId = '{aadObjectId}' ORDER BY c._ts DESC OFFSET 0 LIMIT {limit}"
    items = list(container.query_items(query=query, enable_cross_partition_query=True))
    history = []
    for item in items:
        history.append({"role": "user", "content": item.get("question")})
        history.append({"role": "assistant", "content": item.get("answer")})
    return history


def store_conversation(aadObjectId, question, answer):
    """Store the conversation in Cosmos DB."""
    item_id = str(uuid.uuid4())
    container.upsert_item(
        {
            "id": item_id,  # Required unique ID field
            "aadObjectId": aadObjectId,  # Partition key field
            "question": question,
            "answer": answer,
        }
    )


def run_conversation(aadObjectId, user_message):
    """Run the conversation flow."""
    system_prompt = read_system_prompt()
    good_emails_json = get_good_feedback()
    good_emails = json.loads(good_emails_json)["goodFeedback"]
    system_prompt += (
        "\n\nConsider below sample emails json array while generating new emails:\n"
        + json.dumps(good_emails, indent=4)
    )

    # Build the message sequence
    messages = [
        {
            "role": "system",
            "content": system_prompt,
        }
    ]

    # Retrieve and append conversation history
    conversation_history = get_conversation_history(aadObjectId)
    messages.extend(conversation_history)

    # Add the user's new message
    messages.append(
        {
            "role": "user",
            "content": user_message,
        }
    )
    # print("response")
    # Generate a response using Azure OpenAI
    response = client.chat.completions.create(
        model=deployment,
        messages=messages,
        tools=mytools,
        tool_choice="auto",  # auto is default, but we'll be explicit
    )
    print("----------------")
    print("----------------")
    print(response)
    print("----------------")
    print("----------------")
    # print(response)
    response_message = response.choices[0].message
    tool_calls = (
        response_message.tool_calls if hasattr(response_message, "tool_calls") else []
    )

    logging.info("tool_calls: %s", tool_calls)
    print("tool_calls", tool_calls)
    if tool_calls:
        available_functions = {
            "get_stock_price": get_stock_price,
            "get_good_feedback": get_good_feedback,
            "get_bad_feedback": get_bad_feedback,
        }
        messages.append(response_message)
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            function_to_call = available_functions[function_name]
            function_args = json.loads(tool_call.function.arguments)
            function_response = function_to_call(**function_args)
            messages.append(
                {
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": function_response,
                }
            )
        logging.info("messages: %s", messages)
        second_response = client.chat.completions.create(
            model=deployment,
            messages=messages,
        )
        answer = second_response.choices[0].message.content
    else:
        answer = response_message.content

    # Store the conversation in Cosmos DB
    store_conversation(aadObjectId, user_message, answer)

    return answer


if __name__ == "__main__":
    aadObjectId = input("Enter user AAD Object ID: ")
    # user_message = input("Enter your message: ")
    user_message = "what is the stock price of IBM?"
    response = run_conversation(aadObjectId, user_message)
    print("----------------")
    print("----------------")
    print("Response from assistant:", response)
