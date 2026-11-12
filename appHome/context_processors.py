import requests
from django.conf import settings
from django.core.cache import cache

RESUMO_CACHE_PREFIX = "notificacoes_resumo"
NOME_CACHE_PREFIX = "nome_estacionamento"
SIDEBAR_CACHE_PREFIX = "sidebar_estacionamento_v2"


def _ttl(nome_config, padrao):
    try:
        return int(getattr(settings, nome_config, padrao))
    except (TypeError, ValueError):
        return padrao


def _timeout():
    try:
        return float(getattr(settings, "API_TIMEOUT", 6.0))
    except (TypeError, ValueError):
        return 6.0


def _base_url():
    return getattr(
        settings,
        "API_BASE_URL",
        "http://127.0.0.1:8000",
    ).rstrip("/")


def _uid_usuario(request):
    return str(getattr(request.user, "username", "") or "anonimo")


def _headers(request, id_estacionamento):
    return {
        "Authorization": f"Bearer {request.session.get('id_token')}",
        "X-Estacionamento-ID": id_estacionamento,
    }


def _inteiro(valor):
    try:
        return int(valor or 0)
    except (TypeError, ValueError):
        return 0


def chave_resumo_notificacoes(request, id_estacionamento=None):
    if id_estacionamento is None:
        id_estacionamento = str(
            request.session.get("id_estacionamento") or ""
        ).strip()

    return (
        f"{RESUMO_CACHE_PREFIX}:"
        f"{_uid_usuario(request)}:"
        f"{id_estacionamento}"
    )


def invalidar_cache_notificacoes(request, id_estacionamento=None):
    cache.delete(chave_resumo_notificacoes(request, id_estacionamento))

    if id_estacionamento is None:
        cache.delete(chave_resumo_notificacoes(request, ""))


def chave_nome_estacionamento(id_estacionamento):
    return f"{NOME_CACHE_PREFIX}:{id_estacionamento}"


def definir_nome_estacionamento(id_estacionamento, nome):
    if not id_estacionamento or not nome:
        return

    cache.set(
        chave_nome_estacionamento(id_estacionamento),
        nome,
        _ttl("NOME_ESTACIONAMENTO_TTL", 600),
    )


def obter_resumo_notificacoes(request, usar_cache=True):
    """Resumo leve (total e não lidas) com cache curto no Django."""
    id_estacionamento = str(
        request.session.get("id_estacionamento") or ""
    ).strip()

    chave = chave_resumo_notificacoes(request, id_estacionamento)

    if usar_cache:
        dados = cache.get(chave)
        if isinstance(dados, dict):
            return dados

    vazio = {
        "total": 0,
        "nao_lidas": 0,
        "id_estacionamento": id_estacionamento,
    }

    if not request.session.get("id_token"):
        return vazio

    try:
        resposta = requests.get(
            f"{_base_url()}/notificacoes/resumo/",
            headers=_headers(request, id_estacionamento),
            timeout=_timeout(),
        )

        if resposta.status_code != 200:
            print(
                "[CONTADOR NOTIFICAÇÕES] "
                f"HTTP {resposta.status_code}"
            )
            return vazio

        dados = resposta.json()

    except (requests.RequestException, ValueError) as erro:
        print(
            "[CONTADOR NOTIFICAÇÕES] "
            f"Falha na consulta: {erro}"
        )
        return vazio

    if not isinstance(dados, dict):
        return vazio

    resumo = {
        "total": _inteiro(dados.get("total")),
        "nao_lidas": _inteiro(dados.get("nao_lidas")),
        "id_estacionamento": str(
            dados.get("id_estacionamento") or id_estacionamento
        ).strip(),
    }

    cache.set(chave, resumo, _ttl("NOTIFICACOES_RESUMO_TTL", 20))
    return resumo


def _obter_dados_estacionamento(request, id_estacionamento):
    """Reutiliza a consulta de nome para trazer também a foto do estacionamento."""
    vazio = {"nome_estacionamento": "", "foto_estacionamento": ""}
    if not id_estacionamento or not request.session.get("id_token"):
        return vazio

    # Isola o cache por usuário e estacionamento; não reaproveita foto de outro vínculo.
    chave = f"{SIDEBAR_CACHE_PREFIX}:{_uid_usuario(request)}:{id_estacionamento}"
    dados_cache = cache.get(chave)
    if isinstance(dados_cache, dict):
        return dados_cache

    try:
        resposta = requests.get(
            f"{_base_url()}/estacionamento/buscar_estacionamento/{id_estacionamento}",
            headers=_headers(request, id_estacionamento),
            timeout=_timeout(),
        )
        if resposta.status_code != 200:
            print(f"[SIDEBAR ESTACIONAMENTO] HTTP {resposta.status_code}")
            return vazio
        dados = resposta.json()
        if not isinstance(dados, dict):
            return vazio
        foto = dados.get("fotoEstacionamentoUri") or ""
        # Imagens exibidas pelo navegador devem usar uma URL HTTP(S).
        if not isinstance(foto, str) or not foto.strip().lower().startswith(("https://", "http://")):
            foto = ""
        resumo = {
            "nome_estacionamento": str(dados.get("nome") or ""),
            "foto_estacionamento": foto.strip(),
        }
        cache.set(chave, resumo, _ttl("SIDEBAR_ESTACIONAMENTO_TTL", 60))
        return resumo
    except (requests.RequestException, ValueError) as erro:
        print(f"[SIDEBAR ESTACIONAMENTO] Falha na consulta: {erro}")
        return vazio


def notificacoes_globais(request):
    contexto = {
        "notificacoes_nao_lidas": 0,
        "nome_estacionamento": "",
        "foto_estacionamento": "",
    }

    if not request.user.is_authenticated:
        return contexto

    if not request.session.get("id_token"):
        return contexto

    resumo = obter_resumo_notificacoes(request)
    contexto["notificacoes_nao_lidas"] = resumo.get("nao_lidas", 0)

    id_estacionamento = str(
        request.session.get("id_estacionamento") or ""
    ).strip()

    if not id_estacionamento:
        id_api = str(resumo.get("id_estacionamento") or "").strip()

        if id_api:
            id_estacionamento = id_api
            request.session["id_estacionamento"] = id_api

            # A primeira consulta foi feita sem o ID. Aquece a chave correta
            # para as próximas páginas não repetirem a busca.
            cache.set(
                chave_resumo_notificacoes(request, id_api),
                resumo,
                _ttl("NOTIFICACOES_RESUMO_TTL", 20),
            )

    contexto.update(_obter_dados_estacionamento(request, id_estacionamento))

    return contexto


def chat_global(request):
    """Configuração pública do Firebase usada pelo chat em tempo real.  """
    if not request.user.is_authenticated:
        return {"firebase_chat_config": None}

    from django.urls import reverse

    config = {
        "apiKey": getattr(settings, "FIREBASE_WEB_API_KEY", ""),
        "authDomain": getattr(settings, "FIREBASE_AUTH_DOMAIN", ""),
        "projectId": getattr(settings, "FIREBASE_PROJECT_ID", ""),
    }

    app_id = getattr(settings, "FIREBASE_APP_ID", "")
    if app_id:
        config["appId"] = app_id

    sender_id = getattr(settings, "FIREBASE_MESSAGING_SENDER_ID", "")
    if sender_id:
        config["messagingSenderId"] = sender_id

    return {
        "firebase_chat_config": {
            **config,
            "tokenUrl": reverse("chat_token"),
            "chatUrl": reverse("chat"),
            "collection": getattr(settings, "CHAT_COLLECTION", "chat"),
            "estacionamentoId": str(
                request.session.get("id_estacionamento") or ""
            ).strip(),
        }
    }

