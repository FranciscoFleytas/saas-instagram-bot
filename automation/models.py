from django.db import models

import uuid
from django.db import models
from cryptography.fernet import Fernet
from django.conf import settings

# Clave de encriptación (En producción, mover a variables de entorno)
# Generar una con: Fernet.generate_key()
ENCRYPTION_KEY = settings.ENCRYPTION_KEY

class Agency(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    plan_level = models.CharField(max_length=50, choices=[('basic', 'Basic'), ('pro', 'Pro')], default='basic')
    payment_status = models.CharField(max_length=20, default='unpaid')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Proxy(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ip_address = models.GenericIPAddressField()
    port = models.IntegerField()
    username = models.CharField(max_length=100)
    password = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.ip_address}:{self.port}"

class IGAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(Agency, on_delete=models.CASCADE)
    username = models.CharField(max_length=100, unique=True)
    last_used = models.DateTimeField(null=True, blank=True, help_text="Marca de tiempo para calcular enfriamiento")
    
    # Almacenamos la contraseña encriptada como bytes o string base64
    password_encrypted = models.BinaryField() 
    
    session_id = models.TextField(null=True, blank=True)
    proxy = models.ForeignKey(Proxy, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=50, default='active') # active, challenge, banned
    
    # Configuración del Bot (JSONB)
    config = models.JSONField(default=dict) # Ej: {"auto_dm": True, "target_niche": "Real Estate"}

    def set_password(self, raw_password):
        f = Fernet(ENCRYPTION_KEY)
        self.password_encrypted = f.encrypt(raw_password.encode())

    def get_password(self):
        """
        Desencripta la contraseña manejando la compatibilidad con PostgreSQL.
        """
        if not self.password_encrypted:
            return None
            
        try:
            f = Fernet(ENCRYPTION_KEY)
            
            # CORRECCIÓN CRÍTICA PARA POSTGRESQL:
            data = self.password_encrypted
            # Si viene como memoryview (Postgres), lo forzamos a bytes
            if isinstance(data, memoryview):
                data = bytes(data)
            # Si ya es bytes (SQLite), lo dejamos igual
            
            return f.decrypt(data).decode()
        except Exception as e:
            print(f"Error desencriptando password para {self.username}: {e}")
            return None

class Lead(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_account = models.CharField(max_length=100) # Desde qué cuenta se extrajo
    ig_username = models.CharField(max_length=100, unique=True)
    
    # Datos scrapeados (Seguidores, Bio, Engagement)
    data = models.JSONField(default=dict)
    
    # CRM Status
    status = models.CharField(max_length=50, default='to_contact') # to_contact, contacted, interested
    created_at = models.DateTimeField(auto_now_add=True)

class SystemLog(models.Model):
    LEVEL_CHOICES = [
        ('info', 'INFO'),
        ('warn', 'WARNING'),
        ('error', 'ERROR'),
        ('success', 'SUCCESS'),
    ]
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default='info')
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.level.upper()}] {self.message}"