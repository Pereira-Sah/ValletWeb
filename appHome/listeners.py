# appHome/listeners.py
from firebase_admin import firestore
from django.utils import timezone
from appHome.models import NotificacaoAdmin
from firebase.firebase_singleton import initialize_firebase_once

def start_notification_listener():
    # Usar inicialização única
    initialize_firebase_once()
    
    db = firestore.client()
    
    def on_snapshot(col_snapshot, changes, read_time):
        for change in changes:
            if change.type.name == 'ADDED':
                doc = change.document
                data = doc.to_dict()
                
                try:
                    # 🔥 CORREÇÃO: Garantir que motivo nunca seja NULL
                    motivo = data.get('motivo')
                    if not motivo:
                        # Criar motivo padrão baseado nos dados disponíveis
                        placa = data.get('placa', 'Placa não informada')
                        vaga_numero = data.get('vagaNumero', 'Vaga não informada')
                        motivo = f"Veículo {placa} estacionou na {vaga_numero}"
                    
                    # 🔥 CORREÇÃO: Garantir timestamp válido e corrigir erro de tzinfo
                    timestamp_firestore = data.get('timestamp')
                    if timestamp_firestore:
                        # CORREÇÃO: Chamar timezone.now() para obter o objeto de fuso horário, ou usar timezone.utc
                        # O mais seguro é usar timezone.utc para timestamps do Firestore, que são UTC.
                        timestamp_django = timestamp_firestore.replace(tzinfo=timezone.utc)
                    else:
                        timestamp_django = timezone.now()
                    
                    # 🔥 CORREÇÃO: Garantir tipo válido
                    tipo = data.get('tipo', 'sistema_alerta_estacionamento')
                    # Note: O TIPOS_NOTIFICACAO é uma lista de tuplas, precisamos do dict para checagem rápida
                    tipos_validos = dict(NotificacaoAdmin.TIPOS_NOTIFICACAO)
                    if tipo not in tipos_validos:
                        tipo = 'sistema_alerta_estacionamento'
                    
                    # Preparar dados adicionais
                    dados_adicionais = data.copy()
                    dados_adicionais['firestore_id'] = doc.id
                    
                    # Criar notificação com tratamento de campos opcionais
                    NotificacaoAdmin.objects.create(
                        vaga_id=data.get('vagaId', ''),
                        placa=data.get('placa', ''),
                        usuario_id=data.get('usuarioId', ''),
                        estacionamento_id=data.get('estacionamentoId', ''),
                        motivo=motivo,  # Agora sempre tem valor
                        timestamp=timestamp_django,
                        vaga_numero=data.get('vagaNumero', ''),
                        tipo=tipo,
                        dados_adicionais=dados_adicionais
                    )
                    print(f"📥 Nova notificação sincronizada: {doc.id}")
                    
                except Exception as e:
                    print(f"❌ Erro ao processar notificação {doc.id}: {e}")
                    import traceback
                    traceback.print_exc()

    # Iniciar listener
    db.collection('notificacoes_admin').on_snapshot(on_snapshot)
    print("🎧 Listener de notificações iniciado!")