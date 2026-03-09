import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Message
from .serializers import MessageSerializer

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user_id = self.scope.get("user_id")
        # Room name from the URL: e.g., /ws/chat/1_5/
        self.url_room_name = self.scope['url_route']['kwargs']['room_name']
        # Room name from the SIGNED JWT: e.g., "1_5"
        self.allowed_room = self.scope.get("allowed_room")

        # 1. AUTH CHECK: Did the middleware find a user?
        if not self.user_id:
            await self.close()
            return

        # 2. PERMISSION CHECK: 
        # Does the room in the URL match exactly what the Backend authorized in the JWT?
        if self.url_room_name != self.allowed_room:
            logger.warning(f"User {self.user_id} tried to join {self.url_room_name} but only allowed in {self.allowed_room}")
            await self.close()
            return

        # If we pass both, create the group name
        self.room_group_name = f'chat_{self.url_room_name}'

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()

        # Fetch and send history
        messages = await self.get_messages()
        await self.send(text_data=json.dumps({
            'type': 'chat_history',
            'messages': messages
        }))

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_content = data.get('message')

        if message_content:
            saved_msg = await self.save_message(message_content)

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message_content,
                    'sender_id': self.user_id,
                    'timestamp': saved_msg.timestamp.isoformat() 
                }
            )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'sender_id': event['sender_id'],
            'timestamp': event['timestamp'],
            'is_history': False
        }))

    # --- DATABASE METHODS ---

    # Update your database methods to use self.url_room_name
    @database_sync_to_async
    def get_messages(self):
        
        # 1. Get the QuerySet
        messages = Message.objects.filter(
            room_name=self.url_room_name
        ).order_by('-timestamp')[:50]

        # 2. Use the Serializer (Pass many=True because it's a list)
        serializer = MessageSerializer(reversed(messages), many=True)

        # 3. Return the data
        return serializer.data

    @database_sync_to_async
    def save_message(self, content):
        return Message.objects.create(
            sender_id=self.user_id,
            room_name=self.url_room_name,
            content=content
        )
    
# Hustlr-websockets/consumers.py

import logging
logger = logging.getLogger(__name__)

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user_id = self.scope.get("user_id")
        logger.info(f"--- CONSUMER: Connection Attempt. User ID: {self.user_id} ---")
        
        if not self.user_id:
            logger.warning("--- CONSUMER: Connection Refused. No User ID found in scope. ---")
            await self.close()
            return

        # Group name unique to this user
        self.notification_group = f"user_notifications_{self.user_id}"
        logger.info(f"--- CONSUMER: Connection Accepted. Group Name: '{self.notification_group}' ---")

        await self.channel_layer.group_add(
            self.notification_group,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'notification_group'):
            await self.channel_layer.group_discard(
                self.notification_group,
                self.channel_name
            )

    # This method is called when the BACKEND sends a "type": "send_notification"
    async def send_notification(self, event):
        logger.info(f"--- CONSUMER: Received send_notification event: {event} ---")
        # Send the payload to the worker's browser
        await self.send(text_data=json.dumps(event["payload"]))