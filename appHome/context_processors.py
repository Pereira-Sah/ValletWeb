import requests
from django.conf import settings


def notificacoes_globais(request):
    contexto = {"notificacoes_nao_lidas": 0}

    if not request.user.is_authenticated:
        return contexto

    token = request.session.get("id_token")

    if not token:
        return contexto

    base_url = getattr(
        settings,
        "API_BASE_URL",
        "http://127.0.0.1:8000"
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "X-Estacionamento-ID": str(
            request.session.get("id_estacionamento") or ""
        ).strip(),
    }

    try:
        resposta = requests.get(
            f"{base_url.rstrip('/')}/notificacoes/",
            headers=headers,
            timeout=10,
        )

        if resposta.status_code == 200:
            dados = resposta.json()
            contexto["notificacoes_nao_lidas"] = dados.get(
                "nao_lidas", 0
            )
        else:
            print(
                "[CONTADOR NOTIFICAÇÕES] "
                f"A API respondeu com HTTP {resposta.status_code}."
            )

    except (requests.RequestException, ValueError) as erro:
        print(f"[CONTADOR NOTIFICAÇÕES] Falha na consulta: {erro}")

    return contexto