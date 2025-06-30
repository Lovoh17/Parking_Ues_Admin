from django.urls import path
from .views import LoginView,listar_transacciones,GestionUsuarioView,historial_movimientos,exportar_historial, logout_view, dashboard,listar_usuarios,detalle_usuario,ReportesRTDBView,gestion_espacios, perfil_admin

urlpatterns = [
    path('', dashboard, name='home'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', logout_view, name='logout'),
    path('reportes/', ReportesRTDBView.as_view(), name='reportes'),
    path('perfil/', perfil_admin, name='perfil_admin'),
    path('historial/', historial_movimientos, name='historial_movimientos'),
    path('historial/exportar/', exportar_historial, name='exportar_historial'),
    path('transacciones/', listar_transacciones, name='listar_transacciones'),
    
    # URLs de usuarios
    path('usuarios/nuevo/', GestionUsuarioView.as_view(), name='nuevo_usuario'),
    path('usuarios/<str:user_id>/editar/', GestionUsuarioView.as_view(), name='editar_usuario'),
    path('usuarios/<str:user_id>/', detalle_usuario, name='detalle_usuario'),
    path('usuarios/', listar_usuarios, name='listar_usuarios'),
    
    # URLs de estacionamientos
    path('estacionamientos/', gestion_espacios, name='listar_estacionamientos'),
]