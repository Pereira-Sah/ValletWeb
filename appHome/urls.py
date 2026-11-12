from django.contrib import admin
from django.urls import path
from appHome import views
from appHome.views import (
    firebase_login,
    NotificacoesAdminView,
    NotificacoesAPIView,
    NotificacoesResumoView,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.appHome, name="appHome"),
    path('login/', views.login_view, name="login"),
    path('gestor/', views.gestor, name="gestor"),
    path('gestor/dados/', views.gestor_dashboard_dados, name="gestor_dashboard_dados"),
    path('chat/', views.chat, name="chat"),
    path('chat/token/', views.chat_token, name="chat_token"),
    path('logout/', views.logout_view, name="logout"),
    path("auth/firebase/", firebase_login, name="firebase_login"),
    path("auth/recuperar-senha/", views.recuperar_senha, name="recuperar_senha"),
    path("contato/enviar/", views.contato, name="contato_enviar"),
    path('notificacoes/', NotificacoesAdminView.as_view(), name='notificacoes_admin'),
    path('notificacoes/resumo/', NotificacoesResumoView.as_view(), name='notificacoes_resumo'),
    path('notificacoes/api/', NotificacoesAPIView.as_view(), name='notificacoes_api'),
    path('reservas/', views.reservas, name="reservas"),
]