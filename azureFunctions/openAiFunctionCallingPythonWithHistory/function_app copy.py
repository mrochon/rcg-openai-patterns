import os
import json
import random
from dotenv import load_dotenv
import logging
import requests
from tools import mytools
import azure.functions as func
from openai import AzureOpenAI
from azure.cosmos import CosmosClient, PartitionKey

load_dotenv()

azure_endpoint = os.getenv("AZURE_ENDPOINT")
api_key = os.getenv("API_KEY")
api_version = os.getenv("API_VERSION")
deployment = os.getenv("DEPLOYMENT")
cosmos_endpoint = os.getenv("COSMOS_ENDPOINT")
cosmos_key = os.getenv("COSMOS_KEY")
cosmos_database_name = os.getenv("COSMOS_DATABASE_NAME")
cosmos_container_name = os.getenv("COSMOS_CONTAINER_NAME")

client = AzureOpenAI(
    azure_endpoint=azure_endpoint,
    api_key=api_key,
    api_version=api_version,
)

cosmos_client = CosmosClient(cosmos_endpoint, cosmos_key)
database = cosmos_client.create_database_if_not_exists(id=cosmos_database_name)
container = database.create_container_if_not_exists(
    id=cosmos_container_name,
    partition_key=PartitionKey(path="/aadObjectId"),
    offer_throughput=400,
)


def get_stock_price(symbol):
    """Get the current stock information for a given stock symbol. Only Stock symbol supported is IBM"""
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey=demo"
    r = requests.get(url)
    data = r.json()
    return json.dumps(data)


def get_good_emails(howMany=1, file_path="./emailsGood.jsonl"):
    """Get good and high quality email examples that have been used in the past"""
    emails = []
    with open(file_path, "r") as f:
        for line in f:
            emails.append(json.loads(line))
    selected_emails = random.sample(emails, min(howMany, len(emails)))
    selected_contents = [email["content"][0] for email in selected_emails]
    return json.dumps({"goodEmails": selected_contents})


def get_bad_emails(howMany=1, file_path="./emailsBad.jsonl"):
    """Get bad and low quality email examples that have been used in the past"""
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
    query = f"SELECT * FROM c WHERE c.aadObjectId = '{aadObjectId}' ORDER BY c._ts DESC OFFSET 0 LIMIT {limit}"
    items = list(container.query_items(query=query, enable_cross_partition_query=True))
    history = []
    for item in items:
        history.append({"role": "user", "content": item.get("question")})
        history.append({"role": "assistant", "content": item.get("answer")})
    return history


def store_conversation(aadObjectId, question, answer):
    container.upsert_item(
        {"aadObjectId": aadObjectId, "question": question, "answer": answer}
    )


def run_conversation(aadObjectId, user_message):
    system_prompt = read_system_prompt()
    good_emails_json = get_good_emails(2)
    good_emails = json.loads(good_emails_json)["goodEmails"]
    system_prompt += (
        "\n\nConsider below sample emails json array while generating new emails:\n"
        + json.dumps(good_emails, indent=4)
    )

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        }
    ]

    # Retrieve and append conversation history
    conversation_history = get_conversation_history(aadObjectId)
    messages.extend(conversation_history)

    messages.append(
        {
            "role": "user",
            "content": user_message,
        }
    )

    response = client.chat_completions.create(model=deployment, messages=messages)
    response_message = response.choices[0].message
    tool_calls = (
        response_message.tool_calls if hasattr(response_message, "tool_calls") else []
    )

    logging.info("tool_calls: %s", tool_calls)

    if tool_calls:
        available_functions = {
            "get_stock_price": get_stock_price,
            "get_good_emails": get_good_emails,
            "get_bad_emails": get_bad_emails,
        }
        messages.append(response_message)
        for tool_call in tool_calls:
            function_name = tool_call["function"]["name"]
            function_to_call = available_functions[function_name]
            function_args = json.loads(tool_call["function"]["arguments"])
            function_response = function_to_call(**function_args)
            messages.append(
                {
                    "tool_call_id": tool_call["id"],
                    "role": "tool",
                    "name": function_name,
                    "content": function_response,
                }
            )
        logging.info("messages: %s", messages)
        second_response = client.chat_completions.create(
            model=deployment, messages=messages
        )
        answer = second_response.choices[0].message.content
    else:
        answer = response_message.content

    # Store the conversation in Cosmos DB
    store_conversation(aadObjectId, user_message, answer)

    return answer


app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.route(route="chat")
def chat(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Python HTTP trigger function processed a request.")

    try:
        req_body = req.get_json()
        aadObjectId = req_body.get("aadObjectId")
        user_message = req_body.get("question")
        if not user_message:
            return func.HttpResponse(
                "Invalid request body. 'question' is required.", status_code=400
            )

        response_content = run_conversation(aadObjectId, user_message)
        return func.HttpResponse(
            response_content, status_code=200, mimetype="application/json"
        )

    except ValueError:
        return func.HttpResponse("Invalid request body.", status_code=400)
