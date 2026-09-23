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
from django.views.decorators.cache import never_cache

User = get_user_model()

API_BASE_URL = getattr(settings, "API_BASE_URL", "http://127.0.0.1:8000")


def api_request(method: str, endpoint: str, request_obj, data=None, params=None):
    url = f"{API_BASE_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    headers = {
        "X-Estacionamento-ID": get_clean_id_estacionamento(request_obj),
    }

    id_token = request_obj.session.get("id_token")
    if id_token:
        headers["Authorization"] = f"Bearer {id_token}"

    filtered_params = None
    if params and isinstance(params, dict):
        filtered_params = {}
        for k, v in params.items():
            if v in [None, ""]:
                continue
            if isinstance(v, bool):
                filtered_params[k] = "true" if v else "false"
            else:
                filtered_params[k] = v
        if not filtered_params:
            filtered_params = None
    try:
        response = requests.request(
            method=method.upper(),
            url=url,
            json=data if data else None,
            params=filtered_params,
            headers=headers,
            timeout=10.0,
        )
        return response
    except requests.RequestException as e:
        print(f"[API ERROR] Erro na requisição para {url}: {e}")
        return None


@csrf_exempt
def firebase_login(request):
    try:
        payload = json.loads(request.body.decode()) if request.body else {}
        email = payload.get("email")
        senha = payload.get("password")

        if not email or not senha:
            return JsonResponse({"error": "E-mail e senha são obrigatórios."}, status=400)

        params = {"email": email, "senha": senha}
        api_res = api_request("POST", "auth/login", request, params=params)

        if not api_res or api_res.status_code != 200:
            err_msg = "Credenciais inválidas"
            if api_res and api_res.headers.get("Content-Type") == "application/json":
                err_msg = api_res.json().get("detail", err_msg)
            return JsonResponse({"error": err_msg}, status=api_res.status_code if api_res else 502)

        login_data = api_res.json()
        uid = login_data.get("localId")
        id_token = login_data.get("idToken")

        user, _ = User.objects.get_or_create(username=uid, defaults={"email": email})
        user.backend = "appHome.auth_backend.FirebaseBackend"
        login(request, user)

        request.session["id_token"] = id_token

        perfil_res = api_request("GET", "auth/me", request)
        
        is_gestor = False

        if perfil_res and perfil_res.status_code == 200:
            perfil_data = perfil_res.json()
            request.session["user_name"] = perfil_data.get("nome") or perfil_data.get("nome_empresa", "Usuário")
            
            tipo_user = str(perfil_data.get("tipo_user") or perfil_data.get("tipoUser") or perfil_data.get("cargo", "Padrão")).strip().lower()
            request.session["user_cargo"] = tipo_user.capitalize()
            request.session["fotoPerfil"] = perfil_data.get("fotoPerfil", "")

            if tipo_user in ["admin", "gestor", "administrador", "superadmin"]:
                is_gestor = True

            estac_res = api_request("GET", "usuarios/listar_estacionamentos_usuario", request)
            
            id_estac = None
            if estac_res and estac_res.status_code == 200:
                estacionamentos = estac_res.json()
                if isinstance(estacionamentos, list) and len(estacionamentos) > 0:
                    id_estac = estacionamentos[0].get("id")

            if id_estac:
                request.session["id_estacionamento"] = str(id_estac).strip()
            else:
                request.session["id_estacionamento"] = ""

        redirect_url = "/gestor/" if is_gestor else "/"

        return JsonResponse({"ok": True, "uid": uid, "email": email, "redirect": redirect_url})

    except Exception as e:
        print(f"❌ Erro na view firebase_login: {e}")
        return JsonResponse({"error": str(e)}, status=500)


def get_clean_id_estacionamento(request) -> str:
    """
    Retorna o id_estacionamento armazenado na sessão.
    Caso esteja vazio, retorna string vazia sem apagar a sessão desnecessariamente.
    """
    return str(request.session.get("id_estacionamento", "")).strip()


@login_required(login_url="/login/")
def reservas(request):
    id_estacionamento = get_clean_id_estacionamento(request)

    params = {
        "placa": request.GET.get("placa", "").strip(),
        "usuario": request.GET.get("usuario", "").strip(),
        "data_inicio": request.GET.get("data_inicio", "").strip(),
        "data_fim": request.GET.get("data_fim", "").strip(),
        "status": request.GET.get("status", "").strip().lower(),
    }

    if id_estacionamento:
        endpoint = f"/{id_estacionamento}/reserva/"
    else:
        endpoint = "/reserva/"

    response = api_request("GET", endpoint, request, params=params)

    reservas_lista = []
    if response and response.status_code == 200:
        res_json = response.json()
        if isinstance(res_json, dict):
            reservas_lista = res_json.get("reservas", [])
        elif isinstance(res_json, list):
            reservas_lista = res_json

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


@login_required(login_url="/login/")
def gestor(request):
    id_estacionamento = get_clean_id_estacionamento(request)
    if id_estacionamento:
        endpoint = f"/admin/{id_estacionamento}/dashboard"
    else:
        endpoint = "/admin/dashboard"

    response = api_request("GET", endpoint, request)
    dash_data = response.json() if response and response.status_code == 200 else {}

    context = {
        "user_name": request.session.get("user_name", "Visitante"),
        "user_cargo": request.session.get("user_cargo", "Cargo Desconhecido"),
        "fotoPerfil": request.session.get("fotoPerfil", ""),
        "vagas_total": dash_data.get("vagas_total", 0),
        "vagas_ocupadas": dash_data.get("vagas_ocupadas", 0),
        "reservas_hoje": dash_data.get("reservas_hoje", 0),
        "reservas_pendentes": dash_data.get("reservas_pendentes", 0),
        "receita_mensal": dash_data.get("receita_mensal", "0,00"),
        "reservas_canceladas": dash_data.get("reservas_canceladas", 0),
        "receita_cancelada": dash_data.get("receita_cancelada", "0,00"),
        "ultimas_reservas": dash_data.get("ultimas_reservas", []),
        "id_estacionamento_usado": id_estacionamento,
    }

    return render(request, "admin.html", context)


@method_decorator(never_cache, name="dispatch")
class NotificacoesAdminView(LoginRequiredMixin, View):
    template_name = "notificacoes.html"

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        template = self.get_template_names()[0]
        return render(request, template, context)

    def post(self, request, *args, **kwargs):
        acao = request.POST.get("acao")
        notificacao_id = request.POST.get("notificacao_id")

        payload = {"acao": acao, "notificacao_id": notificacao_id}
        response = api_request("POST", "notificacoes/acao/", request, data=payload)

        if response and response.status_code == 200:
            messages.success(request, "Ação executada com sucesso!")
        else:
            messages.error(request, "Erro ao processar ação na API centralizada.")

        return redirect(request.META.get("HTTP_REFERER", "/notificacoes/"))

    def get_template_names(self):
        if self.request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return ["partials/_notificacoes_list.html"]
        return [self.template_name]

    def get_context_data(self, **kwargs):
        apenas_nao_lidas_raw = self.request.GET.get("apenas_nao_lidas", "")
        apenas_nao_lidas_bool = True if apenas_nao_lidas_raw in ["on", "true", "1", "True"] else False

        id_estacionamento = get_clean_id_estacionamento(self.request)

        params = {
            "tipo": self.request.GET.get("tipo", "").strip(),
            "placa": self.request.GET.get("placa", "").strip(),
            "data_inicio": self.request.GET.get("data_inicio", "").strip(),
            "data_fim": self.request.GET.get("data_fim", "").strip(),
            "apenas_nao_lidas": "true" if apenas_nao_lidas_bool else None,
        }

        response = api_request("GET", "notificacoes/", self.request, params=params)

        api_data = response.json() if (response and response.status_code == 200) else {}

        return {
            "user_name": self.request.session.get("user_name", "Visitante"),
            "user_cargo": self.request.session.get("user_cargo", "Cargo Desconhecido"),
            "fotoPerfil": self.request.session.get("fotoPerfil", ""),
            "id_estacionamento": id_estacionamento,
            "notificacoes": api_data.get("notificacoes", []),
            "nao_lidas": api_data.get("nao_lidas", 0),
            "total_notificacoes": api_data.get("total", 0),
            "tipos_notificacao": api_data.get("tipos_notificacao", []),
            "filtro_tipo": params["tipo"],
            "filtro_placa": params["placa"],
            "filtro_data_inicio": params["data_inicio"],
            "filtro_data_fim": params["data_fim"],
            "filtro_apenas_nao_lidas": apenas_nao_lidas_bool,
        }


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


class NotificacoesAPIView(LoginRequiredMixin, View):
    """
    Mantida para requisições pontuais do frontend (AJAX e Firestore Realtime updates).
    """
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request):
        params = {
            'limit': request.GET.get('limit', 20),
            'offset': request.GET.get('offset', 0),
            'apenas_nao_lidas': request.GET.get('apenas_nao_lidas', 'false'),
        }
        res = api_request("GET", "notificacoes/api/", request, params=params)
        if res and res.status_code == 200:
            return JsonResponse(res.json())
        return JsonResponse({'notificacoes': [], 'total': 0, 'nao_lidas': 0}, status=500)

    def post(self, request):
        try:
            data = json.loads(request.body) if request.body else {}
            res = api_request("POST", "notificacoes/api/", request, data=data)
            if res:
                return JsonResponse(res.json(), status=res.status_code)
            return JsonResponse({'success': False, 'error': 'Erro de comunicação com a API Backend'}, status=502)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Payload JSON inválido'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)