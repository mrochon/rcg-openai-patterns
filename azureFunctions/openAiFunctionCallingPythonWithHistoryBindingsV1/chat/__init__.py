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

client = AzureOpenAI(
    azure_endpoint=azure_endpoint,
    api_key=api_key,
    api_version=api_version,
)


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


def main(
    req: func.HttpRequest,
    conversationHistory: func.DocumentList,
    systemPrompts: func.DocumentList,
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
        question = req_body.get("question")
        # get aadObjectId from the reque url
        aadObjectId = req.route_params.get("aadObjectId")

        if not question or not aadObjectId:
            return func.HttpResponse(
                "Invalid request body. 'aadObjectId' and 'question' are required.",
                status_code=400,
            )

        # Prepare conversation history
        history = []
        for item in conversationHistory:
            history.append({"role": "user", "content": item.get("question")})
            history.append({"role": "assistant", "content": item.get("answer")})
            print(item.get("question"), item.get("answer"))

        # Prepare OpenAI prompt
        system_prompt = system_prompt_text
        good_emails_json = get_good_emails(2)
        good_emails = json.loads(good_emails_json)["goodEmails"]
        system_prompt += (
            "\n\nConsider below sample emails json array while generating new emails:\n"
            + json.dumps(good_emails, indent=4)
        )

        # Prepare OpenAI messages
        messages = [
            {"role": "system", "content": system_prompt},
            *history,
            {"role": "user", "content": question},
        ]

        # Call OpenAI chat completion
        response = client.chat.completions.create(
            model=deployment,
            messages=messages,
            tools=mytools,
            tool_choice="auto"
        )
        response_message = response.choices[0].message
        response_content = response_message.content
        tool_calls = response_message.tool_calls

        # Handle tool calls
        if tool_calls:
            available_functions = {
                "get_good_emails": get_good_emails,
                "get_bad_emails": get_bad_emails,
            }
            messages.append(response_message)
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                function_to_call = available_functions.get(function_name)
                function_args = json.loads(tool_call.function.arguments)
                try:
                    function_response = function_to_call(**function_args)
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
        conversationOutput.set(output_document)  # Set output for Cosmos DB binding

        return func.HttpResponse(
            json.dumps({"response": response_content}),
            status_code=200,
            mimetype="application/json",
        )

    except ValueError:
        return func.HttpResponse("Invalid request body.", status_code=400)
