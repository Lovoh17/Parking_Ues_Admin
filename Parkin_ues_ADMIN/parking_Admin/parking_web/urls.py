from django.urls import path
from .views import LoginView,GestionUsuarioView, logout_view, dashboard,listar_registros,listar_usuarios,detalle_usuario,ReporteVehiculosView,gestion_espacios, perfil_admin

urlpatterns = [
    path('', dashboard, name='home'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', logout_view, name='logout'),
    path('reportes/', ReporteVehiculosView.as_view(), name='reportes'),
    path('registros/', listar_registros, name='listar_registros'),
    path('perfil/', perfil_admin, name='perfil_admin'),
    
    # URLs de usuarios
    path('usuarios/nuevo/', GestionUsuarioView.as_view(), name='nuevo_usuario'),
    path('usuarios/<str:user_id>/editar/', GestionUsuarioView.as_view(), name='editar_usuario'),
    path('usuarios/<str:user_id>/', detalle_usuario, name='detalle_usuario'),
    path('usuarios/', listar_usuarios, name='listar_usuarios'),
    
    # URLs de estacionamientos
    path('estacionamientos/', gestion_espacios, name='listar_estacionamientos'),
]