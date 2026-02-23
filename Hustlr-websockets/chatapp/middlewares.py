from urllib.parse import parse_qs
from jwt import decode as jwt_decode
from django.conf import settings
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser

class JWTAuthMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        # 1. Get the token from the query string (?token=...)
        query_string = scope.get("query_string", b"").decode("utf-8")
        query_params = parse_qs(query_string)
        token = query_params.get("token", [None])[0]

        if token:
            try:
                # 2. Decode the token using our SHARED secret key
                decoded_data = jwt_decode(
                    token, 
                    settings.SECRET_KEY, 
                    algorithms=["HS256"]
                )
                # 3. Get the user_id from the 'user_id' claim
                scope["user_id"] = decoded_data.get("user_id")
            except Exception as e:
                # If token is expired or invalid
                print(f"WebSocket Auth Error: {e}")
                scope["user_id"] = None
        else:
            scope["user_id"] = None

        return await self.inner(scope, receive, send)