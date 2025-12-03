import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import NotificacaoAdmin

class NotificacoesConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        await self.send(json.dumps({
            'type': 'connection_established',
            'message': 'Conectado ao WebSocket!'
        }))

    async def disconnect(self, close_code):
        pass

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']

        if message == 'get_notificacoes':
            notificacoes = await self.get_notificacoes_nao_lidas()
            await self.send(json.dumps({
                'type': 'notificacoes_data',
                'notificacoes': notificacoes
            }))

    @database_sync_to_async
    def get_notificacoes_nao_lidas(self):
        notificacoes = NotificacaoAdmin.objects.filter(lida=False).order_by('-timestamp')[:10]
        return [
            {
                'id': notif.id,
                'motivo': notif.motivo,
                'placa': notif.placa,
                'vaga_numero': notif.vaga_numero,
                'timestamp': notif.timestamp.strftime('%d/%m/%Y %H:%M'),
                'tipo': notif.get_tipo_display()
            }
            for notif in notificacoes
        ]