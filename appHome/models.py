from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class NotificacaoAdmin(models.Model):
    TIPOS_NOTIFICACAO = [
        ('estacionamento_reservado', 'Veículo com reserva estacionado'),
        ('estacionamento_sem_reserva', 'Veículo sem reserva estacionado'),

        ('obstrucao_camera', 'Alerta de obstrução na camera'),
        ('alerta_seguranca', 'Alerta de Segurança'),
        ('pagamento_nao_confirmado', 'Pagamento da Reserva não confirmado'),

        ('alerta_saida', 'Alerta de Saída'),
        ('sistema_erro', 'Erro do Sistema'),
        ('sistema_alerta_estacionamento', 'Alerta de Estacionamento'),
    ]
    
    tipo = models.CharField(max_length=50, choices=TIPOS_NOTIFICACAO, default='alerta_seguranca', verbose_name='Tipo de Notificação')
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
        tipo_display = dict(self.TIPOS_NOTIFICACAO).get(self.tipo, self.tipo)
        return f"[{tipo_display}] {self.placa or 'Sem placa'} - {self.timestamp.strftime('%d/%m/%Y %H:%M')}"
