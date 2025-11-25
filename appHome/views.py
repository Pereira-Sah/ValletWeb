from django.shortcuts import render
from django.http import JsonResponse, HttpResponseRedirect
from django.conf import settings
import requests
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import login, get_user_model, authenticate
import json
from firebase_admin import auth as fb_auth
import firebase.firebase_init as fi
from datetime import date 

User = get_user_model()

@csrf_exempt
def firebase_login(request):
    if request.method != "POST":
        return JsonResponse({"error":"Method not allowed"}, status=405)

    try:
        payload = json.loads(request.body.decode())
        id_token = payload.get("idToken")

        # fallback: if client sent email+password, exchange for idToken via Firebase REST API
        if not id_token:
            email = payload.get("email")
            password = payload.get("password")
            if email and password:
                api_key = getattr(settings, "FIREBASE_API_KEY", "") or getattr(fi, "WEB_API_KEY", "")
                if not api_key:
                    return JsonResponse({"error": "FIREBASE_API_KEY not set on server"}, status=500)
                try:
                    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
                    r = requests.post(url, json={"email": email, "password": password, "returnSecureToken": True}, timeout=10)
                    if r.status_code != 200:
                        if getattr(settings, 'DEBUG', False):
                            return JsonResponse({"error": "Failed to sign in via Firebase REST", "status_code": r.status_code, "response": r.text}, status=502)
                        return JsonResponse({"error": "Failed to sign in via Firebase REST"}, status=502)
                    id_token = r.json().get("idToken")
                    if not id_token:
                        if getattr(settings, 'DEBUG', False):
                            return JsonResponse({"error": "No idToken in Firebase response", "response": r.text}, status=502)
                        return JsonResponse({"error": "Failed to obtain idToken"}, status=502)
                except requests.RequestException as e:
                    if getattr(settings, 'DEBUG', False):
                        return JsonResponse({"error": "Failed to sign in via Firebase REST", "detail": str(e)}, status=502)
                    return JsonResponse({"error": "Failed to sign in via Firebase REST"}, status=502)
            else:
                return JsonResponse({"error":"idToken missing"}, status=400)

        decoded = fb_auth.verify_id_token(id_token)
        uid = decoded["uid"]
        email = decoded.get("email", "")

        user = authenticate(request, token=id_token)
        if user is None:
            user, _ = User.objects.get_or_create(username=uid, defaults={"email": email})
            user.backend = 'appHome.auth_backend.FirebaseBackend'
        login(request, user)

        # Tentar obter dados adicionais do Firestore para decidir redirecionamento
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

        is_gestor = False
        user_name = "Usuário"
        user_cargo = "Padrão"
        id_estacionamento = "" 

        if doc:
            # 1. Extrair Nome, Cargo e ID do Estacionamento (Assumindo campo 'id_estacionamento')
            user_name = doc.get("nome", "Usuário") 
            # Assumindo que o ID do estacionamento é salvo neste campo no documento do usuário:
            id_estacionamento = doc.get("id_estacionamento", "") 
            
            tipo = str(doc.get("tipo_user", "")).lower()
            cargo = str(doc.get("cargo", "")).lower()
            
            if tipo == "admin" or cargo in ("admin", "administrador", "adm", "chefe"):
                is_gestor = True
                user_cargo = "Gestor"
            elif cargo:
                user_cargo = cargo.capitalize() 
            elif tipo:
                user_cargo = tipo.capitalize()
        
        # 2. ARMAZENAR NOME, CARGO E ID NA SESSÃO
        request.session['user_name'] = user_name 
        request.session['user_cargo'] = user_cargo
        request.session['id_estacionamento'] = id_estacionamento # <-- ESSENCIAL PARA A DASHBOARD

        # Se a requisição vem de fetch/ajax, retornamos JSON com a URL para o cliente redirecionar.
        redirect_url = "/gestor/" if is_gestor else "/"
        if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.content_type == "application/json":
            return JsonResponse({"ok": True, "uid": uid, "email": email, "redirect": redirect_url})

        # Para requisições normais (form POST), redirecionar no servidor
        return HttpResponseRedirect(redirect_url)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    
def appHome(request):
    return render(request, 'home.html')

def login_view(request):
    return render(request, 'login.html')

# ----------------------------------------------------------------------------------
# FUNÇÃO GESTOR COM LÓGICA DE DASHBOARD USANDO NOMES CORRIGIDOS
# ----------------------------------------------------------------------------------
def gestor(request):
    hoje = date.today().isoformat() 
    
    # --- 1. Dados do Usuário na Sidebar e ID do Estacionamento ---
    id_estacionamento = request.session.get('id_estacionamento', '')
    
    context = {
        'user_name': request.session.get('user_name', 'Visitante'),
        'user_cargo': request.session.get('user_cargo', 'Cargo Desconhecido'),
    }
    
    # Valores default 
    vagas_total = 0
    vagas_ocupadas = 0
    reservas_hoje = 0
    reservas_pendentes = 0
    receita_mensal = "0,00"
    ultimas_reservas = []
    
    if id_estacionamento:
        
        # A. Vagas Ocupadas e Totais
        try:
            # COLEÇÃO: 'vaga' (singular) | CAMPO ID: 'estacionamento'
            
            # 1. Total de Vagas: Pega todas as vagas do estacionamento pelo ID
            todas_vagas = fi.fetch_query("vaga", "estacionamento", "==", id_estacionamento)
            vagas_total = len(todas_vagas)

            # 2. Vagas Ocupadas: Filtra onde 'disponivel' é False
            vagas_ocupadas_list = fi.fetch_query("vaga", "disponivel", "==", False, conditions=[
                ("estacionamento", "==", id_estacionamento)
            ])
            vagas_ocupadas = len(vagas_ocupadas_list)

        except Exception:
            pass

        # B. Reservas Hoje
        try:
            # COLEÇÃO: 'reserva' (singular) | CAMPO ID: 'estacionamento'
            # Assumindo que o campo de data se chame 'data_reserva'
            reservas_hoje_list = fi.fetch_query("reserva", "data_reserva", "==", hoje, conditions=[
                ("estacionamento", "==", id_estacionamento) 
            ])
            reservas_hoje = len(reservas_hoje_list)
        except Exception:
            pass

        # C. Reservas Pendentes (Ativas)
        try:
            # Assumindo que o campo para pendente/ativa é 'ativa' == True
            reservas_ativas_list = fi.fetch_query("reserva", "ativa", "==", True, conditions=[
                ("estacionamento", "==", id_estacionamento)
            ]) 
            reservas_pendentes = len(reservas_ativas_list)
        except Exception:
            pass

        # D. Receita Mensal (Soma das reservas ativas)
        try:
            receita_total_float = 0.0
            for reserva in reservas_ativas_list: 
                # Assumindo que o campo com o preço da reserva é 'preco' (visto no doc de vaga)
                valor = reserva.get("preco", 0.0) 
                receita_total_float += float(valor) 

            # Formatação para o Brasil
            receita_mensal = f"{receita_total_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".");

        except Exception:
            receita_mensal = "0,00"
            
        # E. Últimas Reservas (Lista)
        try:
            # Busca as 5 mais recentes 
            ultimas_reservas = fi.fetch_query("reserva", limit=5, order_by=["timestamp", "desc"], conditions=[
                ("estacionamento", "==", id_estacionamento)
            ])
        except Exception:
            pass


    # --- 3. Adicionar Dados ao Contexto ---
    context.update({
        'vagas_total': vagas_total,
        'vagas_ocupadas': vagas_ocupadas,
        'reservas_hoje': reservas_hoje,
        'reservas_pendentes': reservas_pendentes,
        'receita_mensal': receita_mensal,
        'ultimas_reservas': ultimas_reservas,
    })

    return render(request, 'admin.html', context)