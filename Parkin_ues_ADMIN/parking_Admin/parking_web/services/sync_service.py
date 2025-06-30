# sync_service.py - Servicio de sincronización mejorado
import requests
import firebase_admin
from firebase_admin import credentials, db as realtime_db
from django.conf import settings
from django.apps import apps
import logging
import json
import uuid
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.db.models import F
from ..models import SyncQueue


logger = logging.getLogger(__name__)

class AdvancedSyncService:
    def __init__(self):
        self.firebase_enabled = self._initialize_firebase()
        self.max_workers = 4  # Para operaciones concurrentes
        
    def _initialize_firebase(self) -> bool:
        """Configura la conexión con Firebase RTDB"""
        try:
            CREDENTIALS_PATH = Path(__file__).resolve().parent.parent / 'config' / 'serviceAccountKey.json'
            DATABASE_URL = 'https://parkingues-69cfa-default-rtdb.firebaseio.com/'
            
            if CREDENTIALS_PATH.exists() and not firebase_admin._apps:
                cred = credentials.Certificate(str(CREDENTIALS_PATH))
                firebase_admin.initialize_app(cred, {
                    'databaseURL': DATABASE_URL,
                    'databaseAuthVariableOverride': {
                        'uid': 'parking-sync-service'
                    }
                })
            
            self.rtdb = realtime_db.reference()
            logger.info("Firebase RTDB configurado correctamente")
            return True
        except Exception as e:
            logger.error(f"Error configurando Firebase: {e}")
            self.rtdb = None
            return False
    
    def check_connectivity(self, timeout: int = 5) -> bool:
        """Verifica conectividad a Internet y a Firebase"""
        try:
            # Verifica conexión a Internet
            requests.get("https://www.google.com", timeout=timeout)
            
            # Verifica conexión a Firebase
            if self.firebase_enabled:
                test_ref = self.rtdb.child('connection_test')
                test_ref.set({'ping': True, 'timestamp': datetime.utcnow().isoformat()})
                test_ref.delete()
            
            return True
        except Exception as e:
            logger.warning(f"Error de conectividad: {e}")
            return False
    
    def batch_sync(self, batch_size: int = 50) -> Dict[str, int]:
        """Sincroniza operaciones pendientes en lotes con procesamiento concurrente"""
        from ..models import SyncQueue
        
        if not self.check_connectivity():
            return {'status': 'offline', 'processed': 0}
        
        pending_ops = SyncQueue.objects.filter(
            processed=False,
            attempts__lt=F('max_attempts')
        ).order_by('created_at')[:batch_size]
        
        stats = {
            'total': pending_ops.count(),
            'success': 0,
            'failed': 0,
            'retries': 0
        }
        
        # Procesamiento concurrente
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._process_sync_operation, op): op 
                for op in pending_ops
            }
            
            for future in as_completed(futures):
                op = futures[future]
                try:
                    result = future.result()
                    if result['success']:
                        op.processed = True
                        op.save()
                        stats['success'] += 1
                        
                        # Marcar el modelo como sincronizado
                        self._update_sync_status(op.model_name, op.object_id)
                    else:
                        op.attempts += 1
                        op.last_error = result.get('error', '')[:500]
                        op.save()
                        stats['failed'] += 1
                        stats['retries'] += 1
                except Exception as e:
                    logger.error(f"Error procesando operación {op.id}: {e}")
                    op.attempts += 1
                    op.last_error = str(e)[:500]
                    op.save()
                    stats['failed'] += 1
        
        logger.info(f"Sincronización por lotes completada. Estadísticas: {stats}")
        return stats
    
    def _process_sync_operation(self, sync_op: SyncQueue) -> Dict[str, Any]:
        """Procesa una operación individual de sincronización"""
        try:
            # Mapeo de modelos a nodos RTDB
            model_mapping = {
                'User': 'users',
                'ParkingSpace': 'parking_spaces',
                'MembershipPlan': 'membership_plans',
                'UserMembership': 'user_memberships',
                'Infraction': 'infractions',
                'CodigoAcceso': 'access_codes',
                'ParkingSession': 'parking_sessions'
            }
            
            node_name = model_mapping.get(sync_op.model_name)
            if not node_name:
                return {
                    'success': False,
                    'error': f"Modelo {sync_op.model_name} no mapeado"
                }
            
            node_ref = self.rtdb.child(node_name).child(str(sync_op.object_id))
            
            if sync_op.operation == 'DELETE':
                node_ref.delete()
                return {'success': True}
            
            # Para CREATE y UPDATE
            data = sync_op.data
            
            # Asegurar campos de sincronización
            data['_synced_at'] = datetime.utcnow().isoformat()
            data['_sync_version'] = data.get('sync_version', 1) + 1
            
            if sync_op.operation == 'CREATE':
                # Verificar conflicto en creación
                existing = node_ref.get()
                if existing:
                    return self._resolve_conflict(node_ref, existing, data, sync_op)
            
            node_ref.set(data)
            return {'success': True}
            
        except Exception as e:
            error_msg = f"Error en {sync_op.operation} {sync_op.model_name}: {str(e)}"
            logger.error(error_msg)
            return {'success': False, 'error': error_msg}
    
    def _resolve_conflict(self, node_ref, existing_data, new_data, sync_op):
        """Resuelve conflictos de sincronización"""
        # Estrategia: Conservar la versión más reciente
        existing_updated = existing_data.get('updated_at')
        new_updated = new_data.get('updated_at')
        
        if not existing_updated or (new_updated and new_updated > existing_updated):
            node_ref.set(new_data)
            return {'success': True}
        
        # Actualizar localmente con datos remotos si son más recientes
        try:
            model_class = apps.get_model('parking', sync_op.model_name)
            obj = model_class.objects.get(id=sync_op.object_id)
            
            for field, value in existing_data.items():
                if hasattr(obj, field) and not field.startswith('_'):
                    setattr(obj, field, value)
            
            obj.synced = True
            obj.save()
            sync_op.processed = True
            sync_op.save()
            
            return {'success': True, 'resolved': 'local_updated'}
        except Exception as e:
            error_msg = f"Error resolviendo conflicto: {str(e)}"
            logger.error(error_msg)
            return {'success': False, 'error': error_msg}
    
    def _update_sync_status(self, model_name: str, object_id: uuid.UUID):
        """Actualiza el estado de sincronización en el modelo local"""
        try:
            model_class = apps.get_model('parking', model_name)
            obj = model_class.objects.get(id=object_id)
            obj.synced = True
            obj.sync_version = F('sync_version') + 1
            obj.save(update_fields=['synced', 'sync_version'])
        except Exception as e:
            logger.warning(f"No se pudo actualizar estado de sync para {model_name} {object_id}: {e}")