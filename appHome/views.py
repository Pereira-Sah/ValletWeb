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
        'receita_mensal': receita_mensal,  # <-- agora calculada corretamente
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
