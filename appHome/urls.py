from appHome.views import firebase_login
from django.contrib import admin
from django.urls import path
from appHome import views
from appHome.views import NotificacoesAdminView, NotificacoesAPIView, NotificacoesCheckNewView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.appHome, name="appHome"),
    path('login/', views.login_view, name="login"),
    path('gestor/', views.gestor, name="gestor"),
    path('logout/', views.logout_view, name="logout"),
    path("auth/firebase/", firebase_login, name="firebase_login"),
    path('notificacoes/', NotificacoesAdminView.as_view(), name='notificacoes_admin'),
    path('api/notificacoes/', NotificacoesAPIView.as_view(), name='api_notificacoes'),
    path('api/notificacoes/atualizacao/', NotificacoesAPIView.as_view(), name='notificacoes_atualizacao'),
    path('notificacoes/api/check-new/', NotificacoesCheckNewView.as_view(), name='notificacoes_check_new'),
    path('reservas/', views.reservas, name="reservas"),
]
