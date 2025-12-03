from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('ws/notificacoes/', consumers.NotificacoesConsumer.as_asgi()),
]