from urllib.parse import parse_qs
from jwt import decode as jwt_decode
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class JWTAuthMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        # 1. Get the token from the query string
        query_string = scope.get("query_string", b"").decode("utf-8")
        query_params = parse_qs(query_string)
        token = query_params.get("token", [None])[0]

        if token:
            try:
                # 2. Decode using the SHARED secret key
                decoded_data = jwt_decode(
                    token, 
                    settings.SECRET_KEY, 
                    algorithms=["HS256"]
                )
                
                scope["user_id"] = decoded_data.get("user_id")
                scope["allowed_room"] = decoded_data.get("room_name") # This is the "Ticket"
                
                if not scope["user_id"] or not scope["allowed_room"]:
                    logger.warning("Middleware: Token valid but missing claims.")
                    
            except Exception as e:
                logger.error(f"Middleware Auth Error: {e}")
                scope["user_id"] = None
                scope["allowed_room"] = None
        else:
            scope["user_id"] = None
            scope["allowed_room"] = None

        return await self.inner(scope, receive, send)