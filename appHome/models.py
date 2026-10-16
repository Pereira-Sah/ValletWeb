from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class NotificacaoAdmin(models.Model):
    TIPOS_NOTIFICACAO = [
        ('sistema_alerta_estacionamento', 'Alerta de Estacionamento'),
        ('reserva_confirmada', 'Reserva Confirmada'),
        ('alerta_saida', 'Alerta de Saída Manual'),
        ('sistema_erro', 'Erro do Sistema'),
        ('motorista_incorreto', 'Motorista Incorreto'),
        ('info_geral', 'Informação Geral'),
        ('alerta_seguranca', 'Alerta de Segurança'),
    ]
    
    tipo = models.CharField(max_length=50, choices=TIPOS_NOTIFICACAO, default='info_geral', verbose_name='Tipo de Notificação')
    motivo = models.TextField(verbose_name='Motivo/Descrição')
    timestamp = models.DateTimeField(default=timezone.now, verbose_name='Data/Hora')
    lida = models.BooleanField(default=False, verbose_name='Lida')
    
    vaga_id = models.CharField(max_length=100, blank=True, null=True, verbose_name='ID da Vaga (Firestore)')
    vaga_numero = models.CharField(max_length=20, blank=True, null=True, verbose_name='Número da Vaga')
    placa = models.CharField(max_length=15, blank=True, null=True, verbose_name='Placa do Veículo')
    usuario_id = models.CharField(max_length=100, blank=True, null=True, verbose_name='ID do Usuário (Firestore)')
    estacionamento_id = models.CharField(max_length=100, blank=True, null=True, verbose_name='ID do Estacionamento (Firestore)')
    
    dados_adicionais = models.JSONField(default=dict, blank=True, verbose_name='Dados Adicionais (JSON)')
    
    class Meta:
        db_table = 'notificacoes_admin'
        ordering = ['-timestamp']
        verbose_name = 'Notificação Admin'
        verbose_name_plural = 'Notificações Admin'
    
    def __str__(self):
        # Melhorando a representação para incluir o tipo
        tipo_display = dict(self.TIPOS_NOTIFICACAO).get(self.tipo, self.tipo)
        return f"[{tipo_display}] {self.placa or 'Sem placa'} - {self.timestamp.strftime('%d/%m/%Y %H:%M')}"
