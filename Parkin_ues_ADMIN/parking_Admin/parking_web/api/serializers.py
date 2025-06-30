# api/serializers.py
from rest_framework import serializers
from ..models import *

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at', 'synced')

class ParkingSpaceSerializer(serializers.ModelSerializer):
    current_occupation_duration = serializers.SerializerMethodField()
    
    class Meta:
        model = ParkingSpace
        fields = '__all__'
    
    def get_current_occupation_duration(self, obj):
        return obj.formatted_occupation_time

class InfractionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Infraction
        fields = '__all__'
        read_only_fields = ('infraction_date', 'resolved_at')