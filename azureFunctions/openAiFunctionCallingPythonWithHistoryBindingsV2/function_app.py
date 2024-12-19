import os
import json
import random
import logging
import uuid
from dotenv import load_dotenv
from tools import mytools
import azure.functions as func
from openai import AzureOpenAI

# Load environment variables
load_dotenv(override=True)

# Azure OpenAI configuration
azure_endpoint = os.getenv("AZURE_ENDPOINT")
api_key = os.getenv("API_KEY")
api_version = os.getenv("API_VERSION")
deployment = os.getenv("DEPLOYMENT")
bot_type = os.getenv("BOT_TYPE")
system_prompt_id = os.getenv("SYSTEM_PROMPT_ID", "default_value")

example_pool_endpoint = os.getenv("EXAMPLE_POOL", "default_value")


# www.data.com/emailsObs

client = AzureOpenAI(
    azure_endpoint=azure_endpoint,
    api_key=api_key,
    api_version=api_version,
)

app = func.FunctionApp()


def get_good_emails(howMany=1, file_path="./emailsGood.jsonl"):
    """Get good and high-quality email examples."""
    emails = []
    with open(file_path, "r") as f:
        for line in f:
            emails.append(json.loads(line))
    selected_emails = random.sample(emails, min(howMany, len(emails)))
    selected_contents = [email["content"][0] for email in selected_emails]
    return json.dumps({"goodEmails": selected_contents})


def get_bad_emails(howMany=1, file_path="./emailsBad.jsonl"):
    """Get bad and low-quality email examples."""
    emails = []
    with open(file_path, "r") as f:
        for line in f:
            emails.append(json.loads(line))
    selected_emails = random.sample(emails, min(howMany, len(emails)))
    selected_contents = [email["content"][0] for email in selected_emails]
    return json.dumps({"badEmails": selected_contents})

cosmos_prompt_query = (
    f"SELECT c.systemPromptText FROM c WHERE c.systemPromptId = '{system_prompt_id}'"
)


@app.route(route="chat", auth_level=func.AuthLevel.FUNCTION)
@app.cosmos_db_input(
    arg_name="conversationHistory",
    database_name="chatHistoryDb",
    container_name="chatHistoryContainer",
    connection="CosmosDBConnection",
    sql_query="SELECT * FROM c WHERE c.aadObjectId = {status} ORDER BY c._ts DESC OFFSET 0 LIMIT 3",
    partition_key="{status}",
    parameters=[
        {"name": "@aadUser", "value": "{aadUser}"},
        {"name": "@status", "value": "{status}"},
    ],
)
@app.cosmos_db_input(
    arg_name="systemPrompts",
    database_name="systemPromptsDb",
    container_name="systemPromptsContainer",
    connection="CosmosDBConnection",
    sql_query=cosmos_prompt_query,
)
@app.cosmos_db_output(
    arg_name="conversationOutput",
    database_name="chatHistoryDb",
    container_name="chatHistoryContainer",
    connection="CosmosDBConnection",
)
def chat(
    req: func.HttpRequest,
    systemPrompts: func.DocumentList,
    conversationHistory: func.DocumentList,
    conversationOutput: func.Out[func.Document],
) -> func.HttpResponse:
    logging.info("Processing chat request.")

    # Extract system prompt text
    system_prompt_text = None
    for doc in systemPrompts:
        doc_dict = json.loads(doc.to_json())
        system_prompt_text = doc_dict.get("systemPromptText")
        break

    if not system_prompt_text:
        return func.HttpResponse("System prompt not found.", status_code=500)

    try:
        req_body = req.get_json()
        aadObjectId = req.params.get("status")
        question = req_body.get("question")

        if not question or not aadObjectId:
            return func.HttpResponse(
                "Invalid request. 'status' and 'question' are required.",
                status_code=400,
            )

        # Reconstruct conversation history:
        # The query returns records in descending order.
        # We'll store them, then reverse so oldest is first.
        raw_history = []
        for item in conversationHistory:
            # Each item represents one turn (user + assistant answer)
            user_msg = item.get("question")
            assistant_msg = item.get("answer")
            timestamp = item.get("_ts")

            # Add these pairs as separate messages
            if user_msg:
                raw_history.append(
                    {"role": "user", "content": user_msg, "time": timestamp}
                )
            if assistant_msg:
                raw_history.append(
                    {"role": "assistant", "content": assistant_msg, "time": timestamp}
                )

        # Sort by time ascending to ensure correct chronological order
        raw_history.sort(key=lambda x: x["time"])

        # Prepare system prompt and reference emails
        system_prompt = system_prompt_text
        good_emails_json = get_good_emails(2)
        good_emails = json.loads(good_emails_json)["goodEmails"]
        system_prompt += (
            "\n\nConsider the sample emails JSON below while generating new emails:\n"
            + json.dumps(good_emails, indent=4)
        )

        # Construct the final message list for the model
        messages = [{"role": "system", "content": system_prompt}]
        # Add all previous conversation turns
        for msg in raw_history:
            messages.append({"role": msg["role"], "content": msg["content"]})
        # Add the latest user query
        messages.append({"role": "user", "content": question})

        # Call OpenAI chat completion
        response = client.chat.completions.create(
            model=deployment,
            messages=messages,
            tools=mytools,
            tool_choice="auto",
        )
        response_message = response.choices[0].message
        response_content = response_message.content
        tool_calls = response_message.tool_calls

        # Handle any tool calls
        if tool_calls:
            available_functions = {
                "get_good_emails": get_good_emails,
                "get_bad_emails": get_bad_emails,
            }
            messages.append(response_message)
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                try:
                    function_response = available_functions[function_name](
                        **function_args
                    )
                    messages.append(
                        {
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": function_response,
                        }
                    )
                except Exception as e:
                    logging.error(
                        f"Exception occurred during the {function_name} function call: {e}"
                    )
            # Call the model again with new tool response messages
            second_response = client.chat.completions.create(
                model=deployment,
                messages=messages,
            )
            response_content = second_response.choices[0].message.content

        # Prepare conversation output
        output_document = func.Document.from_json(
            json.dumps(
                {
                    "id": str(uuid.uuid4()),
                    "aadObjectId": aadObjectId,
                    "question": question,
                    "answer": response_content,
                }
            )
        )
        print("=="*50)
        print("output_document")
        print(output_document)
        conversationOutput.set(output_document)  # Set output for Cosmos DB binding

        return func.HttpResponse(
            json.dumps({"response": response_content}),
            status_code=200,
            mimetype="application/json",
        )

    except ValueError:
        return func.HttpResponse("Invalid request body.", status_code=400)
