from firebase_admin import firestore
from django.utils import timezone
from appHome.models import NotificacaoAdmin
from firebase.firebase_singleton import initialize_firebase_once
import pytz
import threading
import time

# 🔥 VARIÁVEL GLOBAL PARA CONTROLAR O LISTENER
_listener_running = False
_listener_thread = None

def convert_firestore_data(data):
    """Converte dados do Firestore para serem JSON serializáveis"""
    converted = {}
    
    for key, value in data.items():
        if hasattr(value, 'isoformat'):  # Para datetime objects
            converted[key] = value.isoformat()
        elif hasattr(value, '__class__') and 'DatetimeWithNanoseconds' in str(value.__class__):
            # Converter DatetimeWithNanoseconds para string ISO
            converted[key] = value.isoformat()
        else:
            converted[key] = value
    
    return converted

def processar_nova_notificacao(doc):
    """Processa uma nova notificação do Firestore"""
    try:
        data = doc.to_dict()
        doc_id = doc.id
        
        print(f"   📥 PROCESSANDO NOTIFICAÇÃO: {doc_id}")
        print(f"   📊 Dados: {data}")
        
        # Verificar se já existe (por segurança)
        if NotificacaoAdmin.objects.filter(dados_adicionais__firestore_id=doc_id).exists():
            print(f"   ⚠️  Notificação {doc_id} já existe, ignorando...")
            return False
        
        # Tratamento de campos obrigatórios
        motivo = data.get('motivo')
        if not motivo:
            placa = data.get('placa', 'Placa não informada')
            vaga_numero = data.get('vagaNumero', 'Vaga não informada')
            motivo = f"Veículo {placa} estacionou na {vaga_numero}"
        
        # 🔥 CORREÇÃO: Tratamento CORRETO de timestamp
        timestamp_firestore = data.get('timestamp')
        if timestamp_firestore:
            # O timestamp do Firestore já está em UTC
            if timestamp_firestore.tzinfo is None:
                timestamp_django = timestamp_firestore.replace(tzinfo=pytz.UTC)
            else:
                timestamp_django = timestamp_firestore
            print(f"   🕒 Timestamp Firestore (UTC): {timestamp_django}")
        else:
            timestamp_django = timezone.now()
            print(f"   🕒 Timestamp atual (local): {timestamp_django}")
        
        # Converter dados para JSON serializável
        dados_serializaveis = convert_firestore_data(data)
        
        # Criar notificação
        NotificacaoAdmin.objects.create(
            vaga_id=data.get('vagaId', ''),
            placa=data.get('placa', ''),
            usuario_id=data.get('usuarioId', ''),
            estacionamento_id=data.get('estacionamentoId', ''),
            motivo=motivo,
            timestamp=timestamp_django,
            vaga_numero=data.get('vagaNumero', ''),
            tipo=data.get('tipo', 'sistema_alerta_estacionamento'),
            dados_adicionais={'firestore_id': doc_id, **dados_serializaveis}
        )
        print(f"   ✅ Notificação {doc_id} salva no Django!")
        
        # Verificar quantas notificações temos agora
        total = NotificacaoAdmin.objects.count()
        print(f"   📋 Total de notificações: {total}")
        return True
        
    except Exception as e:
        print(f"   ❌ Erro ao processar notificação {doc.id}: {e}")
        import traceback
        traceback.print_exc()
        return False

def on_snapshot(col_snapshot, changes, read_time):
    """Callback para mudanças em tempo real"""
    print(f"📡 Evento recebido! Mudanças: {len(changes)}")
    
    for change in changes:
        print(f"   🔄 Tipo de mudança: {change.type.name}")
        
        if change.type.name == 'ADDED':
            doc = change.document
            processar_nova_notificacao(doc)
        
        elif change.type.name == 'MODIFIED':
            print(f"   🔄 Documento modificado: {change.document.id}")
            # Você pode implementar atualização se necessário
        
        elif change.type.name == 'REMOVED':
            print(f"   🗑️  Documento removido: {change.document.id}")
            # Você pode implementar exclusão se necessário

def start_notification_listener():
    """Inicia o listener em tempo real em uma thread separada"""
    global _listener_running, _listener_thread
    
    if _listener_running:
        print("⚠️  Listener já está rodando!")
        return
    
    def listener_thread():
        global _listener_running
        _listener_running = True
        
        try:
            print("🎧 Iniciando listener em tempo real...")
            
            # Usar inicialização única
            initialize_firebase_once()
            
            db = firestore.client()
            
            # Configurar o listener
            print("🔗 Conectando ao Firestore...")
            query = db.collection('notificacoes_admin')
            
            # Watch the collection query
            query_watch = query.on_snapshot(on_snapshot)
            
            print("✅ Listener conectado e escutando notificações_admin em tempo real!")
            print("💡 Agora crie uma nova notificação no Firestore para testar...")
            
            # Manter a thread viva
            while _listener_running:
                time.sleep(10)  # Verificar a cada 10 segundos se ainda está rodando
                
        except Exception as e:
            print(f"❌ Erro crítico no listener: {e}")
            import traceback
            traceback.print_exc()
        finally:
            _listener_running = False
            print("🛑 Listener parado!")
    
    # Iniciar em thread separada
    _listener_thread = threading.Thread(target=listener_thread, daemon=True)
    _listener_thread.start()
    
    return True

def stop_notification_listener():
    """Para o listener em tempo real"""
    global _listener_running
    _listener_running = False
    print("🛑 Parando listener...")