import uuid
from datetime import datetime
from azure.storage.blob.aio import BlobServiceClient
import os
import json
import logging


class AzureBlobConversationClient:

    def __init__(
        self,
        connection_string: str,
        container_name: str,
        enable_message_feedback: bool = False,
    ):
        self.connection_string = connection_string
        self.container_name = container_name
        self.enable_message_feedback = enable_message_feedback

        try:
            # Initialize BlobServiceClient using connection string
            self.blob_service_client = BlobServiceClient.from_connection_string(
                connection_string, connection_verify=False
            )
            self.container_client = self.blob_service_client.get_container_client(
                container_name
            )
        except Exception as e:
            logging.error(f"Failed to initialize Azure Blob Storage client: {str(e)}")
            raise ValueError("Failed to initialize Azure Blob Storage client") from e

    async def ensure(self):
        """Ensure the container exists."""
        try:
            await self.container_client.create_container()
        except Exception as e:
            if "ContainerAlreadyExists" not in str(e):
                logging.error(f"Error ensuring container exists: {str(e)}")
                raise
        return True, "Azure Blob Storage client initialized successfully"

    async def create_conversation(self, user_id, title=""):
        conversation = {
            "id": str(uuid.uuid4()),
            "type": "conversation",
            "createdAt": datetime.utcnow().isoformat(),
            "updatedAt": datetime.utcnow().isoformat(),
            "userId": user_id,
            "title": title,
            "messages": [],  # Initialize with an empty list of messages
        }
        try:
            # Store conversation in the user-specific folder
            blob_name = f"{str(user_id)}/{str(conversation['id'])}/conversation.json"
            blob_client = self.container_client.get_blob_client(blob_name)
            await blob_client.upload_blob(json.dumps(conversation), overwrite=True)
            logging.info(
                f"Conversation {conversation['id']} stored in blob {blob_name}."
            )
            return conversation
        except Exception as e:
            logging.error(f"Failed to create conversation: {str(e)}")
            return False

    async def upsert_conversation(self, conversation):
        try:
            # Update the conversation within the user folder
            blob_name = f"{str(conversation['userId'])}/{str(conversation['id'])}/conversation.json"
            blob_client = self.container_client.get_blob_client(blob_name)
            conversation["updatedAt"] = datetime.utcnow().isoformat()
            await blob_client.upload_blob(json.dumps(conversation), overwrite=True)
            return conversation
        except Exception as e:
            logging.error(f"Failed to upsert conversation: {str(e)}")
            return False

    async def delete_conversation(self, user_id, conversation_id):
        try:
            blob_name = f"{str(user_id)}/{str(conversation_id)}/conversation.json"
            blob_client = self.container_client.get_blob_client(blob_name)
            await blob_client.delete_blob()
            logging.info(
                f"Conversation {conversation_id} deleted from blob {blob_name}."
            )
            return True
        except Exception as e:
            logging.error(f"Failed to delete conversation: {str(e)}")
            return False

    async def create_message(self, uuid, conversation_id, user_id, input_message: dict):
        message = {
            "id": uuid,
            "type": "message",
            "userId": user_id,
            "createdAt": datetime.utcnow().isoformat(),
            "updatedAt": datetime.utcnow().isoformat(),
            "conversationId": conversation_id,
            "role": input_message["role"],
            "content": input_message["content"],
        }

        if self.enable_message_feedback:
            message["feedback"] = ""

        try:
            # Fetch the existing conversation and append the new message
            conversation = await self.get_conversation(user_id, conversation_id)
            if not conversation:
                return "Conversation not found"

            conversation["messages"].append(message)
            conversation["updatedAt"] = message["createdAt"]
            await self.upsert_conversation(conversation)
            return message
        except Exception as e:
            logging.error(f"Failed to create message: {str(e)}")
            return False

    async def delete_messages(self, conversation_id, user_id):
        """Delete all messages in the conversation."""
        try:
            # Fetch the conversation to access messages
            conversation = await self.get_conversation(user_id, conversation_id)
            if not conversation:
                return False

            # Clear the messages list in the conversation
            conversation["messages"] = []
            conversation["updatedAt"] = datetime.utcnow().isoformat()

            # Update the conversation without messages
            await self.upsert_conversation(conversation)
            logging.info(f"All messages in conversation {conversation_id} deleted.")
            return True
        except Exception as e:
            logging.error(f"Failed to delete messages: {str(e)}")
            return False

    async def get_conversations(self, user_id, limit=None, sort_order="DESC", offset=0):
        """Get conversations for a user."""
        conversations = []
        try:
            # Ensure offset is an integer
            offset = int(offset) if offset else 0
            
            async for blob in self.container_client.list_blobs(
                name_starts_with=f"{str(user_id)}/"
            ):
                blob_client = self.container_client.get_blob_client(blob.name)
                blob_data = await blob_client.download_blob()
                conversation = json.loads(await blob_data.readall())
                conversations.append(conversation)

            # Sort conversations by updatedAt and apply pagination
            conversations = sorted(
                conversations,
                key=lambda x: x["updatedAt"],
                reverse=(sort_order == "DESC"),
            )

            # Ensure limit is an integer or assign default value
            limit = int(limit) if limit else len(conversations)

            return conversations[offset : offset + limit] if limit else conversations

        except Exception as e:
            logging.error(f"Failed to retrieve conversations: {str(e)}")
            return []

    async def get_conversation(self, user_id, conversation_id):
        try:
            blob_name = f"{str(user_id)}/{str(conversation_id)}/conversation.json"
            blob_client = self.container_client.get_blob_client(blob_name)
            blob_data = await blob_client.download_blob()
            conversation = json.loads(await blob_data.readall())
            if conversation["userId"] == user_id:
                return conversation
            else:
                return None
        except Exception as e:
            logging.error(f"Failed to retrieve conversation: {str(e)}")
            return None

    async def get_messages(self, user_id, conversation_id):
        """Get messages in a specific conversation."""
        try:
            conversation = await self.get_conversation(user_id, conversation_id)
            if conversation and "messages" in conversation:
                return conversation["messages"]
            else:
                logging.error(f"No messages found for conversation {conversation_id}")
                return []
        except Exception as e:
            logging.error(f"Failed to retrieve messages: {str(e)}")
            return []
