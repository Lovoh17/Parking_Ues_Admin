from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission
from django.core.validators import EmailValidator
from django.utils.translation import gettext_lazy as _

class Usuario(AbstractUser):
    """
    Modelo personalizado de usuario que extiende AbstractUser
    """
    
    # Campos adicionales
    email = models.EmailField(
        _('email address'),
        unique=True,
        validators=[EmailValidator()],
        help_text=_('Correo electrónico institucional')
    )
    
    ROLES = (
        ('admin', 'Administrador'),
        ('staff', 'Personal'),
        ('user', 'Usuario regular'),
    )
    
    role = models.CharField(
        _('rol'),
        max_length=20,
        choices=ROLES,
        default='user',
        help_text=_('Rol del usuario en el sistema')
    )
    
    # Solución para los conflictos de related_name
    groups = models.ManyToManyField(
        Group,
        verbose_name=_('groups'),
        blank=True,
        help_text=_('The groups this user belongs to.'),
        related_name="usuario_set",  # Cambiado de 'user_set'
        related_query_name="usuario",
    )
    
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name=_('user permissions'),
        blank=True,
        help_text=_('Specific permissions for this user.'),
        related_name="usuario_set",  # Cambiado de 'user_set'
        related_query_name="usuario",
    )
    
    # Metadata
    class Meta:
        verbose_name = _('usuario')
        verbose_name_plural = _('usuarios')
        ordering = ['username']
        db_table = 'usuarios'
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
    @property
    def is_admin(self):
        return self.role == 'admin' or self.is_superuser
    
    @property
    def is_staff_member(self):
        return self.role == 'staff' or self.is_staff