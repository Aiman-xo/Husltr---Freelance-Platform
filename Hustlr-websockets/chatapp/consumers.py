import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Message

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user_id = self.scope.get("user_id")
        self.room_name = self.scope['url_route']['kwargs']['room_name']

        if not self.user_id:
            await self.close()
            return

        # Security check
        allowed_ids = self.room_name.split('_')
        if str(self.user_id) not in allowed_ids:
            await self.close()
            return

        self.room_group_name = f'chat_{self.room_name}'

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        # 1. Accept the connection first
        await self.accept()

        # 2. Fetch and send old messages to the user who just connected
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

    @database_sync_to_async
    def get_messages(self):
        # Fetch the last 50 messages for this room
        # We use list() to evaluate the queryset inside this sync method
        messages = Message.objects.filter(room_name=self.room_name).order_by('-timestamp').values('content', 'sender_id', 'timestamp')[:50]
    # ... rest of your code
        formatted_messages = []
        for msg in reversed(messages):
            formatted_messages.append({
                'message': msg['content'], # Note the dict access ['content']
                'sender_id': msg['sender_id'],
                'timestamp': msg['timestamp'].isoformat()
            })
    
        return formatted_messages

    @database_sync_to_async
    def save_message(self, content):
        return Message.objects.create(
            sender_id=self.user_id,
            room_name=self.room_name,
            content=content
        )