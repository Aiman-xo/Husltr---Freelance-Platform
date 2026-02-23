"""
ASGI config for websocketproject project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
import django
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'websocketproject.settings')
django.setup() # <--- This initializes the app registry
django_asgi_app = get_asgi_application()

# DO NOT MOVE THESE TO THE TOP
from channels.routing import ProtocolTypeRouter, URLRouter
from chatapp.middlewares import JWTAuthMiddleware
import chatapp.routing 

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": JWTAuthMiddleware(
        URLRouter(chatapp.routing.websocket_urlpatterns)
    ),
})