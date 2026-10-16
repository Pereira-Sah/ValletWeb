from django.core.management.base import BaseCommand
from appHome.models import NotificacaoAdmin
from django.utils import timezone
from firebase.firebase_singleton import initialize_firebase_once
from firebase_admin import firestore
import pytz
from datetime import datetime

class Command(BaseCommand):
    help = 'Sincroniza notificações do Firestore'

    def add_arguments(self, parser):
        parser.add_argument(
            '--recent-only',
            action='store_true',
            help='Sincronizar apenas notificações das últimas 24 horas',
        )

    def handle(self, *args, **options):
        try:
            initialize_firebase_once()
            db = firestore.client()
            
            # 🔥 CONSULTA MAIS INTELIGENTE
            if options['recent_only']:
                # Apenas últimas 24 horas
                from datetime import timedelta
                ontem = timezone.now() - timedelta(hours=24)
                notificacoes_ref = db.collection('notificacoes_admin')\
                    .where('timestamp', '>=', ontem)\
                    .order_by('timestamp', direction=firestore.Query.DESCENDING)\
                    .stream()
            else:
                # Todas as notificações, ordenadas por timestamp
                notificacoes_ref = db.collection('notificacoes_admin')\
                    .order_by('timestamp', direction=firestore.Query.DESCENDING)\
                    .stream()
            
            count = 0
            atualizadas = 0
            
            for doc in notificacoes_ref:
                data = doc.to_dict()
                doc_id = doc.id
                
                # Tratamento de campos obrigatórios
                motivo = data.get('motivo')
                if not motivo:
                    placa = data.get('placa', 'Placa não informada')
                    vaga_numero = data.get('vagaNumero', 'Vaga não informada')
                    motivo = f"Veículo {placa} estacionou na {vaga_numero}"
                
                # 🔥 CORREÇÃO: Tratamento correto do timestamp
                timestamp_firestore = data.get('timestamp')
                if timestamp_firestore:
                    if timestamp_firestore.tzinfo is None:
                        timestamp_django = timestamp_firestore.replace(tzinfo=pytz.UTC)
                    else:
                        timestamp_django = timestamp_firestore
                else:
                    timestamp_django = timezone.now()
                
                # Verificar se já existe
                notificacao_existente = NotificacaoAdmin.objects.filter(
                    dados_adicionais__firestore_id=doc_id
                ).first()
                
                if notificacao_existente:
                    # 🔥 ATUALIZAR EXISTENTE
                    notificacao_existente.vaga_id = data.get('vagaId', '')
                    notificacao_existente.placa = data.get('placa', '')
                    notificacao_existente.motivo = motivo
                    notificacao_existente.timestamp = timestamp_django
                    notificacao_existente.tipo = data.get('tipo', 'sistema_alerta_estacionamento')
                    notificacao_existente.save()
                    atualizadas += 1
                    self.stdout.write(f"🔄 Notificação {doc_id} atualizada")
                else:
                    # Criar nova
                    dados_convertidos = {}
                    for key, value in data.items():
                        if hasattr(value, 'isoformat'):
                            dados_convertidos[key] = value.isoformat()
                        else:
                            dados_convertidos[key] = value
                    
                    NotificacaoAdmin.objects.create(
                        vaga_id=data.get('vagaId', ''),
                        placa=data.get('placa', ''),
                        usuario_id=data.get('usuarioId', ''),
                        estacionamento_id=data.get('estacionamentoId', ''),
                        motivo=motivo,
                        timestamp=timestamp_django,
                        vaga_numero=data.get('vagaNumero', ''),
                        tipo=data.get('tipo', 'sistema_alerta_estacionamento'),
                        dados_adicionais={'firestore_id': doc_id, **dados_convertidos}
                    )
                    count += 1
                    self.stdout.write(f"✅ Notificação {doc_id} importada")
            
            self.stdout.write(self.style.SUCCESS(
                f'🎉 {count} notificações novas + {atualizadas} atualizadas = {count + atualizadas} total sincronizadas!'
            ))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Erro: {e}'))
            import traceback
            traceback.print_exc()