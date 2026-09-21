import json
import requests
from datetime import datetime
from django.contrib.auth.decorators import login_required

from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponseRedirect
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import login, get_user_model, authenticate, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.contrib import messages
from django.utils import timezone
from django.utils.decorators import method_decorator

User = get_user_model()

# Endereço base da sua API centralizada (pode ser configurado no settings.py)
API_BASE_URL = getattr(settings, "API_BASE_URL", "http://127.0.0.1:8000")

def api_request(method: str, endpoint: str, request_obj, data=None, params=None):
    url = f"{API_BASE_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    headers = {
        "X-Estacionamento-ID": request_obj.session.get("id_estacionamento", ""),
    }
    
    id_token = request_obj.session.get("id_token")
    if id_token:
        headers["Authorization"] = f"Bearer {id_token}"

    try:
        response = requests.request(
            method=method.upper(),
            url=url,
            json=data if data else None,
            params=params,  # <- Repassa os Query Parameters aqui
            headers=headers,
            timeout=10.0
        )
        return response
    except requests.RequestException as e:
        print(f"[API ERROR] Erro na requisição para {url}: {e}")
        return None

User = get_user_model()

@csrf_exempt
def firebase_login(request):
    try:
        # Extrai os dados enviados do formulário HTML/JS
        payload = json.loads(request.body.decode()) if request.body else {}
        email = payload.get("email")
        senha = payload.get("password")  # No JS vem como 'password'

        if not email or not senha:
            return JsonResponse({"error": "E-mail e senha são obrigatórios."}, status=400)

        # Envia como Query Parameters para bater com a assinatura do FastAPI: login(email: str, senha: str)
        # Nota: O endpoint na sua API é /login (e não /auth/login)
        params = {
            "email": email,
            "senha": senha
        }

        # Faz a chamada POST passando params ao invés de data/json
        api_res = api_request("POST", "auth/login", request, params=params)

        if not api_res or api_res.status_code != 200:
            err_msg = "Credenciais inválidas"
            if api_res and api_res.headers.get("Content-Type") == "application/json":
                err_msg = api_res.json().get("detail", err_msg)
            return JsonResponse({"error": err_msg}, status=api_res.status_code if api_res else 502)

        login_data = api_res.json()
        
        # O FastAPI retorna: {"mensagem": "...", "idToken": "...", "refreshToken": "...", "expiresIn": "...", "localId": "..."}
        uid = login_data.get("localId")
        id_token = login_data.get("idToken")

        # 1. Autentica localmente no Django
        user, _ = User.objects.get_or_create(username=uid, defaults={"email": email})
        user.backend = 'appHome.auth_backend.FirebaseBackend'
        login(request, user)

        # 2. Armazena o idToken do Firebase na sessão
        request.session['id_token'] = id_token

        # 3. Busca o perfil completo do usuário chamando o endpoint /me da API
        perfil_res = api_request("GET", "auth/me", request)
        if perfil_res and perfil_res.status_code == 200:
            perfil_data = perfil_res.json()
            request.session['user_name'] = perfil_data.get("nome", "Usuário")
            request.session['user_cargo'] = perfil_data.get("cargo", "Padrão")
            request.session['fotoPerfil'] = perfil_data.get("fotoPerfil", "")
            
            # Verifica se o tipo do usuário é gestor/admin
            tipo_user = perfil_data.get("tipo_user", "").lower()
            is_gestor = tipo_user in ["admin", "administrador", "superadmin", "gestor"]
        else:
            is_gestor = False

        redirect_url = "/gestor/" if is_gestor else "/"

        return JsonResponse({
            "ok": True,
            "uid": uid,
            "email": email,
            "redirect": redirect_url
        })

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


def appHome(request):
    return render(request, 'home.html')


def login_view(request):
    return render(request, 'login.html')


def logout_view(request):
    try:
        logout(request)
    except Exception:
        pass
    return HttpResponseRedirect('/login/')


# --- Dashboard do Gestor ---
@login_required(login_url='/login/')
def gestor(request):
    id_estacionamento = request.session.get('id_estacionamento', '')
    if id_estacionamento:
        endpoint = f"/admin/{id_estacionamento}/dashboard"
    else:
        endpoint = "/admin/dashboard"
        
    response = api_request("GET", endpoint, request)
    dash_data = response.json() if response and response.status_code == 200 else {}

    context = {
        'user_name': request.session.get('user_name', 'Visitante'),
        'user_cargo': request.session.get('user_cargo', 'Cargo Desconhecido'),
        'fotoPerfil': request.session.get('fotoPerfil', ''),
        'vagas_total': dash_data.get('vagas_total', 0),
        'vagas_ocupadas': dash_data.get('vagas_ocupadas', 0),
        'reservas_hoje': dash_data.get('reservas_hoje', 0),
        'reservas_pendentes': dash_data.get('reservas_pendentes', 0),
        'receita_mensal': dash_data.get('receita_mensal', '0,00'),
        'reservas_canceladas': dash_data.get('reservas_canceladas', 0),
        'receita_cancelada': dash_data.get('receita_cancelada', '0,00'),
        'ultimas_reservas': dash_data.get('ultimas_reservas', []),
        'id_estacionamento_usado': id_estacionamento,
    }

    return render(request, 'admin.html', context)

@login_required(login_url='/login/')
def reservas(request):
    id_estacionamento = request.session.get("id_estacionamento", "")

    # Coleta filtros para enviar via Query Parameters
    params = {
        "placa": request.GET.get("placa", "").strip(),
        "usuario": request.GET.get("usuario", "").strip(),
        "data_inicio": request.GET.get("data_inicio", "").strip(),
        "data_fim": request.GET.get("data_fim", "").strip(),
        "status": request.GET.get("status", "").strip().lower(),
    }

    # Trata caso o ID do estacionamento venha vazio
    endpoint = f"{id_estacionamento}/reservas/" if id_estacionamento else "/estacionamentos/reservas/"

    response = api_request("GET", endpoint, request, params=params)
    reservas_lista = response.json().get("reservas", []) if response and response.status_code == 200 else []

    context = {
        "reservas": reservas_lista,
        "filtro_placa": params["placa"],
        "filtro_usuario": params["usuario"],
        "filtro_data_inicio": params["data_inicio"],
        "filtro_data_fim": params["data_fim"],
        "filtro_status": params["status"],
        "fotoPerfil": request.session.get("fotoPerfil", ""),
        "user_name": request.session.get("user_name", "Visitante"),
        "user_cargo": request.session.get("user_cargo", "Cargo Desconhecido"),
    }

    return render(request, "reservas.html", context)


# --- Notificações do Administrador ---

class NotificacoesAdminView(LoginRequiredMixin, View):
    template_name = 'notificacoes.html'

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        acao = request.POST.get('acao')
        notificacao_id = request.POST.get('notificacao_id')

        # Encaminha a ação do POST diretamente para a API centralizada
        payload = {"acao": acao, "notificacao_id": notificacao_id}
        response = api_request("POST", "/notificacoes/acao/", request, data=payload)

        if response and response.status_code == 200:
            messages.success(request, 'Ação executada com sucesso!')
        else:
            messages.error(request, 'Erro ao processar ação na API.')

        return redirect(request.META.get('HTTP_REFERER', '/notificacoes/'))

    def get_template_names(self):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return ['partials/_notificacoes_list.html']
        return [self.template_name]

    def get_context_data(self, **kwargs):
        params = {
            'tipo': self.request.GET.get('tipo', ''),
            'placa': self.request.GET.get('placa', ''),
            'data_inicio': self.request.GET.get('data_inicio', ''),
            'data_fim': self.request.GET.get('data_fim', ''),
            'apenas_nao_lidas': self.request.GET.get('apenas_nao_lidas', ''),
        }

        response = api_request("GET", "/notificacoes/", self.request, params=params)
        api_data = response.json() if response and response.status_code == 200 else {}

        return {
            'user_name': self.request.session.get('user_name', 'Visitante'),
            'user_cargo': self.request.session.get('user_cargo', 'Cargo Desconhecido'),
            'fotoPerfil': self.request.session.get('fotoPerfil', ''),
            'id_estacionamento': self.request.session.get('id_estacionamento', ''),
            'notificacoes_com_vaga': api_data.get('notificacoes', []),
            'notificacoes_nao_lidas': api_data.get('nao_lidas', 0),
            'total_notificacoes': api_data.get('total', 0),
            'tipos_notificacao': api_data.get('tipos_notificacao', []),
            'filtro_tipo': params['tipo'],
            'filtro_placa': params['placa'],
            'filtro_data_inicio': params['data_inicio'],
            'filtro_data_fim': params['data_fim'],
            'filtro_apenas_nao_lidas': params['apenas_nao_lidas'],
        }

# --- Notificações do Administrador ---

class NotificacoesAdminView(LoginRequiredMixin, View):
    template_name = 'notificacoes.html'

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        return render(request, self.template_name, context)

    def post(self, request, *args, **kwargs):
        acao = request.POST.get('acao')
        notificacao_id = request.POST.get('notificacao_id')

        # Encaminha a ação do POST diretamente para a API centralizada
        payload = {"acao": acao, "notificacao_id": notificacao_id}
        response = api_request("POST", "/notificacoes/acao/", request, data=payload)

        if response and response.status_code == 200:
            messages.success(request, 'Ação executada com sucesso!')
        else:
            messages.error(request, 'Erro ao processar ação na API.')

        return redirect(request.META.get('HTTP_REFERER', '/notificacoes/'))

    def get_template_names(self):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return ['partials/_notificacoes_list.html']
        return [self.template_name]

    def get_context_data(self, **kwargs):
        params = {
            'tipo': self.request.GET.get('tipo', ''),
            'placa': self.request.GET.get('placa', ''),
            'data_inicio': self.request.GET.get('data_inicio', ''),
            'data_fim': self.request.GET.get('data_fim', ''),
            'apenas_nao_lidas': self.request.GET.get('apenas_nao_lidas', ''),
        }

        response = api_request("GET", "/notificacoes/", self.request, params=params)
        api_data = response.json() if response and response.status_code == 200 else {}

        return {
            'user_name': self.request.session.get('user_name', 'Visitante'),
            'user_cargo': self.request.session.get('user_cargo', 'Cargo Desconhecido'),
            'fotoPerfil': self.request.session.get('fotoPerfil', ''),
            'id_estacionamento': self.request.session.get('id_estacionamento', ''),
            'notificacoes_com_vaga': api_data.get('notificacoes', []),
            'notificacoes_nao_lidas': api_data.get('nao_lidas', 0),
            'total_notificacoes': api_data.get('total', 0),
            'tipos_notificacao': api_data.get('tipos_notificacao', []),
            'filtro_tipo': params['tipo'],
            'filtro_placa': params['placa'],
            'filtro_data_inicio': params['data_inicio'],
            'filtro_data_fim': params['data_fim'],
            'filtro_apenas_nao_lidas': params['apenas_nao_lidas'],
        }


class NotificacoesAPIView(LoginRequiredMixin, View):
    """
    Mantida apenas para requisições pontuais de ações do frontend (AJAX).
    """
    def get(self, request):
        params = {
            'limit': request.GET.get('limit', 20),
            'offset': request.GET.get('offset', 0),
            'apenas_nao_lidas': request.GET.get('apenas_nao_lidas', 'false'),
        }
        res = api_request("GET", "/notificacoes/api/", request, params=params)
        if res and res.status_code == 200:
            return JsonResponse(res.json())
        return JsonResponse({'notificacoes': [], 'total': 0, 'nao_lidas': 0}, status=500)

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request):
        try:
            data = json.loads(request.body)
            res = api_request("POST", "/notificacoes/api/", request, data=data)
            if res:
                return JsonResponse(res.json(), status=res.status_code)
            return JsonResponse({'success': False, 'error': 'Erro de comunicação com a API Backend'}, status=502)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)