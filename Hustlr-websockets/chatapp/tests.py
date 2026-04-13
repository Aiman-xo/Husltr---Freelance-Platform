import json
import pytest
from channels.testing import WebsocketCommunicator
from django.conf import settings
from jwt import encode as jwt_encode
from websocketproject.asgi import application
from chatapp.models import Message
from django.contrib.auth import get_user_model
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

User = get_user_model()

@pytest.fixture
def generate_token():
    def _generate(user_id, room_name):
        return jwt_encode(
            {"user_id": user_id, "room_name": room_name},
            settings.SECRET_KEY,
            algorithm="HS256"
        )
    return _generate

@pytest.mark.asyncio
@pytest.mark.django_db
class TestChatConsumer:
    async def test_chat_connect_success(self, generate_token):
        token = generate_token(user_id=1, room_name="1_2")
        communicator = WebsocketCommunicator(
            application, 
            f"/ws/chat/1_2/?token={token}"
        )
        connected, _ = await communicator.connect()
        assert connected
        
        # Verify history is sent initially
        response = await communicator.receive_json_from()
        assert response['type'] == 'chat_history'
        
        await communicator.disconnect()

    async def test_chat_connect_denied_room_mismatch(self, generate_token):
        # Token says room 1_2, but URL says room 3_4
        token = generate_token(user_id=1, room_name="1_2")
        communicator = WebsocketCommunicator(
            application, 
            f"/ws/chat/3_4/?token={token}"
        )
        connected, _ = await communicator.connect()
        # The consumer should close the connection
        assert not connected

    async def test_message_broadcast(self, generate_token):
        token = generate_token(user_id=1, room_name="1_2")
        communicator = WebsocketCommunicator(application, f"/ws/chat/1_2/?token={token}")
        await communicator.connect()
        # Skip history
        await communicator.receive_json_from()

        # Send a message
        await communicator.send_json_to({"message": "Hello World"})
        
        # Receive the broadcast
        response = await communicator.receive_json_from()
        assert response['message'] == "Hello World"
        assert response['sender_id'] == 1
        
        await communicator.disconnect()

@pytest.mark.asyncio
@pytest.mark.django_db
class TestNotificationConsumer:
    async def test_notification_connection(self, generate_token):
        token = generate_token(user_id=5, room_name="any")
        communicator = WebsocketCommunicator(application, f"/ws/notifications/?token={token}")
        connected, _ = await communicator.connect()
        assert connected
        await communicator.disconnect()

    async def test_receive_notification_from_layer(self, generate_token):
        user_id = 10
        token = generate_token(user_id=user_id, room_name="any")
        communicator = WebsocketCommunicator(application, f"/ws/notifications/?token={token}")
        await communicator.connect()

        # Simulate the Backend (Employer/Worker App) sending a notification via Redis
        channel_layer = get_channel_layer()
        await channel_layer.group_send(
            f"user_notifications_{user_id}",
            {
                "type": "send_notification",
                "payload": {"type": "JOB_ACCEPTED", "message": "Your job was accepted!"}
            }
        )

        # Verify the websocket receives it
        response = await communicator.receive_json_from()
        assert response['type'] == "JOB_ACCEPTED"
        assert response['message'] == "Your job was accepted!"
        
        await communicator.disconnect()
