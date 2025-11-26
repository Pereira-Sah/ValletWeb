from appHome.views import firebase_login
from django.contrib import admin
from django.urls import path
from appHome import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.appHome, name="appHome"),
    path('login/', views.login_view, name="login"),
    path('gestor/', views.gestor, name="gestor"),
    path('logout/', views.logout_view, name="logout"),
    path("auth/firebase/", firebase_login, name="firebase_login"),
    path('notificacoes/', views.NotificacoesAdminView.as_view(), name='notificacoes_admin'),
    path('api/notificacoes/', views.NotificacoesAPIView.as_view(), name='api_notificacoes'),
    path('api/notificacoes/sincronizar/', views.SincronizarNotificacoesView.as_view(), name='sincronizar_notificacoes'),
    path('api/notificacoes/debug/', views.DebugNotificacoesView.as_view(), name='debug_notificacoes'),  # 🔥 NOVA
# urls.py
    path('api/notificacoes/sincronizacao-agressiva/', views.SincronizacaoAgressivaView.as_view(), name='sincronizacao_agressiva'),
]
