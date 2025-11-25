from django.shortcuts import render
from django.http import JsonResponse, HttpResponseRedirect
from django.conf import settings
import requests
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import login, get_user_model
import json
from firebase_admin import auth as fb_auth
import firebase.firebase_init as fi

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
                # Prefer the explicit settings var, fallback to firebase_init.WEB_API_KEY if present
                api_key = getattr(settings, "FIREBASE_API_KEY", "") or getattr(fi, "WEB_API_KEY", "")
                if not api_key:
                    return JsonResponse({"error": "FIREBASE_API_KEY not set on server"}, status=500)
                try:
                    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
                    r = requests.post(url, json={"email": email, "password": password, "returnSecureToken": True}, timeout=10)
                    # If Firebase returns a non-200, surface the response body when DEBUG for diagnosis
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

        user, _ = User.objects.get_or_create(username=uid, defaults={"email": email})
        login(request, user)

        # Tentar obter dados adicionais do Firestore para decidir redirecionamento
        try:
            # Primeiro, tentar buscar documento com id igual ao uid
            doc = fi.fetch_document("usuario", uid)
        except Exception:
            doc = None

        if not doc and email:
            # fallback: buscar por email
            try:
                results = fi.fetch_query("usuario", "email", "==", email)
                doc = results[0] if results else None
            except Exception:
                doc = None

        is_gestor = False
        if doc:
            tipo = str(doc.get("tipo_user", "")).lower()
            cargo = str(doc.get("cargo", "")).lower()
            if tipo == "admin" or cargo in ("admin", "administrador", "adm", "chefe"):
                is_gestor = True

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

def gestor(request):
    return render(request, 'admin.html')
