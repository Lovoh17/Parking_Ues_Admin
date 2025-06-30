# api/views.py
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from ..models import ParkingSpace, User, Infraction
from .serializers import ParkingSpaceSerializer, UserSerializer
from services.sync_service import AdvancedSyncService

class ParkingSpaceViewSet(viewsets.ModelViewSet):
    queryset = ParkingSpace.objects.all()
    serializer_class = ParkingSpaceSerializer
    
    @action(detail=True, methods=['post'])
    def occupy(self, request, pk=None):
        space = self.get_object()
        user_id = request.data.get('user_id')
        
        try:
            user = User.objects.get(id=user_id)
            space.occupy(user)
            return Response({'status': 'occupied'})
        except User.DoesNotExist:
            return Response({'error': 'Usuario no encontrado'}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=True, methods=['post'])
    def vacate(self, request, pk=None):
        space = self.get_object()
        space.vacate()
        return Response({'status': 'vacated'})

class SyncViewSet(viewsets.ViewSet):
    @action(detail=False, methods=['post'])
    def force_sync(self, request):
        sync_service = AdvancedSyncService()
        result = sync_service.batch_sync()
        return Response(result)