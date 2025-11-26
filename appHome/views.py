from django.shortcuts import render
from django.http import JsonResponse, HttpResponseRedirect
from django.conf import settings
import requests
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import login, get_user_model, authenticate, logout
import json
from firebase_admin import auth as fb_auth
import firebase.firebase_init as fi
from datetime import date 

# ... (outras views, como firebase_login, appHome, login_view) ...

User = get_user_model()

@csrf_exempt
def firebase_login(request):
    # ... (Seu código da firebase_login)
    try:
        payload = json.loads(request.body.decode())
        id_token = payload.get("idToken")

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
                        if getattr(settings, 'DEBUG', False):
                            return JsonResponse({"error": "E-mail ou senha incorreta.", "status_code": r.status_code, "response": r.text}, status=502)
                        return JsonResponse({"error": "Falha ao fazer login via Firebase REST. Verifique e-mail e senha."}, status=502)
                    id_token = r.json().get("idToken")
                    if not id_token:
                        if getattr(settings, 'DEBUG', False):
                            return JsonResponse({"error": "Nenhum idToken na resposta do Firebase", "response": r.text}, status=502)
                        return JsonResponse({"error": "Falha ao obter o idToken para autenticação"}, status=502)
                except requests.RequestException as e:
                    if getattr(settings, 'DEBUG', False):
                        return JsonResponse({"error": "Falha ao fazer login via Firebase REST", "detail": str(e)}, status=502)
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

        is_gestor = False
        user_name = "Usuário"
        user_cargo = "Padrão"
        id_estacionamento = "" 

        if doc:
            user_name = doc.get("nome", "Usuário")
            id_estacionamento = ""
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
        request.session['id_estacionamento'] = id_estacionamento 

        redirect_url = "/gestor/" if is_gestor else "/"
        if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.content_type == "application/json":
            return JsonResponse({"ok": True, "uid": uid, "email": email, "redirect": redirect_url})

        return HttpResponseRedirect(redirect_url)
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    
def appHome(request):
    return render(request, 'home.html')

def login_view(request):
    return render(request, 'login.html')

def gestor(request):
    hoje = date.today().isoformat() 
    
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
    reservas_canceladas = 0
    receita_cancelada = "0,00"
    ultimas_reservas = []
    
    if id_estacionamento:
        
        try:
            todas_vagas = fi.fetch_query("vaga", "estacionamentoId", "==", id_estacionamento)
            vagas_total = len(todas_vagas)
            try:
                vaga_ids = [v.get('_id') or v.get('id') or '<sem-id>' for v in todas_vagas]
            except Exception:
                vaga_ids = []
            print(f"[DEBUG] Estacionamento {id_estacionamento} - vagas encontradas: {vaga_ids}")
            print(f"[DEBUG] Estacionamento {id_estacionamento} - vagas_total: {vagas_total}")

            vagas_ocupadas_list = fi.fetch_query("vaga", "disponivel", "==", False, conditions=[
                ("estacionamentoId", "==", id_estacionamento)
            ])
            vagas_ocupadas = len(vagas_ocupadas_list)
            print(f"[DEBUG] Estacionamento {id_estacionamento} - vagas_ocupadas_ids: {[v.get('_id') for v in vagas_ocupadas_list]}")
            print(f"[DEBUG] Estacionamento {id_estacionamento} - vagas_ocupadas: {vagas_ocupadas}")

        except Exception:
            pass

        try:

            reservas_hoje_list = fi.fetch_query("reserva", "inicioReserva", "==", hoje, conditions=[
                ("estacionamentoId", "==", id_estacionamento) 
            ])
            reservas_hoje = len(reservas_hoje_list)
        except Exception:
            pass

        try:
            reservas_ativas_list = fi.fetch_query("reserva", "status", "==", "ativa", conditions=[
                ("estacionamentoId", "==", id_estacionamento)
            ]) 
            reservas_pendentes = len(reservas_ativas_list)
        except Exception:
            pass
        try:
            receita_total_float = 0.0
            for reserva in reservas_ativas_list: 
                valor = reserva.get("preco", 0.0) 
                receita_total_float += float(valor) 

            receita_mensal = f"{receita_total_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".");

        except Exception:
            receita_mensal = "0,00"
        
        reservas_canceladas = 0
        receita_cancelada = "0,00"
        try:
            reservas_canceladas_list = fi.fetch_query("reserva", "status", "==", "cancelada", conditions=[
                ("estacionamentoId", "==", id_estacionamento)
            ])
            reservas_canceladas = len(reservas_canceladas_list)
            
            receita_cancelada_float = 0.0
            for reserva in reservas_canceladas_list:
                valor = reserva.get("preco", 0.0)
                receita_cancelada_float += float(valor)
                vagaN = reserva.get("numero", "desconhecido")
            
            receita_cancelada = f"{receita_cancelada_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".");
        except Exception:
            pass
            
        try:
            ultimas_reservas = fi.fetch_query("reserva", "estacionamentoId", "==", id_estacionamento)
            ultimas_reservas = sorted(
                ultimas_reservas,
                key=lambda r: r.get('timestamp') or r.get('dataReserva') or "",
                reverse=True
            )[:5]
            print(f"[DEBUG] Últimas reservas do estacionamento {id_estacionamento}: {len(ultimas_reservas)} encontradas")
            
            #  Buscar o NOME  da vaga
            reservas_com_nome = []
            for reserva in ultimas_reservas:
                reserva_numero = reserva.get("vagaId")
                nome_vaga_completo = "Nome Indisponível"

                if reserva_numero:
                    try:
                        vaga_results = fi.fetch_query("vaga", "vagaId", "==", reserva_numero, conditions=[
                            ("estacionamentoId", "==", id_estacionamento)
                        ])
                        
                        if vaga_results:
                            vaga_doc = vaga_results[0]
                            nome_vaga_completo = vaga_doc.get("nome") or vaga_doc.get("numero") or reserva_numero

                    except Exception as e:
                        print(f"[DEBUG] Erro ao buscar nome da vaga para numero {reserva_numero}: {e}")
                        pass

                reserva['nome_vaga_completo'] = nome_vaga_completo
                reservas_com_nome.append(reserva)

            ultimas_reservas = reservas_com_nome 
            
            for r in ultimas_reservas:
                print(f"[DEBUG] Reserva: {r}")
        except Exception as e:
            print(f"[DEBUG] Erro ao buscar últimas reservas: {e}")
            ultimas_reservas = []
            
    # --- PONTO CHAVE DA CORREÇÃO ---
    # 1. Atualizar o contexto com todos os dados coletados
    context.update({
        'vagas_total': vagas_total,
        'vagas_ocupadas': vagas_ocupadas,
        'reservas_hoje': reservas_hoje,
        'reservas_pendentes': reservas_pendentes,
        'receita_mensal': receita_mensal,
        'reservas_canceladas': reservas_canceladas,
        'receita_cancelada': receita_cancelada,
        'ultimas_reservas': ultimas_reservas,
        'id_estacionamento_usado': id_estacionamento, # Útil para debug
    })
    
    # 2. RETORNAR O HttpResponse (renderizando o template)
    return render(request, 'admin.html', context) # Assumindo que o template se chama 'gestor.html'

def logout_view(request):
    try:
        logout(request)
    except Exception:
        pass
    return HttpResponseRedirect('/login/')