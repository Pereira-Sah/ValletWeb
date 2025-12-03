import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import appHome.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Projeto.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": AuthMiddlewareStack(
        URLRouter(
            appHome.routing.websocket_urlpatterns
        )
    ),
})