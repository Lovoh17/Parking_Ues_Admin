import os
import logging
from pathlib import Path
import firebase_admin
from firebase_admin import credentials, db as realtime_db  # Cambio clave aquí
from django.conf import settings

logger = logging.getLogger(__name__)

class FirebaseConfig:
    """Configuración centralizada para Firebase Realtime Database"""
    
    def __init__(self):
        self.rtdb = None  # Cambiamos db por rtdb
        self._initialized = False
        self.setup_firebase()
    
    def setup_firebase(self):
        """Inicializa Firebase RTDB de forma segura"""
        try:
            # Ruta del archivo de credenciales (igual que antes)
            credentials_path = getattr(
                settings, 
                'FIREBASE_CREDENTIALS_PATH',
                Path(settings.BASE_DIR) / 'config' / 'firebase_config.json'
            )
            
            if not credentials_path.exists():
                raise FileNotFoundError(f"Credenciales no encontradas: {credentials_path}")
            
            # URL de tu RTDB (¡Obtén esta URL de tu consola Firebase!)
            database_url = getattr(
                settings,
                'FIREBASE_DATABASE_URL',
                'https://parkingues-69cfa-default-rtdb.firebaseio.com/'  # Reemplaza con tu URL
            )
            
            # Inicializar Firebase solo si no está inicializado
            if not firebase_admin._apps:
                cred = credentials.Certificate(str(credentials_path))
                firebase_admin.initialize_app(cred, {
                    'databaseURL': database_url  # Configuración específica para RTDB
                })
                logger.info("Firebase RTDB inicializado correctamente")
            
            # Obtener referencia a la base de datos
            self.rtdb = realtime_db.reference()  # Cambio clave aquí
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Error configurando Firebase RTDB: {str(e)}")
            self._initialized = False
            self.rtdb = None
    
    @property
    def is_initialized(self):
        return self._initialized and self.rtdb is not None
    
    def test_connection(self):
        """Prueba la conexión con RTDB"""
        if not self.is_initialized:
            return False
        
        try:
            # Prueba simple de escritura/lectura en RTDB
            test_ref = self.rtdb.child('connection_test/ping')
            test_ref.set({
                'timestamp': {'.sv': 'timestamp'},  # Sintaxis diferente para timestamp
                'status': 'active'
            })
            
            # Verificar que se escribió correctamente
            data = test_ref.get()
            return data is not None
            
        except Exception as e:
            logger.error(f"Error en test de conexión RTDB: {str(e)}")
            return False

# Instancia global
firebase_config = FirebaseConfig()

# Exportar referencia para uso fácil
rtdb = firebase_config.rtdb if firebase_config.is_initialized else None
FIREBASE_ENABLED = firebase_config.is_initialized