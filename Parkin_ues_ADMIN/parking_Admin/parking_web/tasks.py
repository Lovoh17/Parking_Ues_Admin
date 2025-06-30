# tasks.py
from celery import shared_task
from services.sync_service import AdvancedSyncService
from .notifications import Notification
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def sync_parking_data(self, batch_size=100):
    """Tarea Celery para sincronización periódica"""
    try:
        sync_service = AdvancedSyncService()
        result = sync_service.batch_sync(batch_size)
        
        # Notificar resultados importantes
        if result['failed'] > 0:
            Notification.notify_sync_status(result)
        
        return result
    except Exception as e:
        logger.error(f"Error en sync_parking_data: {e}")
        self.retry(exc=e, countdown=60)