import sys
import threading
from django.apps import AppConfig

class ApphomeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'appHome'
    
    def ready(self):
        if 'runserver' in sys.argv:
            try:
                # 🔥 AGUARDAR UM POUCO ANTES DE INICIAR O LISTENER
                import time
                time.sleep(2)  # Aguardar 2 segundos para o servidor inicializar
                
                from .listeners import start_notification_listener
                if start_notification_listener():
                    print("✅ Listener de notificações iniciado com sucesso!")
                else:
                    print("⚠️  Listener já estava rodando!")
                    
            except Exception as e:
                print(f"❌ Erro ao iniciar listener: {e}")
                import traceback
                traceback.print_exc()