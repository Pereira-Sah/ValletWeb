import json
import requests
from datetime import datetime
from zoneinfo import ZoneInfo
from django.contrib.auth.decorators import login_required
from .models import NotificacaoAdmin
from django.urls import reverse
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
from django.views.decorators.http import require_GET
from django.core.exceptions import PermissionDenied
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.views.decorators.http import require_POST

from appHome.context_processors import (
    definir_nome_estacionamento,
    invalidar_cache_notificacoes,
    obter_resumo_notificacoes,
)

User = get_user_model()

API_BASE_URL = getattr(settings, "API_BASE_URL", "http://127.0.0.1:8000")
API_TIMEOUT = float(getattr(settings, "API_TIMEOUT", 6))

def api_request(
    method: str,
    endpoint: str,
    request_obj,
    data=None,
    params=None,
    timeout=None,
):
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
            timeout=API_TIMEOUT if timeout is None else timeout,
        )
        if response.status_code == 401:
            request_obj.session.flush()
            raise PermissionDenied("Sessão expirada. Faça login novamente.")
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

            estac_res = api_request(
                "GET",
                "estacionamento/listar_estacionamentos_usuario",
                request
            )
            
            id_estac = None
            nome_estac = ""

            if estac_res and estac_res.status_code == 200:
                estacionamentos = estac_res.json()
                if isinstance(estacionamentos, list) and len(estacionamentos) > 0:
                    primeiro = estacionamentos[0]
                    if isinstance(primeiro, dict):
                        id_estac = primeiro.get("id")
                        nome_estac = primeiro.get("nome") or ""

            if id_estac:
                request.session["id_estacionamento"] = str(id_estac).strip()
                definir_nome_estacionamento(
                    str(id_estac).strip(),
                    nome_estac,
                )
            else:
                request.session["id_estacionamento"] = ""

            invalidar_cache_notificacoes(request)

        redirect_url = "/gestor/" if is_gestor else "/login/"

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
    # Pega a data de hoje formatada no fuso horário correto (igual às notificações)
    hoje_obj = timezone.localdate(timezone=ZoneInfo("America/Sao_Paulo"))
    hoje_str = hoje_obj.isoformat()

    # Verifica se é a primeira abertura (se nenhum filtro de data foi enviado na URL)
    primeira_abertura = not any(
        campo in request.GET for campo in ("data_inicio", "data_fim")
    )

    # Se for a primeira abertura, define data_inicio e data_fim para o dia de hoje
    data_inicio_padrao = hoje_str if primeira_abertura else ""
    data_fim_padrao = hoje_str if primeira_abertura else ""

    params = {
        "id_estacionamento": get_clean_id_estacionamento(request),
        "placa": request.GET.get("placa", "").strip(),
        "usuario": request.GET.get("usuario", "").strip(),
        "data_inicio": request.GET.get("data_inicio", data_inicio_padrao).strip(),
        "data_fim": request.GET.get("data_fim", data_fim_padrao).strip(),
        "status": request.GET.get("status", "").strip().lower(),
        "limite": 24,
        "cursor": request.GET.get("cursor", "").strip(),
        "direcao": request.GET.get("direcao", "proxima"),
    }

    response = api_request(
        "GET",
        "/reserva/",
        request,
        params=params
    )

    dados = {}
    erro = ""

    if response is not None and response.status_code == 200:
        dados = response.json()
    else:
        codigo = (
            response.status_code
            if response is not None
            else "sem conexão"
        )

        erro = (
            f"Não foi possível carregar as reservas "
            f"(API: {codigo})."
        )

        if response is not None and response.status_code == 400:
            erro = response.json().get("detail", erro)

        print(f"[RESERVAS] {erro}")

    filtros = request.GET.copy()

    for chave in ("cursor", "direcao", "pagina"):
        filtros.pop(chave, None)

    try:
        pagina = max(
            1,
            int(request.GET.get("pagina", "1"))
        )
    except ValueError:
        pagina = 1

    def link_pagina(cursor, direcao, numero):
        query = filtros.copy()

        query.update({
            "cursor": cursor,
            "direcao": direcao,
            "pagina": str(numero),
        })

        return "?" + query.urlencode()

    context = {
        "reservas": dados.get("reservas", []),
        "erro_reservas": erro,
        "pagina": pagina,
        "url_anterior": (
            link_pagina(
                dados.get("cursor_anterior"),
                "anterior",
                max(1, pagina - 1)
            )
            if dados.get("tem_anterior")
            else ""
        ),
        "url_proxima": (
            link_pagina(
                dados.get("cursor_proxima"),
                "proxima",
                pagina + 1
            )
            if dados.get("tem_proxima")
            else ""
        ),
        "fotoPerfil": request.session.get("fotoPerfil", ""),
        "user_name": request.session.get("user_name", "Visitante"),
        "user_cargo": request.session.get(
            "user_cargo",
            "Cargo Desconhecido"
        ),
    }

    for campo in (
        "placa", "usuario", "data_inicio", "data_fim", "status"
    ):
        context[f"filtro_{campo}"] = params[campo]

    return render(request, "reservas.html", context)

@never_cache
@login_required(login_url="/login/")
def gestor(request):
    return render(request, "dashboard.html", {
        "user_name": request.session.get("user_name", "Visitante"),
        "user_cargo": request.session.get("user_cargo", "Cargo Desconhecido"),
        "fotoPerfil": request.session.get("fotoPerfil", ""),
    })


@never_cache
@login_required(login_url="/login/")
def chat(request):
    return render(request, "chat.html", {
        "user_name": request.session.get("user_name", "Visitante"),
        "user_cargo": request.session.get("user_cargo", "Cargo Desconhecido"),
        "fotoPerfil": request.session.get("fotoPerfil", ""),
        "id_estacionamento": get_clean_id_estacionamento(request),
    })


@never_cache
@require_GET
@login_required(login_url="/login/")
def chat_token(request):
    """Entrega ao navegador um token de curta duração para o Firestore."""
    if not request.session.get("id_token"):
        return JsonResponse(
            {"detail": "Sua sessão expirou. Faça login novamente.",
             "login_url": reverse("login")},
            status=401,
        )

    try:
        resposta = api_request("POST", "chat/token", request, timeout=15)
    except PermissionDenied:
        return JsonResponse(
            {"detail": "Sua sessão expirou. Faça login novamente.",
             "login_url": reverse("login")},
            status=401,
        )

    if resposta is None:
        return JsonResponse(
            {"detail": "Não foi possível conectar à API do chat."},
            status=503,
        )

    try:
        dados = resposta.json()
    except ValueError:
        return JsonResponse(
            {"detail": "A API retornou uma resposta inválida para o chat."},
            status=502,
        )

    if resposta.status_code != 200:
        detalhe = dados.get("detail") if isinstance(dados, dict) else None
        if not isinstance(detalhe, str) or not detalhe:
            detalhe = "Não foi possível iniciar o chat."
        status_code = resposta.status_code if resposta.status_code in (
            400, 401, 403, 404, 422, 503
        ) else 502
        return JsonResponse({"detail": detalhe}, status=status_code)

    if not isinstance(dados, dict) or not dados.get("token"):
        return JsonResponse(
            {"detail": "A API não retornou um token de chat válido."},
            status=502,
        )

    return JsonResponse(dados)


@never_cache
@require_GET
def gestor_dashboard_dados(request):
    """Proxy autenticado: o token Firebase nunca é enviado ao JavaScript."""
    if not request.user.is_authenticated or not request.session.get("id_token"):
        return JsonResponse({
            "detail": "Sua sessão expirou. Faça login novamente.",
            "login_url": reverse("login"),
        }, status=401)

    secao = request.GET.get("secao", "reservas")
    if secao not in ("reservas", "ocupacao"):
        return JsonResponse({"detail": "Seção inválida."}, status=400)

    params = {}
    if secao == "reservas":
        periodo = request.GET.get("periodo", "mes_atual")
        if periodo not in ("ultimos_7_dias", "mes_atual", "mes"):
            return JsonResponse({"detail": "Período inválido."}, status=422)
        params["periodo"] = periodo
        ano, mes = request.GET.get("ano"), request.GET.get("mes")
        if periodo == "mes":
            try:
                ano, mes = int(ano), int(mes)
            except (ValueError, TypeError):
                return JsonResponse({"detail": "Informe ano e mês válidos."}, status=422)
            if not 1900 <= ano <= 9998 or not 1 <= mes <= 12:
                return JsonResponse({"detail": "Ano ou mês fora do intervalo."}, status=422)
            params.update({"ano": ano, "mes": mes})
        elif ano is not None or mes is not None:
            return JsonResponse({"detail": "Ano e mês só podem ser usados em Escolher mês."}, status=422)

    id_estacionamento = get_clean_id_estacionamento(request)
    endpoint = (
        f"/admin/{id_estacionamento}/dashboard/{secao}"
        if id_estacionamento else f"/admin/dashboard/{secao}"
    )
    try:
        resposta = api_request(
            "GET", endpoint, request, params=params,
            timeout=float(getattr(settings, "API_DASHBOARD_TIMEOUT", 35)),
        )
        # Somente um ID removido/desatualizado permite redescobrir o estacionamento.
        # Não mascara falhas de acesso, índices, rede ou parâmetros com outra consulta.
        if id_estacionamento and resposta is not None and resposta.status_code == 404:
            resposta = api_request(
                "GET", f"/admin/dashboard/{secao}", request, params=params,
                timeout=float(getattr(settings, "API_DASHBOARD_TIMEOUT", 35)),
            )
    except PermissionDenied:
        return JsonResponse({
            "detail": "Sua sessão expirou. Faça login novamente.",
            "login_url": reverse("login"),
        }, status=401)

    if resposta is None:
        return JsonResponse({
            "detail": "Não foi possível conectar à API. Tente mudar o período novamente.",
        }, status=503)

    try:
        dados = resposta.json()
    except ValueError:
        return JsonResponse({"detail": "A API retornou uma resposta inválida."}, status=502)

    if resposta.status_code != 200:
        detalhe = dados.get("detail") if isinstance(dados, dict) else None
        if not isinstance(detalhe, str):
            detalhe = "Não foi possível carregar os dados do dashboard."
        # Uma rota nova ausente deve orientar a instalar a API da etapa 2.
        if resposta.status_code == 404 and detalhe == "Not Found":
            detalhe = "Atualize a API com os arquivos da etapa 2 e reinicie o serviço."
        codigo = resposta.status_code if resposta.status_code in (401, 403, 404, 422, 503) else 502
        return JsonResponse({"detail": detalhe}, status=codigo)

    if not isinstance(dados, dict) or not dados.get("id_estacionamento"):
        return JsonResponse({"detail": "Dados do dashboard inválidos."}, status=502)
    if secao == "reservas" and not all(isinstance(dados.get(k), dict) for k in ("resumo", "graficos", "periodo")):
        return JsonResponse({"detail": "Dados das reservas inválidos."}, status=502)
    if secao == "ocupacao" and not all(isinstance(dados.get(k), int) for k in ("vagas_total", "vagas_ocupadas", "vagas_disponiveis")):
        return JsonResponse({"detail": "Dados de ocupação inválidos."}, status=502)

    request.session["id_estacionamento"] = str(dados["id_estacionamento"])
    return JsonResponse(dados)


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
            invalidar_cache_notificacoes(request)
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

        hoje_obj = timezone.localdate(timezone=ZoneInfo("America/Sao_Paulo"))
        hoje_str = hoje_obj.isoformat()
        
        primeira_abertura = not any(
            campo in self.request.GET for campo in ("data_inicio", "data_fim")
        )
        
        data_inicio_padrao = hoje_str if primeira_abertura else ""
        data_fim_padrao = hoje_str if primeira_abertura else ""

        params = {
            "tipo": self.request.GET.get("tipo", "").strip(),
            "placa": self.request.GET.get("placa", "").strip(),
            "data_inicio": self.request.GET.get("data_inicio", data_inicio_padrao).strip(),
            "data_fim": self.request.GET.get("data_fim", data_fim_padrao).strip(),
            "apenas_nao_lidas": "true" if apenas_nao_lidas_bool else None,
        }

        response = api_request("GET", "notificacoes/", self.request, params=params)

        erro_notificacoes = ""
        if response is None:
            print("[NOTIFICAÇÕES] Não foi possível conectar à API.")
            erro_notificacoes = "Não foi possível conectar à API de notificações. Tente novamente em instantes."
            api_data = {}
            notificacoes = []
        elif response.status_code != 200:
            print(f"[NOTIFICAÇÕES] A API respondeu com HTTP {response.status_code}.")
            erro_notificacoes = f"Não foi possível carregar as notificações (HTTP {response.status_code}). Confira o terminal da API."
            api_data = {}
            notificacoes = []
        else:
            api_data = response.json()
            TIPOS_MAP = dict(NotificacaoAdmin.TIPOS_NOTIFICACAO)
            TIPOS_MAP["reserva_iniciada"] = "Reserva iniciada"
            notificacoes_api = api_data.get("notificacoes", [])
            notificacoes = []
            for n in notificacoes_api:
                n = dict(n)
                n["tipo_display"] = TIPOS_MAP.get(n.get("tipo"), n.get("tipo"))
                notificacoes.append(n)
            tipos_api = api_data.get("tipos_notificacao", [])
            if not tipos_api:
                tipos_api = list(TIPOS_MAP.keys())

            tipos_formatados = []
            for tipo_codigo in tipos_api:
                tipos_formatados.append({
                    "codigo": tipo_codigo,
                    "label": TIPOS_MAP.get(tipo_codigo, tipo_codigo.replace("_", " ").capitalize())
                })
        return {
            "user_name": self.request.session.get("user_name", "Visitante"),
            "user_cargo": self.request.session.get("user_cargo", "Cargo Desconhecido"),
            "fotoPerfil": self.request.session.get("fotoPerfil", ""),
            "id_estacionamento": id_estacionamento,
            "notificacoes": notificacoes,
            "erro_notificacoes": erro_notificacoes,
            "nao_lidas": api_data.get("nao_lidas", 0),
            "total_notificacoes": api_data.get("total", 0),
            "tipos_notificacao": tipos_formatados,
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


@method_decorator(never_cache, name="dispatch")
class NotificacoesResumoView(LoginRequiredMixin, View):
    """Entrega apenas o total e as não lidas, usando cache curto."""

    def get(self, request):
        return JsonResponse(obter_resumo_notificacoes(request))


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
            if res and res.status_code == 200:
                invalidar_cache_notificacoes(request)
            if res:
                return JsonResponse(res.json(), status=res.status_code)
            return JsonResponse({'success': False, 'error': 'Erro de comunicação com a API Backend'}, status=502)
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Payload JSON inválido'}, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=500)

def _excedeu_limite(request, nome, maximo, janela_s):
    """Limite simples por IP, para o formulário não virar canal de spam."""
    chave = f"rl:{nome}:{request.META.get('REMOTE_ADDR', '')}"
    cache.add(chave, 0, janela_s)
    try:
        return cache.incr(chave) > maximo
    except ValueError:
        cache.set(chave, 1, janela_s)
        return False


@require_POST
def recuperar_senha(request):
    email = request.POST.get("email", "").strip().lower()
    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({"ok": False, "detail": "Informe um e-mail válido."}, status=400)

    if _excedeu_limite(request, "recuperar", 5, 600):
        return JsonResponse({"ok": False, "detail": "Muitas tentativas. Aguarde alguns minutos."}, status=429)

    resp = api_request("POST", "auth/recuperar_senha", request, data={"email": email})

    if resp is None or resp.status_code >= 500 or resp.status_code in (400, 403):
        return JsonResponse(
            {"ok": False, "detail": "Não foi possível enviar o link agora. Tente novamente em instantes."},
            status=503,
        )

    return JsonResponse({
        "ok": True,
        "detail": "Se o e-mail estiver cadastrado, você receberá um link para redefinir a senha.",
    })


ASSUNTOS_CONTATO = {
    "acesso": "Solicitar acesso",
    "suporte": "Problema para entrar",
    "outro": "Outro assunto",
}


@require_POST
def contato(request):
    resposta_ok = JsonResponse({"ok": True, "detail": "Mensagem enviada! Responderemos pelo e-mail informado."})

    if request.POST.get("website"):
        return resposta_ok

    nome = " ".join(request.POST.get("nome", "").split())[:100]
    email = request.POST.get("email", "").strip()[:254]
    estacionamento = " ".join(request.POST.get("estacionamento", "").split())[:150]
    assunto = request.POST.get("assunto", "")
    mensagem = request.POST.get("mensagem", "").strip()[:3000]

    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse({"ok": False, "detail": "Informe um e-mail válido."}, status=400)
    if not nome or not mensagem or assunto not in ASSUNTOS_CONTATO:
        return JsonResponse({"ok": False, "detail": "Preencha nome, assunto e mensagem."}, status=400)

    if _excedeu_limite(request, "contato", 3, 600):
        return JsonResponse({"ok": False, "detail": "Muitas mensagens. Aguarde alguns minutos."}, status=429)

    corpo = (
        f"Assunto: {ASSUNTOS_CONTATO[assunto]}\n"
        f"Nome: {nome}\n"
        f"E-mail: {email}\n"
        f"Estacionamento: {estacionamento or '(não informado)'}\n\n"
        f"{mensagem}"
    )
    try:
        enviados = EmailMessage(
            subject=f"[Vallet] {ASSUNTOS_CONTATO[assunto]} - {nome}",
            body=corpo,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[settings.CONTATO_DESTINO],
            reply_to=[email],
        ).send()
        if not enviados:
            raise RuntimeError(
                "Nenhum e-mail enviado: verifique EMAIL_HOST_USER, "
                "EMAIL_HOST_PASSWORD e CONTATO_DESTINO."
            )
        print(f"[CONTATO] Mensagem enviada de {email} ({nome}) sobre '{assunto}'")
    except Exception as e:
        print(f"[CONTATO] Falha ao enviar e-mail: {e}")
        return JsonResponse(
            {"ok": False, "detail": "Não foi possível enviar agora. Tente novamente em instantes."},
            status=503,
        )
    return resposta_ok