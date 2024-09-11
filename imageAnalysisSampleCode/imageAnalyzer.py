import os
import base64
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
from openai import AzureOpenAI

# Load environment variables from the .env file and overwrite existing ones
load_dotenv(override=True)

# Set up Azure Blob Storage connection using the connection string from environment variables
connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
container_name = os.getenv("AZIRE_STORAGE_CONTAINER")
print(f"Container name: {container_name}")
print(f"Connection string: {connection_string}")
blob_service_client = BlobServiceClient.from_connection_string(connection_string)

# Set up Azure OpenAI client using credentials from environment variables
client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2023-12-01-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
)


def load_prompt(file_path):
    """
    Load the system prompt from a text file.

    Args:
        file_path (str): The path to the text file containing the prompt.

    Returns:
        str: The content of the prompt file as a string.
    """
    with open(file_path, "r") as file:
        return file.read()


def find_latest_png(container_client):
    """
    Find the most recently modified PNG file in the Azure Blob Storage container.

    Args:
        container_client: The BlobServiceClient container client.

    Returns:
        latest_blob: The latest PNG blob object, or None if no PNG files are found.
    """
    blobs = container_client.list_blobs()
    latest_blob = None
    for blob in blobs:
        if blob.name.endswith(".png"):
            if latest_blob is None or blob.last_modified > latest_blob.last_modified:
                latest_blob = blob

    # Debug output for the latest blob found
    print(latest_blob)
    return latest_blob


def download_blob(container_client, blob_name, download_file_path):
    """
    Download a specific blob from Azure Blob Storage to a local file.

    Args:
        container_client: The BlobServiceClient container client.
        blob_name (str): The name of the blob to download.
        download_file_path (str): The local file path to save the downloaded blob.

    Returns:
        str: The path to the downloaded file.
    """
    blob_client = container_client.get_blob_client(blob_name)
    with open(download_file_path, "wb") as download_file:
        download_file.write(blob_client.download_blob().readall())
    return download_file_path


def send_image_to_openai(image_path, system_prompt):
    """
    Send the image and a system prompt to OpenAI's API for analysis.

    Args:
        image_path (str): The path to the image file to be analyzed.
        system_prompt (str): The system prompt to guide the analysis.

    Returns:
        str: The content of the OpenAI response.
    """
    print(image_path)

    with open(image_path, "rb") as image_file:
        # Encode the image data to Base64 format
        image_base64 = base64.b64encode(image_file.read()).decode("utf-8")

        # Make the API request to OpenAI with the system prompt and image data
        response = client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            # Uncomment and set the temperature and top_p if needed from environment variables
            # temperature=float(os.environ.get("CHART_PROCESSOR_TEMPERATURE")),
            # top_p=float(os.environ.get("CHART_PROCESSOR_P")),
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Image: "},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            },
                        },
                    ],
                },
            ],
        )

        # Return the response content from OpenAI
        return response.choices[0].message.content.strip()


def main():
    """
    Main function to orchestrate the process:
    - Create a local directory for storing images.
    - Find and download the latest PNG image from Azure Blob Storage.
    - Send the image along with a system prompt to OpenAI for analysis.
    """
    # Directory for storing downloaded images
    image_dir = "./localImageStore"
    if not os.path.exists(image_dir):
        os.makedirs(image_dir)

    container_client = blob_service_client.get_container_client(container_name)

    # Find the most recent PNG file in the Blob Storage container
    latest_blob = find_latest_png(container_client)
    if not latest_blob:
        print("No PNG files found in the container.")
        return

    print(f"Latest PNG file: {latest_blob.name}")

    # Define the path where the image will be downloaded locally
    download_path = os.path.join(image_dir, latest_blob.name)
    download_blob(container_client, latest_blob.name, download_path)
    print(f"Downloaded the latest PNG file to: {download_path}")

    # Load the system prompt from a text file
    system_prompt = load_prompt("imageAnalyzerSystemPrompt.txt")

    # Send the image and prompt to OpenAI for analysis and print the response
    response = send_image_to_openai(download_path, system_prompt)
    print(f"OpenAI response: {response}")

    return response


# Execute the main function when the script is run directly
if __name__ == "__main__":
    main()
