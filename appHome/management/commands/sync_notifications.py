# management/commands/sync_notifications.py
from django.core.management.base import BaseCommand
from appHome.models import NotificacaoAdmin
from django.utils import timezone
from firebase.firebase_singleton import initialize_firebase_once
from firebase_admin import firestore

class Command(BaseCommand):
    help = 'Sincroniza notificações do Firestore'

    def handle(self, *args, **options):
        try:
            initialize_firebase_once()
            db = firestore.client()
            
            notificacoes_ref = db.collection('notificacoes_admin').stream()
            
            count = 0
            for doc in notificacoes_ref:
                data = doc.to_dict()
                
                # Tratamento de campos obrigatórios
                motivo = data.get('motivo')
                if not motivo:
                    placa = data.get('placa', 'Placa não informada')
                    vaga_numero = data.get('vagaNumero', 'Vaga não informada')
                    motivo = f"Veículo {placa} estacionou na {vaga_numero}"
                
                timestamp_firestore = data.get('timestamp')
                if timestamp_firestore:
                    timestamp_django = timestamp_firestore.replace(tzinfo=timezone.utc)
                else:
                    timestamp_django = timezone.now()
                
                # Verificar se já existe
                if not NotificacaoAdmin.objects.filter(
                    dados_adicionais__firestore_id=doc.id
                ).exists():
                    
                    NotificacaoAdmin.objects.create(
                        vaga_id=data.get('vagaId', ''),
                        placa=data.get('placa', ''),
                        usuario_id=data.get('usuarioId', ''),
                        estacionamento_id=data.get('estacionamentoId', ''),
                        motivo=motivo,
                        timestamp=timestamp_django,
                        vaga_numero=data.get('vagaNumero', ''),
                        tipo=data.get('tipo', 'sistema_alerta_estacionamento'),
                        dados_adicionais={'firestore_id': doc.id, **data}
                    )
                    count += 1
                    self.stdout.write(f"✅ Notificação {doc.id} importada")
            
            self.stdout.write(self.style.SUCCESS(f'🎉 {count} notificações sincronizadas!'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Erro: {e}'))