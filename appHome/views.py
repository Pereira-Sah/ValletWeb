from django.shortcuts import render
from django.http import JsonResponse, HttpResponseRedirect
from django.conf import settings
import requests
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import login, get_user_model, authenticate, logout
import json
from firebase_admin import auth as fb_auth
import firebase.firebase_init as fi
from datetime import date, datetime
from django.core.serializers.json import DjangoJSONEncoder  # <-- para serializar datetime

User = get_user_model()

# --- Função utilitária para contar reservas do dia ---
def contar_reservas_hoje(id_estacionamento: str) -> int:
    hoje = date.today().isoformat()
    try:
        reservas_hoje = fi.fetch_query("reserva", "inicioReserva", "==", hoje)
        reservas_filtradas = [
            r for r in reservas_hoje if r.get("estacionamentoId") == id_estacionamento
        ]
        print(f"[DEBUG] Reservas encontradas hoje ({hoje}) para estacionamento {id_estacionamento}: {len(reservas_filtradas)}")
        return len(reservas_filtradas)
    except Exception as e:
        print(f"[DEBUG] Erro ao contar reservas de hoje: {e}")
        return 0

@csrf_exempt
def firebase_login(request):
    try:
        payload = json.loads(request.body.decode())
        id_token = payload.get("idToken")

        # --- inicializa variáveis padrão ---
        is_gestor = False
        user_name = "Usuário"
        user_cargo = "Padrão"
        id_estacionamento = ""
        fotoPerfil = ""

        if not id_token:
            email = payload.get("email")
            password = payload.get("password")
            if email and password:
                api_key = getattr(settings, "FIREBASE_API_KEY", "") or getattr(fi, "WEB_API_KEY", "")
                if not api_key:
                    return JsonResponse({"error": "FIREBASE_API_KEY não configurada no servidor"}, status=500)
                try:
                    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
                    r = requests.post(url, json={"email": email, "password": password, "returnSecureToken": True}, timeout=10)
                    if r.status_code != 200:
                        return JsonResponse({"error": "Falha ao fazer login via Firebase REST"}, status=502)
                    id_token = r.json().get("idToken")
                    if not id_token:
                        return JsonResponse({"error": "Falha ao obter o idToken para autenticação"}, status=502)
                except requests.RequestException:
                    return JsonResponse({"error": "Falha ao fazer login via Firebase REST"}, status=502)
            else:
                return JsonResponse({"error":"idToken ou credenciais de e-mail/senha faltando"}, status=400)
            
        decoded = fb_auth.verify_id_token(id_token, clock_skew_seconds=60)
        uid = decoded["uid"]
        email = decoded.get("email", "")

        user = authenticate(request, token=id_token)
        if user is None:
            user, _ = User.objects.get_or_create(username=uid, defaults={"email": email})
            user.backend = 'appHome.auth_backend.FirebaseBackend'
        login(request, user)

        try:
            doc = fi.fetch_document("usuario", uid)
        except Exception:
            doc = None

        if not doc and email:
            try:
                results = fi.fetch_query("usuario", "email", "==", email)
                doc = results[0] if results else None
            except Exception:
                doc = None

        if doc:
            user_name = doc.get("nome", "Usuário")
            try:
                est_results = fi.fetch_query("estacionamento", "adminEmail", "==", email)
            except Exception:
                est_results = []

            if not est_results:
                try:
                    est_results = fi.fetch_query("estacionamento", "adminUid", "==", uid)
                except Exception:
                    est_results = []

            if est_results:
                est = est_results[0]
                id_estacionamento = est.get("_id") or est.get("id") or est.get("estacionamentoId") or ""
                print(f"[DEBUG] Estacionamento encontrado por adminEmail/adminUid: {id_estacionamento} (doc={est})")
            else:
                id_estacionamento = doc.get("id_estacionamento", "")
                print(f"[DEBUG] Usuário {uid} associado ao estacionamento (fallback user doc): {id_estacionamento}")
                
            fotoPerfil = doc.get("fotoPerfil", "")
            tipo = str(doc.get("tipo_user", "")).lower()
            cargo = str(doc.get("cargo", "")).lower()
            
            if tipo == "admin" or cargo in ("admin", "administrador", "adm", "chefe"):
                is_gestor = True
                user_cargo = "Gestor"
            elif cargo:
                user_cargo = cargo.capitalize() 
            elif tipo:
                user_cargo = tipo.capitalize()
        
        request.session['user_name'] = user_name 
        request.session['user_cargo'] = user_cargo
        request.session['fotoPerfil'] = fotoPerfil
        request.session['id_estacionamento'] = id_estacionamento 

        redirect_url = "/gestor/" if is_gestor else "/"
        if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.content_type == "application/json":
            return JsonResponse({
                "ok": True,
                "uid": uid,
                "email": email,
                "fotoPerfil": fotoPerfil,
                "redirect": redirect_url
            })

        return HttpResponseRedirect(redirect_url)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

def appHome(request):
    return render(request, 'home.html')


def login_view(request):
    return render(request, 'login.html')


def calcular_renda_mensal(id_estacionamento: str) -> float:
    hoje = date.today()
    ano_atual = hoje.year
    mes_atual = hoje.month
    try:
        reservas = fi.fetch_query("reserva", "estacionamentoId", "==", id_estacionamento)
        receita_total = 0.0
        for reserva in reservas:
            inicio = reserva.get("inicioReserva")
            preco = float(reserva.get("preco", 0.0))

            # Se inicioReserva for timestamp do Firestore
            if hasattr(inicio, "year") and hasattr(inicio, "month"):
                if inicio.year == ano_atual and inicio.month == mes_atual:
                    receita_total += preco
            else:
                # Se vier como string, tenta converter
                try:
                    dt = datetime.fromisoformat(str(inicio))
                    if dt.year == ano_atual and dt.month == mes_atual:
                        receita_total += preco
                except Exception:
                    pass

        print(f"[DEBUG] Receita mensal para estacionamento {id_estacionamento}: {receita_total}")
        return receita_total
    except Exception as e:
        print(f"[DEBUG] Erro ao calcular renda mensal: {e}")
        return 0.0


def gestor(request):
    id_estacionamento = request.session.get('id_estacionamento', '')
    
    context = {
        'user_name': request.session.get('user_name', 'Visitante'),
        'user_cargo': request.session.get('user_cargo', 'Cargo Desconhecido'),
    }
    
    vagas_total = 0
    vagas_ocupadas = 0
    reservas_hoje = 0
    reservas_pendentes = 0
    receita_mensal = "0,00"
    reservas_canceladas = 0
    receita_cancelada = "0,00"
    ultimas_reservas = []
    
    if id_estacionamento:
        try:
            todas_vagas = fi.fetch_query("vaga", "estacionamentoId", "==", id_estacionamento)
            vagas_total = len(todas_vagas)
            print(f"[DEBUG] Estacionamento {id_estacionamento} - vagas encontradas: {[v.get('_id') for v in todas_vagas]}")
        except Exception as e:
            print(f"[DEBUG] Erro ao buscar vagas: {e}")

        # --- usa função utilitária para reservas de hoje ---
        reservas_hoje = contar_reservas_hoje(id_estacionamento)

        # --- usa função utilitária para calcular renda mensal ---
        receita_total_float = calcular_renda_mensal(id_estacionamento)
        receita_mensal = f"{receita_total_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        try:
            reservas_ativas_list = fi.fetch_query("reserva", "status", "==", "ativa")
            reservas_pendentes = len([r for r in reservas_ativas_list if r.get("estacionamentoId") == id_estacionamento])
        except Exception:
            pass
        
        try:
            reservas_canceladas_list = fi.fetch_query("reserva", "status", "==", "cancelada")
            reservas_canceladas = len([r for r in reservas_canceladas_list if r.get("estacionamentoId") == id_estacionamento])
            receita_cancelada_float = sum(float(r.get("preco", 0.0)) for r in reservas_canceladas_list if r.get("estacionamentoId") == id_estacionamento)
            receita_cancelada = f"{receita_cancelada_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            pass
            
        try:
            ultimas_reservas = fi.fetch_query("reserva", "estacionamentoId", "==", id_estacionamento)
            ultimas_reservas = sorted(
                ultimas_reservas,
                key=lambda r: r.get('timestamp') or r.get('dataReserva') or "",
                reverse=True
            )[:5]
            
            reservas_com_nome = []
            for reserva in ultimas_reservas:
                vaga_id = reserva.get("vagaId")
                nome_vaga_completo = "Nome Indisponível"

                if vaga_id:
                    try:
                        vaga_doc = fi.fetch_document("vaga", vaga_id)
                        print(f"[DEBUG] Buscando vaga {vaga_id}... resultado: {vaga_doc}")

                        if vaga_doc:
                            numero = vaga_doc.get("numero", vaga_id)
                            localizacao = vaga_doc.get("localizacao", "")
                            nome_vaga_completo = f"{numero} - {localizacao}" if localizacao else numero
                            print(f"[DEBUG] Nome da vaga encontrado: {nome_vaga_completo}")
                        else:
                            print(f"[DEBUG] Nenhum documento encontrado para vaga {vaga_id}")
                    except Exception as e:
                        print(f"[DEBUG] Erro ao buscar vaga {vaga_id}: {e}")

                reserva['nome_vaga_completo'] = nome_vaga_completo
                reservas_com_nome.append(reserva)
                
            ultimas_reservas = reservas_com_nome 
        except Exception as e:
            print(f"[DEBUG] Erro ao buscar últimas reservas: {e}")
            ultimas_reservas = []
            

    context.update({
        'fotoPerfil': request.session.get('fotoPerfil', ''),
        'vagas_total': vagas_total,
        'vagas_ocupadas': vagas_ocupadas,
        'reservas_hoje': reservas_hoje,
        'reservas_pendentes': reservas_pendentes,
        'receita_mensal': receita_mensal,
        'reservas_canceladas': reservas_canceladas,
        'receita_cancelada': receita_cancelada,
        'ultimas_reservas': ultimas_reservas,
        'id_estacionamento_usado': id_estacionamento,
    })
    
    print(f"[DEBUG] Contexto do gestor antes do render: {context}")
    return render(request, 'admin.html', context)


def logout_view(request):
    try:
        logout(request)
    except Exception:
        pass
    return HttpResponseRedirect('/login/')

from django.http import JsonResponse
from django.views import View
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
import json
from .models import NotificacaoAdmin
from firebase_admin import firestore
import firebase_admin
from firebase_admin import credentials
from datetime import datetime

class NotificacoesAdminView(LoginRequiredMixin, TemplateView):
    template_name = 'notificacoes.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Buscar notificações do banco Django
        notificacoes = NotificacaoAdmin.objects.all().order_by('-timestamp')[:50]
        context['notificacoes'] = notificacoes
        
        # Contar notificações não lidas
        context['notificacoes_nao_lidas'] = NotificacaoAdmin.objects.filter(lida=False).count()
        
        return context

class NotificacoesAPIView(LoginRequiredMixin, View):
    def get(self, request):
        # Parâmetros para paginação e filtros
        limite = int(request.GET.get('limit', 20))
        offset = int(request.GET.get('offset', 0))
        apenas_nao_lidas = request.GET.get('apenas_nao_lidas', 'false').lower() == 'true'
        
        # Query base
        notificacoes_query = NotificacaoAdmin.objects.all()
        
        if apenas_nao_lidas:
            notificacoes_query = notificacoes_query.filter(lida=False)
        
        # Total para paginação
        total = notificacoes_query.count()
        
        # Aplicar limite e offset
        notificacoes = notificacoes_query.order_by('-timestamp')[offset:offset + limite]
        
        # Serializar dados
        notificacoes_data = []
        for notificacao in notificacoes:
            notificacoes_data.append({
                'id': notificacao.id,
                'vaga_id': notificacao.vaga_id,
                'placa': notificacao.placa,
                'usuario_id': notificacao.usuario_id,
                'motivo': notificacao.motivo,
                'timestamp': notificacao.timestamp.isoformat(),
                'tipo': notificacao.tipo,
                'lida': notificacao.lida,
                'tipo_display': notificacao.get_tipo_display(),
                'dados_adicionais': notificacao.dados_adicionais,
            })
        
        return JsonResponse({
            'notificacoes': notificacoes_data,
            'total': total,
            'nao_lidas': NotificacaoAdmin.objects.filter(lida=False).count()
        })
    
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            acao = data.get('acao')
            
            if acao == 'marcar_como_lida':
                notificacao_id = data.get('notificacao_id')
                notificacao = NotificacaoAdmin.objects.get(id=notificacao_id)
                notificacao.lida = True
                notificacao.save()
                
                return JsonResponse({'success': True, 'message': 'Notificação marcada como lida'})
            
            elif acao == 'marcar_todas_como_lidas':
                NotificacaoAdmin.objects.filter(lida=False).update(lida=True)
                return JsonResponse({'success': True, 'message': 'Todas as notificações marcadas como lidas'})
            
            elif acao == 'excluir':
                notificacao_id = data.get('notificacao_id')
                NotificacaoAdmin.objects.filter(id=notificacao_id).delete()
                return JsonResponse({'success': True, 'message': 'Notificação excluída'})
            
            else:
                return JsonResponse({'success': False, 'error': 'Ação não reconhecida'})
                
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})


class SincronizarNotificacoesView(LoginRequiredMixin, View):
    """View para sincronizar notificações - VERSÃO CORRIGIDA"""
    
    def post(self, request):
        try:
            print("🔄 INICIANDO SINCRONIZAÇÃO CORRIGIDA...")
            
            # Inicializar Firebase
            if not firebase_admin._apps:
                cred = credentials.Certificate('firebase/firebase-key.json')
                firebase_admin.initialize_app(cred)
            
            db = firestore.client()
            
            # Buscar notificações do Firestore
            notificacoes_ref = db.collection('notificacoes_admin')
            notificacoes_firebase = notificacoes_ref.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(50).get()
            
            print(f"📦 Encontradas {len(notificacoes_firebase)} notificações no Firestore")
            
            notificacoes_sincronizadas = 0
            notificacoes_atualizadas = 0
            
            for doc in notificacoes_firebase:
                data = doc.to_dict()
                
                # 🔥 CORREÇÃO: Mapear campos corretamente
                vaga_id = data.get('vagaId') or data.get('vaga_id') or ''
                placa = data.get('placa') or ''
                motivo = data.get('motivo') or 'Não especificado'
                
                # Converter timestamp
                timestamp_firestore = data.get('timestamp')
                if timestamp_firestore:
                    timestamp_django = timestamp_firestore.replace(tzinfo=timezone.utc)
                else:
                    timestamp_django = timezone.now()
                
                # 🔥 CORREÇÃO: Buscar por ID do documento Firestore
                firestore_id = doc.id
                
                # Verificar se já existe (usando ID do Firestore como referência)
                notificacao_existente = NotificacaoAdmin.objects.filter(
                    dados_adicionais__has_key='firestore_id',
                    dados_adicionais__firestore_id=firestore_id
                ).first()
                
                if notificacao_existente:
                    # Atualizar existente
                    notificacao_existente.vaga_id = vaga_id
                    notificacao_existente.placa = placa
                    notificacao_existente.motivo = motivo
                    notificacao_existente.timestamp = timestamp_django
                    notificacao_existente.tipo = data.get('tipo', 'sistema_alerta_estacionamento')
                    notificacao_existente.estacionamento_id = data.get('estacionamentoId')
                    notificacao_existente.vaga_numero = data.get('vagaNumero')
                    
                    # Atualizar dados adicionais
                    dados_atuais = notificacao_existente.dados_adicionais
                    dados_atuais.update(data)
                    dados_atuais['firestore_id'] = firestore_id
                    notificacao_existente.dados_adicionais = dados_atuais
                    
                    notificacao_existente.save()
                    notificacoes_atualizadas += 1
                    print(f"   🔄 ATUALIZADA: {placa} - {vaga_id}")
                    
                else:
                    # Criar nova notificação
                    dados_adicionais = data.copy()
                    dados_adicionais['firestore_id'] = firestore_id
                    
                    NotificacaoAdmin.objects.create(
                        vaga_id=vaga_id,
                        placa=placa,
                        usuario_id=data.get('usuarioId', ''),
                        motivo=motivo,
                        timestamp=timestamp_django,
                        tipo=data.get('tipo', 'sistema_alerta_estacionamento'),
                        estacionamento_id=data.get('estacionamentoId'),
                        vaga_numero=data.get('vagaNumero'),
                        dados_adicionais=dados_adicionais
                    )
                    notificacoes_sincronizadas += 1
                    print(f"   ✅ NOVA: {placa} - {vaga_id}")
            
            # Contar totais
            total_django = NotificacaoAdmin.objects.count()
            
            print("📊 RESUMO DA SINCRONIZAÇÃO:")
            print(f"   ✅ Novas sincronizadas: {notificacoes_sincronizadas}")
            print(f"   🔄 Atualizadas: {notificacoes_atualizadas}")
            print(f"   📋 Total no Django: {total_django}")
            
            return JsonResponse({
                'success': True,
                'message': f'Sincronização concluída! {notificacoes_sincronizadas} novas, {notificacoes_atualizadas} atualizadas.',
                'sincronizadas': notificacoes_sincronizadas,
                'atualizadas': notificacoes_atualizadas,
                'total_django': total_django
            })
            
        except Exception as e:
            print(f"❌ ERRO NA SINCRONIZAÇÃO: {e}")
            import traceback
            traceback.print_exc()
            return JsonResponse({
                'success': False, 
                'error': f'Erro: {str(e)}'
            })


class SincronizacaoAgressivaView(LoginRequiredMixin, View):
    """Sincronização que limpa e recria TUDO"""
    
    def post(self, request):
        try:
            print("💥 SINCRONIZAÇÃO AGRESSIVA - RECRIANDO TUDO...")
            
            # Inicializar Firebase
            if not firebase_admin._apps:
                cred = credentials.Certificate('firebase/serviceAccountKey.json')
                firebase_admin.initialize_app(cred)
            
            db = firestore.client()
            
            # Buscar todas as notificações do Firestore
            notificacoes_firebase = db.collection('notificacoes_admin').get()
            
            print(f"📦 Encontradas {len(notificacoes_firebase)} notificações no Firestore")
            
            # 🔥 LIMPAR TUDO primeiro
            NotificacaoAdmin.objects.all().delete()
            print("🧹 Todas as notificações locais foram removidas")
            
            # Recriar todas do Firestore
            criadas = 0
            for doc in notificacoes_firebase:
                data = doc.to_dict()
                
                # Converter timestamp
                timestamp_firestore = data.get('timestamp')
                if timestamp_firestore:
                    timestamp_django = timestamp_firestore.replace(tzinfo=timezone.utc)
                else:
                    timestamp_django = timezone.now()
                
                # Preparar dados adicionais
                dados_adicionais = data.copy()
                dados_adicionais['firestore_id'] = doc.id
                
                # Criar notificação
                NotificacaoAdmin.objects.create(
                    vaga_id=data.get('vagaId') or data.get('vaga_id') or '',
                    placa=data.get('placa') or '',
                    usuario_id=data.get('usuarioId', ''),
                    motivo=data.get('motivo', 'Não especificado'),
                    timestamp=timestamp_django,
                    tipo=data.get('tipo', 'sistema_alerta_estacionamento'),
                    estacionamento_id=data.get('estacionamentoId'),
                    vaga_numero=data.get('vagaNumero'),
                    dados_adicionais=dados_adicionais
                )
                criadas += 1
            
            print(f"✅ {criadas} notificações recriadas do Firestore")
            
            return JsonResponse({
                'success': True,
                'message': f'Sincronização agressiva concluída! {criadas} notificações recriadas.',
                'criadas': criadas
            })
            
        except Exception as e:
            print(f"❌ Erro na sincronização agressiva: {e}")
            import traceback
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': str(e)})


class DebugNotificacoesView(View):
    """View para debug das notificações"""
    
    @method_decorator(login_required(login_url='/login/'))
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get(self, request):
        try:
            print("🔍 Iniciando debug das notificações...")
            
            # Notificações no Django
            notificacoes_django = NotificacaoAdmin.objects.all()
            print(f"📊 Django: {notificacoes_django.count()} notificações")
            
            dados_django = []
            for notif in notificacoes_django:
                dados_django.append({
                    'id': notif.id,
                    'vaga_id': notif.vaga_id,
                    'placa': notif.placa,
                    'timestamp': notif.timestamp.isoformat() if notif.timestamp else None,
                    'lida': notif.lida,
                    'motivo': notif.motivo
                })
            
            # Notificações no Firestore
            dados_firestore = []
            try:
                if not firebase_admin._apps:
                    cred = credentials.Certificate('firebase/serviceAccountKey.json')
                    firebase_admin.initialize_app(cred)
                
                db = firestore.client()
                notificacoes_firestore = db.collection('notificacoes_admin').limit(50).get()
                
                print(f"📊 Firestore: {len(notificacoes_firestore)} notificações")
                
                for doc in notificacoes_firestore:
                    data = doc.to_dict()
                    timestamp = data.get('timestamp')
                    dados_firestore.append({
                        'id': doc.id,
                        'vagaId': data.get('vagaId'),
                        'placa': data.get('placa'),
                        'timestamp': timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp),
                        'motivo': data.get('motivo', 'Não especificado'),
                        'usuarioId': data.get('usuarioId'),
                        'tipo': data.get('tipo')
                    })
                    
            except Exception as e:
                print(f"❌ Erro ao buscar do Firestore: {e}")
                dados_firestore = {'error': str(e)}
            
            response_data = {
                'django': {
                    'total': len(dados_django),
                    'dados': dados_django
                },
                'firestore': {
                    'total': len(dados_firestore) if isinstance(dados_firestore, list) else 0,
                    'dados': dados_firestore
                },
                'user': {
                    'username': request.user.username,
                    'is_authenticated': request.user.is_authenticated
                }
            }
            
            print("✅ Debug concluído")
            return JsonResponse(response_data)
            
        except Exception as e:
            print(f"❌ Erro no debug: {e}")
            return JsonResponse({'error': str(e)})     

    
    def get(self, request):
        try:
            # Notificações no Django
            notificacoes_django = NotificacaoAdmin.objects.all()
            
            # Notificações no Firestore
            if not firebase_admin._apps:
                cred = credentials.Certificate('firebase/firebase-key.json')
                firebase_admin.initialize_app(cred)
            
            db = firestore.client()
            notificacoes_firestore = db.collection('notificacoes_admin').get()
            
            dados_django = []
            for notif in notificacoes_django:
                dados_django.append({
                    'id': notif.id,
                    'vaga_id': notif.vaga_id,
                    'placa': notif.placa,
                    'timestamp': notif.timestamp,
                    'lida': notif.lida
                })
            
            dados_firestore = []
            for doc in notificacoes_firestore:
                data = doc.to_dict()
                dados_firestore.append({
                    'id': doc.id,
                    'vagaId': data.get('vagaId'),
                    'placa': data.get('placa'),
                    'timestamp': data.get('timestamp'),
                    'motivo': data.get('motivo')
                })
            
            return JsonResponse({
                'django': {
                    'total': len(dados_django),
                    'dados': dados_django
                },
                'firestore': {
                    'total': len(dados_firestore),
                    'dados': dados_firestore
                }
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)})
