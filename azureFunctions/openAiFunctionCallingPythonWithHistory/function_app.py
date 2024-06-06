import os
import json
import random
from dotenv import load_dotenv
import logging
import requests
import uuid
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

cosmos_client = CosmosClient(cosmos_endpoint, cosmos_key)
database = cosmos_client.create_database_if_not_exists(id=cosmos_database_name)
container = database.create_container_if_not_exists(
    id=cosmos_container_name,
    partition_key=PartitionKey(path="/aadObjectId"),
)

client = AzureOpenAI(
    azure_endpoint=azure_endpoint,
    api_key=api_key,
    api_version=api_version,
)


def get_stock_price(symbol):
    """Get the current stock information for a given stock symbol. Only Stock symbol supported is IBM"""
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey=demo"

    r = requests.get(url)
    data = r.json()
    # return data as string
    return json.dumps(data)


def get_good_emails(howMany=1, file_path="./emailsGood.jsonl"):
    """Get good and high quality email examples that have been used in the past"""
    emails = []

    # Read the JSONL file
    with open(file_path, "r") as f:
        for line in f:
            emails.append(json.loads(line))

    # Randomly select the specified number of emails
    selected_emails = random.sample(emails, min(howMany, len(emails)))

    # Extract content from selected emails
    selected_contents = [email["content"][0] for email in selected_emails]

    # Return the selected emails in the required format
    return json.dumps({"goodEmails": selected_contents})


def get_bad_emails(howMany=1, file_path="./emailsBad.jsonl"):
    """Get bad and low quality email examples that have been used in the past"""
    emails = []

    # Read the JSONL file
    with open(file_path, "r") as f:
        for line in f:
            emails.append(json.loads(line))

    # Randomly select the specified number of emails
    selected_emails = random.sample(emails, min(howMany, len(emails)))

    # Extract content from selected emails
    selected_contents = [email["content"][0] for email in selected_emails]

    # Return the selected emails in the required format
    return json.dumps({"goodEmails": selected_contents})


def read_system_prompt(file_path="systemPrompt.txt"):
    """Read the system prompt from a file."""
    with open(file_path, "r") as file:
        return file.read().strip()


def get_conversation_history(aadObjectId, limit=5):
    query = "SELECT * FROM c WHERE c.aadObjectId = @aadObjectId ORDER BY c._ts DESC OFFSET 0 LIMIT @limit"
    parameters = [
        {"name": "@aadObjectId", "value": aadObjectId},
        {"name": "@limit", "value": limit},
    ]
    items = list(
        container.query_items(
            query=query, parameters=parameters, enable_cross_partition_query=True
        )
    )
    history = []
    for item in items:
        history.append({"role": "user", "content": item.get("question")})
        history.append({"role": "assistant", "content": item.get("answer")})
    return history


def store_conversation(aadObjectId, question, answer):
    if not aadObjectId or not question or not answer:
        logging.error("One of the inputs is None or empty.")
        return

    if (
        not isinstance(aadObjectId, str)
        or not isinstance(question, str)
        or not isinstance(answer, str)
    ):
        logging.error("One of the inputs is not a string.")
        return

    item = {
        "id": str(uuid.uuid4()),  # Unique identifier for the item
        "aadObjectId": aadObjectId,
        "question": question,
        "answer": answer,
    }

    try:
        container.upsert_item(item)
        logging.info("Item upserted successfully.")
    except Exception as e:
        logging.error(f"An error occurred while upserting the item: {e}")


def run_conversation(user_message, aadObjectId):
    # Read the system prompt
    system_prompt = read_system_prompt()

    # Get examples of good emails
    good_emails_json = get_good_emails(2)
    good_emails = json.loads(good_emails_json)["goodEmails"]

    # Append email examples to the system prompt
    system_prompt += (
        "\n\nConsider below sample emails json array while generating new emails:\n"
        + json.dumps(good_emails, indent=4)
    )

    # Step 1: send the conversation and available functions to the model
    # Initialize the messages list with the system message
    messages = [
        {
            "role": "system",
            "content": system_prompt,
        }
    ]

    # Retrieve and append conversation history
    conversation_history = get_conversation_history(aadObjectId)
    # reverse the conversation history to get the last user message
    conversation_history.reverse()
    
    messages.extend(conversation_history)

    # Append the user message
    messages.append(
        {
            "role": "user",
            "content": user_message,
        }
    )
    
    print(messages)

    response = client.chat.completions.create(
        model=deployment,
        messages=messages,
        tools=mytools,
        tool_choice="auto",  # auto is default, but we'll be explicit
    )
    response_message = response.choices[0].message
    tool_calls = response_message.tool_calls

    # Print the tool calls for debugging
    logging.info("tool_calls")
    logging.info(tool_calls)
    logging.info("tool_calls")
    # Step 2: check if the model wanted to call a function
    if tool_calls:
        # Step 3: call the function
        # Note: the JSON response may not always be valid; be sure to handle errors
        available_functions = {
            "get_stock_price": get_stock_price,
            "get_good_emails": get_good_emails,
            "get_bad_emails": get_bad_emails,
        }  # only one function in this example, but you can have multiple
        messages.append(response_message)  # extend conversation with assistant's reply
        # Step 4: send the info for each function call and function response to the model
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
            print("messages-------------------")
            print(messages)
            print("-------------------messages")
            # extend conversation with function response
        second_response = client.chat.completions.create(
            model=deployment,
            messages=messages,
        )  # get a new response from the model where it can see the function response
        return second_response.choices[0].message.content

    return response_message.content


app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


@app.route(route="chat")
def chat(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Python HTTP trigger function processed a request.")

    try:
        req_body = req.get_json()
        aadObjectId = req_body.get("aadObjectId")
        question = req_body.get("question")
        if not question:
            return func.HttpResponse(
                "Invalid request body. 'question' is required.", status_code=400
            )

        response_content = run_conversation(question, aadObjectId)

        store_conversation(aadObjectId, str(question), str(response_content))

        return func.HttpResponse(
            response_content, status_code=200, mimetype="application/json"
        )

    except ValueError:
        return func.HttpResponse("Invalid request body.", status_code=400)
