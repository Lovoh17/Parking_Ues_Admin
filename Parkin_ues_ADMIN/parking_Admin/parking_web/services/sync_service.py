import threading
import time
import logging
from django.db import transaction
from firebase_admin import db
from firebase_admin.exceptions import FirebaseError
from models import LocalData

logger = logging.getLogger(__name__)

class SyncService:
    """
    Servicio para manejar la sincronización entre Firebase RTDB y SQLite local
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SyncService, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance
    
    def _initialize(self):
        """Inicialización del servicio singleton"""
        self.sync_interval = 60  # Segundos entre intentos de sincronización
        self.sync_thread = None
        self.running = False
        self.last_sync = None
        self.connection_retries = 3
        self.retry_delay = 5  # Segundos entre reintentos

    def start_sync(self):
        """Inicia el servicio de sincronización en segundo plano"""
        if not self.running:
            self.running = True
            self.sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
            self.sync_thread.start()
            logger.info("Servicio de sincronización iniciado")

    def stop_sync(self):
        """Detiene el servicio de sincronización"""
        if self.running:
            self.running = False
            if self.sync_thread:
                self.sync_thread.join()
            logger.info("Servicio de sincronización detenido")

    def save_data(self, collection, key, data):
        """
        Guarda datos en Firebase o localmente según la conexión
        
        Args:
            collection (str): Nombre de la colección/nodo (ej: 'usuarios')
            key (str): ID del documento/registro
            data (dict): Datos a guardar
        """
        try:
            if self._check_internet_connection():
                self._save_to_firebase(collection, key, data)
                logger.debug(f"Datos guardados en Firebase: {collection}/{key}")
            else:
                self._save_locally(collection, key, data)
                logger.debug(f"Datos guardados localmente: {collection}/{key}")
        except Exception as e:
            logger.error(f"Error al guardar datos {collection}/{key}: {str(e)}")
            raise

    def _save_to_firebase(self, collection, key, data):
        """Guarda datos directamente en Firebase RTDB"""
        for attempt in range(self.connection_retries):
            try:
                ref = db.reference(f'{collection}/{key}')
                ref.set(data)
                return
            except FirebaseError as e:
                if attempt == self.connection_retries - 1:
                    raise
                time.sleep(self.retry_delay)
                continue

    def _save_locally(self, collection, key, data):
        """Guarda datos en SQLite para sincronización posterior"""
        with transaction.atomic():
            LocalData.objects.update_or_create(
                collection=collection,
                key=key,
                defaults={
                    'data': data,
                    'is_synced': False
                }
            )

    def _sync_loop(self):
        """Bucle principal de sincronización"""
        while self.running:
            try:
                if self._check_internet_connection():
                    self._sync_pending_data()
            except Exception as e:
                logger.error(f"Error en el bucle de sincronización: {str(e)}")
            finally:
                time.sleep(self.sync_interval)

    def _sync_pending_data(self):
        """Sincroniza todos los datos pendientes con Firebase"""
        pending_data = LocalData.objects.filter(is_synced=False)
        
        if pending_data.exists():
            logger.info(f"Iniciando sincronización de {pending_data.count()} registros pendientes")
            
            success_count = 0
            for item in pending_data:
                try:
                    self._save_to_firebase(item.collection, item.key, item.data)
                    item.is_synced = True
                    item.save()
                    success_count += 1
                except Exception as e:
                    logger.error(f"Error sincronizando {item.collection}/{item.key}: {str(e)}")
                    # Continúa con los siguientes items
            
            self.last_sync = time.time()
            logger.info(f"Sincronización completada. Éxitos: {success_count}/{pending_data.count()}")

    def _check_internet_connection(self):
        """
        Verifica conexión a internet y acceso a Firebase
        
        Returns:
            bool: True si hay conexión funcional, False si no
        """
        for attempt in range(self.connection_retries):
            try:
                ref = db.reference('.info/connected')
                return ref.get() is True
            except Exception as e:
                if attempt == self.connection_retries - 1:
                    logger.warning("No se pudo verificar conexión con Firebase")
                    return False
                time.sleep(self.retry_delay)
                continue

# Instancia singleton del servicio
sync_service = SyncService()