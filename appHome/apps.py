# appHome/apps.py
import sys
from django.apps import AppConfig

class ApphomeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'appHome'
    
    def ready(self):
        # Só inicializa o listener quando rodando o servidor
        if 'runserver' in sys.argv:
            try:
                from .listeners import start_notification_listener
                start_notification_listener()
                print("✅ Listener de notificações iniciado com sucesso!")
            except Exception as e:
                print(f"❌ Erro ao iniciar listener: {e}")