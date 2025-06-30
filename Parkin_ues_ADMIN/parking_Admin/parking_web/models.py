# models.py - Sistema de Parking con Django y SQLite
import uuid
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import AbstractUser

class BaseModel(models.Model):
    """Modelo base con campos comunes para auditoría y sincronización"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    
    # Campos para sincronización offline
    synced = models.BooleanField(default=False, db_index=True)
    sync_version = models.PositiveIntegerField(default=1)
    
    class Meta:
        abstract = True
        ordering = ['-created_at']

class User(BaseModel):
    """Usuario del sistema de parking"""
    ROLE_CHOICES = [
        ('admin', 'Administrador'),
        ('cliente', 'Cliente'),
        ('operador', 'Operador'),
    ]
    
    PLAN_TYPE_CHOICES = [
        ('none', 'Sin Plan'),
        ('basic', 'Básico'),
        ('standard', 'Estándar'),
        ('vip', 'VIP'),
    ]
    
    # Campos principales
    user_id = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True, db_index=True)
    phone = models.CharField(max_length=20, blank=True)
    
    # Campos adicionales del JSON
    apellido = models.CharField(max_length=100, blank=True)
    nombre = models.CharField(max_length=100, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    
    # Configuración del usuario
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='cliente', db_index=True)
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPE_CHOICES, default='none', db_index=True)
    
    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
        indexes = [
            models.Index(fields=['email', 'is_active']),
            models.Index(fields=['role', 'plan_type']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.email})"
    
    @property
    def full_name(self):
        """Nombre completo del usuario"""
        if self.nombre and self.apellido:
            return f"{self.nombre} {self.apellido}"
        return self.name
    
    @property
    def primary_phone(self):
        """Teléfono principal del usuario"""
        return self.telefono or self.phone

class ParkingSpace(BaseModel):
    """Espacio de estacionamiento"""
    SECTION_CHOICES = [
        ('normal', 'Normal'),
        ('vip', 'VIP'),
        ('disabled', 'Discapacitados'),
        ('electric', 'Vehículos Eléctricos'),
    ]
    
    # Identificación del espacio
    space_id = models.CharField(max_length=50, unique=True, db_index=True)
    space_number = models.PositiveIntegerField(db_index=True)
    section = models.CharField(max_length=20, choices=SECTION_CHOICES, default='normal', db_index=True)
    
    # Estado del espacio
    occupied = models.BooleanField(default=False, db_index=True)
    reserved = models.BooleanField(default=False, db_index=True)
    occupied_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='current_spaces')
    
    # Tiempos de ocupación
    occupation_start_time = models.DateTimeField(null=True, blank=True)
    current_occupation_duration = models.PositiveIntegerField(default=0, help_text="Duración en minutos")
    total_occupation_time = models.PositiveIntegerField(default=0, help_text="Tiempo total en minutos")
    combined_occupation_time = models.PositiveIntegerField(default=0, help_text="Tiempo combinado en minutos")
    
    # Metadatos
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Espacio de Estacionamiento'
        verbose_name_plural = 'Espacios de Estacionamiento'
        unique_together = ['space_number', 'section']
        indexes = [
            models.Index(fields=['section', 'occupied']),
            models.Index(fields=['occupied', 'reserved']),
            models.Index(fields=['space_number', 'section']),
        ]
    
    def __str__(self):
        return f"Espacio {self.space_number} - {self.get_section_display()}"
    
    @property
    def formatted_occupation_time(self):
        """Tiempo de ocupación formateado"""
        if self.current_occupation_duration == 0:
            return "0m"
        
        hours = self.current_occupation_duration // 60
        minutes = self.current_occupation_duration % 60
        
        if hours > 0:
            return f"{hours}h {minutes:02d}m"
        return f"{minutes}m"
    
    @property
    def is_available(self):
        """Verifica si el espacio está disponible"""
        return not self.occupied and not self.reserved and self.is_active
    
    def occupy(self, user):
        """Ocupa el espacio con un usuario"""
        self.occupied = True
        self.occupied_by = user
        self.occupation_start_time = timezone.now()
        self.save()
    
    def vacate(self):
        """Libera el espacio"""
        if self.occupation_start_time:
            duration = timezone.now() - self.occupation_start_time
            self.current_occupation_duration = int(duration.total_seconds() / 60)
            self.total_occupation_time += self.current_occupation_duration
            self.combined_occupation_time += self.current_occupation_duration
        
        self.occupied = False
        self.occupied_by = None
        self.occupation_start_time = None
        self.save()

class MembershipPlan(BaseModel):
    """Planes de membresía"""
    # Identificación
    plan_id = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Configuración del plan
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    duration_days = models.PositiveIntegerField(default=30)
    
    # Beneficios (almacenados como JSON para flexibilidad)
    benefits = models.JSONField(default=list, blank=True)
    
    class Meta:
        verbose_name = 'Plan de Membresía'
        verbose_name_plural = 'Planes de Membresía'
        indexes = [
            models.Index(fields=['is_active', 'price']),
        ]
    
    def __str__(self):
        return f"{self.name} - ${self.price}"
    
    @property
    def benefits_list(self):
        """Lista de beneficios como string"""
        return ", ".join(self.benefits) if self.benefits else "Sin beneficios"

class UserMembership(BaseModel):
    """Membresías activas de usuarios"""
    PAYMENT_METHOD_CHOICES = [
        ('credit_card', 'Tarjeta de Crédito'),
        ('debit_card', 'Tarjeta de Débito'),
        ('paypal', 'PayPal'),
        ('cash', 'Efectivo'),
        ('bank_transfer', 'Transferencia Bancaria'),
    ]
    
    # Identificación
    membership_id = models.CharField(max_length=50, unique=True, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='memberships')
    plan = models.ForeignKey(MembershipPlan, on_delete=models.CASCADE, related_name='memberships')
    
    # Fechas de vigencia
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField()
    
    # Información de pago
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    transaction_id = models.CharField(max_length=100, blank=True)
    
    class Meta:
        verbose_name = 'Membresía de Usuario'
        verbose_name_plural = 'Membresías de Usuarios'
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['end_date', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.user.name} - {self.plan.name}"
    
    @property
    def is_expired(self):
        """Verifica si la membresía ha expirado"""
        return timezone.now() > self.end_date
    
    @property
    def days_remaining(self):
        """Días restantes de la membresía"""
        if self.is_expired:
            return 0
        delta = self.end_date - timezone.now()
        return delta.days
    
    def save(self, *args, **kwargs):
        if not self.end_date:
            self.end_date = self.start_date + timezone.timedelta(days=self.plan.duration_days)
        super().save(*args, **kwargs)

class Infraction(BaseModel):
    """Infracciones de estacionamiento"""
    INFRACTION_TYPE_CHOICES = [
        ('fuera del rango de horas', 'Fuera del Rango de Horas'),
        ('sin pago', 'Sin Pago'),
        ('exceso de tiempo', 'Exceso de Tiempo'),
        ('zona prohibida', 'Zona Prohibida'),
        ('espacio reservado', 'Espacio Reservado'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('paid', 'Pagada'),
        ('cancelled', 'Cancelada'),
        ('expired', 'Vencida'),
    ]
    
    # Identificación
    infraction_id = models.CharField(max_length=50, unique=True, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='infractions')
    parking_space = models.ForeignKey(ParkingSpace, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Detalles de la infracción
    infraction_type = models.CharField(max_length=50, choices=INFRACTION_TYPE_CHOICES, db_index=True)
    description = models.TextField()
    fine = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    
    # Estado y fechas
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    infraction_date = models.DateTimeField(default=timezone.now, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    
    # Información de sesión
    session_id = models.CharField(max_length=50, blank=True)
    
    class Meta:
        verbose_name = 'Infracción'
        verbose_name_plural = 'Infracciones'
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['infraction_date', 'status']),
            models.Index(fields=['infraction_type', 'status']),
        ]
    
    def __str__(self):
        return f"Infracción {self.infraction_id} - {self.user.name} - ${self.fine}"
    
    @property
    def is_paid(self):
        """Verifica si la infracción está pagada"""
        return self.status == 'paid'
    
    def mark_as_paid(self):
        """Marca la infracción como pagada"""
        self.status = 'paid'
        self.resolved_at = timezone.now()
        self.save()

class CodigoAcceso(BaseModel):
    """Códigos de acceso al sistema de parking"""
    STATUS_CHOICES = [
        ('Permitido', 'Permitido'),
        ('Denegado', 'Denegado'),
        ('Suspendido', 'Suspendido'),
    ]
    
    # Código de acceso
    codigo = models.CharField(max_length=20, unique=True, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='access_codes', null=True, blank=True)
    
    # Estado del código
    disponible = models.BooleanField(default=True, db_index=True)
    registrado = models.BooleanField(default=False, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Permitido', db_index=True)
    
    # Configuración de uso
    expires_at = models.DateTimeField(null=True, blank=True)
    uses_count = models.PositiveIntegerField(default=0)
    max_uses = models.PositiveIntegerField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Código de Acceso'
        verbose_name_plural = 'Códigos de Acceso'
        indexes = [
            models.Index(fields=['codigo', 'status']),
            models.Index(fields=['disponible', 'registrado']),
        ]
    
    def __str__(self):
        return f"Código {self.codigo} - {self.get_status_display()}"
    
    @property
    def is_valid(self):
        """Verifica si el código es válido"""
        if not self.disponible or self.status != 'Permitido':
            return False
        
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        
        if self.max_uses and self.uses_count >= self.max_uses:
            return False
        
        return True
    
    def use_code(self):
        """Incrementa el contador de usos"""
        if self.is_valid:
            self.uses_count += 1
            self.save()
            return True
        return False

class ParkingSession(BaseModel):
    """Sesiones de estacionamiento"""
    session_id = models.CharField(max_length=50, unique=True, db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='parking_sessions')
    parking_space = models.ForeignKey(ParkingSpace, on_delete=models.CASCADE, related_name='sessions')
    access_code = models.ForeignKey(CodigoAcceso, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Tiempos de sesión
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(default=0)
    
    # Información de pago
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_status = models.CharField(max_length=20, default='pending')
    
    class Meta:
        verbose_name = 'Sesión de Estacionamiento'
        verbose_name_plural = 'Sesiones de Estacionamiento'
        indexes = [
            models.Index(fields=['user', 'start_time']),
            models.Index(fields=['parking_space', 'start_time']),
        ]
    
    def __str__(self):
        return f"Sesión {self.session_id} - {self.user.name}"
    
    def end_session(self):
        """Finaliza la sesión de estacionamiento"""
        if not self.end_time:
            self.end_time = timezone.now()
            duration = self.end_time - self.start_time
            self.duration_minutes = int(duration.total_seconds() / 60)
            self.save()
            
            # Liberar el espacio
            if self.parking_space:
                self.parking_space.vacate()

class SyncQueue(models.Model):
    """Cola para sincronización de datos offline"""
    OPERATION_CHOICES = [
        ('CREATE', 'Crear'),
        ('UPDATE', 'Actualizar'),
        ('DELETE', 'Eliminar'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    model_name = models.CharField(max_length=50, db_index=True)
    object_id = models.UUIDField(db_index=True)
    operation = models.CharField(max_length=10, choices=OPERATION_CHOICES, db_index=True)
    data = models.JSONField()
    
    # Control de reintentos
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=3)
    last_error = models.TextField(blank=True)
    processed = models.BooleanField(default=False, db_index=True)
    
    class Meta:
        verbose_name = 'Cola de Sincronización'
        verbose_name_plural = 'Colas de Sincronización'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['processed', 'created_at']),
            models.Index(fields=['model_name', 'operation']),
        ]
    
    def __str__(self):
        return f"{self.get_operation_display()} {self.model_name} {self.object_id}"
    
    @property
    def can_retry(self):
        """Verifica si se puede reintentar la operación"""
        return self.attempts < self.max_attempts and not self.processed