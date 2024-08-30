import os
import base64
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
from openai import AzureOpenAI

# Load environment variables from the .env file
load_dotenv()

# Set up Azure Blob Storage connection
connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
container_name = os.getenv("AZIRE_STORAGE_CONTAINER")

blob_service_client = BlobServiceClient.from_connection_string(connection_string)


client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2023-12-01-preview",
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
)

def load_prompt(file_path):
    """Load the system prompt from a text file."""
    with open(file_path, "r") as file:
        return file.read()


def find_latest_png(container_client):
    """Find the latest PNG file in the container."""
    blobs = container_client.list_blobs()
    latest_blob = None
    for blob in blobs:
        if blob.name.endswith(".png"):
            if latest_blob is None or blob.last_modified > latest_blob.last_modified:
                latest_blob = blob

    print(latest_blob)
    return latest_blob


def download_blob(container_client, blob_name, download_file_path):
    """Download a blob to a local file."""
    blob_client = container_client.get_blob_client(blob_name)
    with open(download_file_path, "wb") as download_file:
        download_file.write(blob_client.download_blob().readall())
    return download_file_path


def send_image_to_openai(image_path, system_prompt):
    """Send the image and a system prompt to OpenAI's API."""
    print(image_path)

    with open(image_path, "rb") as image_file:
        # Encode the image data in Base64
        image_base64 = base64.b64encode(image_file.read()).decode("utf-8")

        # Make the API request
        response = client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            # temperature=float(os.environ.get("CHART_PROCESSOR_TEMPERATURE")), # if needed you can set the temperature and top_p from the environment variables
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

        return response.choices[0].message.content.strip()


def main():
    # Create a directory for the downloaded images
    image_dir = "./localImageStore"
    if not os.path.exists(image_dir):
        os.makedirs(image_dir)

    container_client = blob_service_client.get_container_client(container_name)

    # Find the latest PNG file
    latest_blob = find_latest_png(container_client)
    if not latest_blob:
        print("No PNG files found in the container.")
        return

    print(f"Latest PNG file: {latest_blob.name}")

    # Define the download path in the chartImages directory
    download_path = os.path.join(image_dir, latest_blob.name)
    download_blob(container_client, latest_blob.name, download_path)
    print(f"Downloaded the latest PNG file to: {download_path}")

    # Define your system prompt
    system_prompt = load_prompt("imageAnalyzerSystemPrompt.txt")

    # Send the image and system prompt to OpenAI
    response = send_image_to_openai(download_path, system_prompt)
    print(f"OpenAI response: {response}")

    return response


if __name__ == "__main__":
    main()
