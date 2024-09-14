# routing.py

from django.urls import path
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator
from .consumers import BalanceConsumer
from .middleware import TokenOrSessionAuthMiddleware

application = ProtocolTypeRouter({
    "websocket": AllowedHostsOriginValidator(
        TokenOrSessionAuthMiddleware(  # Use the custom middleware here
            URLRouter([
                path("ws/balance/", BalanceConsumer.as_asgi()),
            ])
        )
    ),
})

