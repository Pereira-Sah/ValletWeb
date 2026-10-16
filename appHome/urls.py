from django.contrib import admin
from django.urls import path
from appHome import views
from appHome.views import (
    firebase_login,
    NotificacoesAdminView,
    NotificacoesAPIView
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.appHome, name="appHome"),
    path('login/', views.login_view, name="login"),
    path('gestor/', views.gestor, name="gestor"),
    path('logout/', views.logout_view, name="logout"),
    path("auth/firebase/", firebase_login, name="firebase_login"),
    path('notificacoes/', NotificacoesAdminView.as_view(), name='notificacoes_admin'),
    path('notificacoes/api/', NotificacoesAPIView.as_view(), name='notificacoes_api'),
    path('reservas/', views.reservas, name="reservas"),
]