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
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q 
from django.contrib import messages  
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
    
    def get_template_names(self):
        # 🔥 SE FOR REQUISIÇÃO AJAX, RETORNAR APENAS O PARTIAL
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return ['partials/_notificacoes_list.html']
        return [self.template_name]
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 🔥 ADICIONAR INFORMAÇÕES DO USUÁRIO LOGADO À SESSÃO
        context.update({
            'user_name': self.request.session.get('user_name', 'Visitante'),
            'user_cargo': self.request.session.get('user_cargo', 'Cargo Desconhecido'),
            'fotoPerfil': self.request.session.get('fotoPerfil', ''),
            'id_estacionamento': self.request.session.get('id_estacionamento', ''),
        })
        
        # 🔥 FILTROS: Obter parâmetros da URL
        tipo_filtro = self.request.GET.get('tipo', '')
        placa_filtro = self.request.GET.get('placa', '')
        data_inicio = self.request.GET.get('data_inicio', '')
        data_fim = self.request.GET.get('data_fim', '')
        apenas_nao_lidas = self.request.GET.get('apenas_nao_lidas', '')
        
        # Query base
        notificacoes_query = NotificacaoAdmin.objects.all()
        
        # 🔥 APLICAR FILTROS
        if tipo_filtro:
            notificacoes_query = notificacoes_query.filter(tipo=tipo_filtro)
        
        if placa_filtro:
            notificacoes_query = notificacoes_query.filter(
                Q(placa__icontains=placa_filtro) | 
                Q(motivo__icontains=placa_filtro)
            )
        
        if data_inicio:
            try:
                data_inicio_obj = datetime.strptime(data_inicio, '%Y-%m-%d')
                notificacoes_query = notificacoes_query.filter(timestamp__date__gte=data_inicio_obj)
            except ValueError:
                pass
        
        if data_fim:
            try:
                data_fim_obj = datetime.strptime(data_fim, '%Y-%m-%d')
                notificacoes_query = notificacoes_query.filter(timestamp__date__lte=data_fim_obj)
            except ValueError:
                pass
        
        if apenas_nao_lidas == 'on':
            notificacoes_query = notificacoes_query.filter(lida=False)
        
        # Ordenar e limitar
        notificacoes = notificacoes_query.order_by('-timestamp')[:100]
        
        # Buscar todos os números das vagas de uma vez
        numeros_vagas = self.get_numeros_vagas_em_lote(notificacoes)
        
        notificacoes_com_vaga = []
        for notificacao in notificacoes:
            numero_vaga = numeros_vagas.get(notificacao.vaga_id, notificacao.vaga_id)
            notificacoes_com_vaga.append({
                'obj': notificacao,
                'numero_vaga': numero_vaga
            })
        
        # 🔥 CONTAGENS
        total_notificacoes = NotificacaoAdmin.objects.count()
        notificacoes_nao_lidas = NotificacaoAdmin.objects.filter(lida=False).count()
        
        context.update({
            'notificacoes_com_vaga': notificacoes_com_vaga,
            'notificacoes_nao_lidas': notificacoes_nao_lidas,
            'total_notificacoes': total_notificacoes,
            'tipos_notificacao': NotificacaoAdmin.TIPOS_NOTIFICACAO,
            
            # 🔥 Manter valores dos filtros ativos
            'filtro_tipo': tipo_filtro,
            'filtro_placa': placa_filtro,
            'filtro_data_inicio': data_inicio,
            'filtro_data_fim': data_fim,
            'filtro_apenas_nao_lidas': apenas_nao_lidas,
        })
        
        print(f"[DEBUG] Contexto de notificações: user_name={context['user_name']}, cargo={context['user_cargo']}, foto={context['fotoPerfil']}")
        
        return context
    
    def post(self, request, *args, **kwargs):
        """🔨 Processa ações de marcar como lida/deslida"""
        acao = request.POST.get('acao')
        notificacao_id = request.POST.get('notificacao_id')
        
        try:
            if acao == 'marcar_como_lida' and notificacao_id:
                notificacao = NotificacaoAdmin.objects.get(id=notificacao_id)
                notificacao.lida = True
                notificacao.save()
                messages.success(request, 'Notificação marcada como lida!')
                
            elif acao == 'marcar_como_nao_lida' and notificacao_id:
                notificacao = NotificacaoAdmin.objects.get(id=notificacao_id)
                notificacao.lida = False
                notificacao.save()
                messages.success(request, 'Notificação marcada como não lida!')
                
            elif acao == 'marcar_todas_como_lidas':
                NotificacaoAdmin.objects.filter(lida=False).update(lida=True)
                messages.success(request, 'Todas as notificações foram marcadas como lidas!')
                
            elif acao == 'marcar_todas_como_nao_lidas':
                NotificacaoAdmin.objects.filter(lida=True).update(lida=False)
                messages.success(request, 'Todas as notificações foram marcadas como não lidas!')
                
            elif acao == 'excluir' and notificacao_id:
                notificacao = NotificacaoAdmin.objects.get(id=notificacao_id)
                notificacao.delete()
                messages.success(request, 'Notificação excluída com sucesso!')
                
        except Exception as e:
            messages.error(request, f'Erro ao processar ação: {str(e)}')
        
        # Redirecionar de volta para a mesma página com os filtros mantidos
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/notificacoes/'))
    
    def get_numeros_vagas_em_lote(self, notificacoes):
        """Busca todos os números das vagas em uma única operação"""
        from firebase.firebase_singleton import initialize_firebase_once
        from firebase_admin import firestore
        
        # Coletar todos os vaga_ids únicos
        vaga_ids = set()
        for notificacao in notificacoes:
            if notificacao.vaga_id:
                vaga_ids.add(notificacao.vaga_id)
        
        if not vaga_ids:
            return {}
        
        try:
            initialize_firebase_once()
            db = firestore.client()
            
            numeros_vagas = {}
            
            # Buscar todas as vagas de uma vez
            for vaga_id in vaga_ids:
                vaga_doc = db.collection('vaga').document(vaga_id).get()
                
                if vaga_doc.exists:
                    vaga_data = vaga_doc.to_dict()
                    numero = (vaga_data.get('numero') or 
                             vaga_data.get('nome') or 
                             vaga_data.get('vagaNumero') or
                             vaga_data.get('numeroVaga'))
                    numeros_vagas[vaga_id] = numero or vaga_id
                else:
                    numeros_vagas[vaga_id] = vaga_id
            
            return numeros_vagas
                
        except Exception as e:
            print(f"Erro ao buscar vagas em lote: {e}")
            return {vaga_id: vaga_id for vaga_id in vaga_ids}

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


class NotificacoesCheckNewView(LoginRequiredMixin, View):
    """API rápida para verificar novas notificações"""
    
    def get(self, request):
        try:
            # Obter timestamp da última verificação do cliente
            last_check_str = request.GET.get('last_check')
            last_check = None
            
            if last_check_str:
                try:
                    last_check = datetime.fromisoformat(last_check_str.replace('Z', '+00:00'))
                except ValueError:
                    pass
            
            # Contagem total de não lidas
            nao_lidas_count = NotificacaoAdmin.objects.filter(lida=False).count()
            
            # Buscar notificações novas (últimos 5 minutos ou desde última verificação)
            if last_check:
                novas_notificacoes = NotificacaoAdmin.objects.filter(
                    lida=False,
                    timestamp__gt=last_check
                ).order_by('-timestamp')[:10]
            else:
                # Se não tem última verificação, pegar das últimas 2 horas
                duas_horas_atras = timezone.now() - timezone.timedelta(hours=2)
                novas_notificacoes = NotificacaoAdmin.objects.filter(
                    lida=False,
                    timestamp__gt=duas_horas_atras
                ).order_by('-timestamp')[:10]
            
            # Serializar notificações novas
            novas_data = []
            for notif in novas_notificacoes:
                novas_data.append({
                    'id': notif.id,
                    'motivo': notif.motivo,
                    'placa': notif.placa,
                    'vaga_numero': notif.vaga_numero,
                    'timestamp': notif.timestamp.strftime('%H:%M'),
                    'tipo': notif.get_tipo_display()
                })
            
            return JsonResponse({
                'success': True,
                'nao_lidas': nao_lidas_count,
                'novas': novas_data,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })



class NotificacoesAtualizacaoView(LoginRequiredMixin, View):
    """API para atualização parcial das notificações"""
    
    def get(self, request):
        try:
            # Parâmetros
            ultima_atualizacao = request.GET.get('ultima_atualizacao')
            limite = int(request.GET.get('limit', 20))
            
            # Query base
            notificacoes_query = NotificacaoAdmin.objects.all()
            
            # Filtrar por data se fornecida
            if ultima_atualizacao:
                try:
                    from datetime import datetime
                    ultima_dt = datetime.fromisoformat(ultima_atualizacao.replace('Z', '+00:00'))
                    notificacoes_query = notificacoes_query.filter(timestamp__gt=ultima_dt)
                except ValueError:
                    pass
            
            notificacoes = notificacoes_query.order_by('-timestamp')[:limite]
            
            # Serializar
            notificacoes_data = []
            for notif in notificacoes:
                notificacoes_data.append({
                    'id': notif.id,
                    'motivo': notif.motivo,
                    'placa': notif.placa,
                    'vaga_numero': notif.vaga_numero,
                    'timestamp': notif.timestamp.isoformat(),
                    'tipo': notif.tipo,
                    'tipo_display': notif.get_tipo_display(),
                    'lida': notif.lida,
                    'nova': notif.timestamp > timezone.now() - timezone.timedelta(minutes=5)
                })
            
            return JsonResponse({
                'success': True,
                'notificacoes': notificacoes_data,
                'total': NotificacaoAdmin.objects.count(),
                'nao_lidas': NotificacaoAdmin.objects.filter(lida=False).count(),
                'ultima_atualizacao': timezone.now().isoformat()
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
        

def reservas(request):
    id_estacionamento = request.session.get("id_estacionamento", "")

    placa_f = (request.GET.get("placa") or "").strip()
    usuario_f = (request.GET.get("usuario") or "").strip()
    data_inicio = (request.GET.get("data_inicio") or "").strip()
    data_fim = (request.GET.get("data_fim") or "").strip()
    status_f = (request.GET.get("status") or "").strip().lower()

    try:
        reservas_raw = fi.fetch_query("reserva", "estacionamentoId", "==", id_estacionamento) if id_estacionamento else []
    except Exception:
        reservas_raw = []

    lista = []

    for r in reservas_raw:
        nome_usuario = r.get("usuarioNome") or r.get("nomeMotorista") or r.get("nomeUsuario") or r.get("nome")
        status = (r.get("status") or "desconhecida").lower()
        if status == "finalizada":
            status = "concluida"

        usuario_id = r.get("usuarioId")
        foto, telefone, placa = "/static/default_profile.png", "", None

        if usuario_id:
            try:
                u = fi.fetch_document("usuario", usuario_id)
                foto = u.get("fotoPerfil") or "/static/default_profile.png"
                telefone = u.get("telefone") or ""
                if not nome_usuario:
                    nome_usuario = u.get("nome") or u.get("usuarioNome") or u.get("nomeMotorista")

                try:
                    veiculos = fi.fetch_query("veiculo", "usuarioId", "==", usuario_id)
                    if veiculos:
                        v = veiculos[0] 
                        placa = v.get("placa") or v.get("placaCarro") or v.get("carPlate")
                except Exception:
                    pass
            except Exception:
                pass

        inicio_dt, fim_dt = None, None
        try:
            inicio_dt = datetime.fromisoformat(str(r.get("inicioReserva")))
            fim_dt = datetime.fromisoformat(str(r.get("fimReserva")))
        except Exception:
            pass

        if placa_f and (not placa or placa_f.lower() not in placa.lower()):
            continue
        if usuario_f and (not nome_usuario or usuario_f.lower() not in nome_usuario.lower()):
            continue
        if status_f and status_f != status:
            continue
        if data_inicio and inicio_dt:
            if inicio_dt.date() < datetime.strptime(data_inicio, "%Y-%m-%d").date():
                continue
        if data_fim and fim_dt:
            if fim_dt.date() > datetime.strptime(data_fim, "%Y-%m-%d").date():
                continue

        numero_vaga = "—"
        if r.get("vagaId"):
            try:
                v = fi.fetch_document("vaga", r["vagaId"])
                numero_vaga = v.get("numero") or "—"
            except Exception:
                pass

        lista.append({
            "placa": placa,
            "usuario": nome_usuario,
            "telefone": telefone,
            "foto": foto,
            "status": status,
            "numero_vaga": numero_vaga,
            "inicio": inicio_dt,
            "fim": fim_dt,
        })

    lista.sort(key=lambda x: x["inicio"] or datetime.min, reverse=True)

    context = {
        "reservas": lista,
        "filtro_placa": placa_f,
        "filtro_usuario": usuario_f,
        "filtro_data_inicio": data_inicio,
        "filtro_data_fim": data_fim,
        "filtro_status": status_f,
        "fotoPerfil": request.session.get("fotoPerfil", ""),
        'user_name': request.session.get('user_name', 'Visitante'),
        'user_cargo': request.session.get('user_cargo', 'Cargo Desconhecido'),
    }
    return render(request, "reservas.html", context)


