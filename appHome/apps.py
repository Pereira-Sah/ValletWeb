import sys
import threading
from django.apps import AppConfig

class ApphomeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'appHome'
    
    def ready(self):
        if 'runserver' in sys.argv:
            try:
                import time
                time.sleep(2)
                from .listeners import start_notification_listener
                    
            except Exception as e:
                print(f"Erro ao iniciar listener: {e}")
                import traceback
                traceback.print_exc()