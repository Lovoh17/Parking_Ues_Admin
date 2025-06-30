from django.db import models
from django.utils import timezone
from .models import BaseModel 
from parking_web.models import User 

class Notification(BaseModel):
    """Sistema de notificaciones para usuarios"""
    LEVEL_CHOICES = [
        ('info', 'Informativo'),
        ('warning', 'Advertencia'),
        ('error', 'Error'),
        ('success', 'Éxito'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=100)
    message = models.TextField()
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='info')
    read = models.BooleanField(default=False)
    related_model = models.CharField(max_length=50, blank=True)
    related_id = models.UUIDField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'read']),
        ]
    
    def __str__(self):
        return f"{self.get_level_display()}: {self.title}"
    
    @classmethod
    def notify_user(cls, user, title, message, level='info', related_model=None, related_id=None):
        """Crea una notificación para el usuario"""
        return cls.objects.create(
            user=user,
            title=title,
            message=message,
            level=level,
            related_model=related_model,
            related_id=related_id
        )
    
    @classmethod
    def notify_sync_status(cls, sync_result):
        """Notifica el resultado de una sincronización"""
        # Implementación para notificar sobre sync completado/fallido
        pass