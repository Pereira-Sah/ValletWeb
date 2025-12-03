from .models import NotificacaoAdmin

def notificacoes_globais(request):
    if request.user.is_authenticated:
        return {
            'notificacoes_nao_lidas': NotificacaoAdmin.objects.filter(lida=False).count()
        }
    return {}