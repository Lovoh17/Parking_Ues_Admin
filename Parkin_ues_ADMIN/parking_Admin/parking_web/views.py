###################################### IMPORTES NECESARIOS PARA LAS VISTAS ######################################
from django.shortcuts import render, redirect,Http404
from django.views.generic import View
import logging
from pathlib import Path
from django.http import JsonResponse
from django.views.generic import TemplateView
from firebase_admin import db as realtime_db
from firebase_admin import db, auth
from datetime import datetime
from datetime import datetime, timedelta
from django.contrib import messages
import hashlib
from django.shortcuts import get_object_or_404
import csv
from datetime import datetime, timedelta
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views import View
from django.template.loader import get_template
from xhtml2pdf import pisa
from openpyxl import Workbook
from datetime import datetime, timedelta
from collections import defaultdict
###################################################################################################################

###################################### FUNCIONES PARA LA CONECCION DE REALTIME DATABASE ###########################
try:
    import firebase_admin
    from firebase_admin import credentials, db as realtime_db
    
    CREDENTIALS_PATH = Path(__file__).resolve().parent.parent / 'config' / 'serviceAccountKey.json'
    DATABASE_URL = 'https://parkingues-69cfa-default-rtdb.firebaseio.com/'
    
    if CREDENTIALS_PATH.exists() and not firebase_admin._apps:
        cred = credentials.Certificate(str(CREDENTIALS_PATH))
        firebase_admin.initialize_app(cred, {'databaseURL': DATABASE_URL})
        rtdb = realtime_db.reference()
        FIREBASE_ENABLED = True
    else:
        rtdb = None
        FIREBASE_ENABLED = False
        
except Exception as e:
    logging.error(f"Error configurando Firebase: {e}")
    rtdb = None
    FIREBASE_ENABLED = False


def check_connection(request):
    """Vista simplificada solo para verificar conexión"""
    if not FIREBASE_ENABLED:
        return JsonResponse({
            'status': 'disabled',
            'message': 'Firebase no configurado'
        }, status=503)
    
    try:
        # Prueba mínima de conexión
        test_ref = rtdb.child('connection_test')
        test_ref.set({'ping': True})
        return JsonResponse({
            'status': 'connected',
            'message': 'Conexión exitosa con Firebase'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)
        

######################################### HOME ###################################################################

def dashboard(request):
    if not FIREBASE_ENABLED:
        return render(request, 'home.html', {
            'error': 'Firebase no está configurado correctamente'
        })

    try:
        # 1. Datos de espacios de parqueo
        espacios_ref = realtime_db.reference('parking_spaces')
        espacios_data = espacios_ref.get() or {}
        
        espacios_lista = []
        espacios_disponibles = 0
        vehiculos_actuales = 0
        espacios_vip = 0

        for espacio_id, espacio_data in espacios_data.items():
            if not isinstance(espacio_data, dict):
                continue
                
            ocupado = espacio_data.get('occupied', False)
            es_vip = espacio_data.get('section', 'normal') == 'vip'
            
            espacio = {
                'id': espacio_id,
                'numero': espacio_data.get('spaceNumber', espacio_id.split('_')[-1]),
                'disponible': not ocupado,
                'ocupado_por': espacio_data.get('occupiedByUserId', ''),
                'tipo': 'vip' if es_vip else 'normal',
                'tiempo_ocupado': espacio_data.get('formattedOccupationTime', ''),
                'ultima_actualizacion': espacio_data.get('lastUpdated', ''),
                'hora_ocupacion': espacio_data.get('occupationStartTime', '')
            }
            
            espacios_lista.append(espacio)
            if not ocupado:
                espacios_disponibles += 1
            else:
                vehiculos_actuales += 1
                
            if es_vip:
                espacios_vip += 1

        capacidad_total = len(espacios_lista)
        ocupacion_porcentaje = round((vehiculos_actuales / capacidad_total) * 100) if capacidad_total > 0 else 0

        # 2. Datos de usuarios
        usuarios_ref = realtime_db.reference('users')
        usuarios_data = usuarios_ref.get() or {}
        total_usuarios = len(usuarios_data)
        usuarios_activos = sum(1 for u in usuarios_data.values() if isinstance(u, dict) and u.get('active', False))

        # 3. Datos de transacciones
        transacciones_ref = realtime_db.reference('transactions')
        transacciones_data = transacciones_ref.get() or {}
        
        hoy = datetime.now().date()
        ingresos_hoy = 0
        ingresos_mes = 0
        total_transacciones = 0
        
        for trans_id, trans_data in transacciones_data.items():
            if not isinstance(trans_data, dict):
                continue
                
            try:
                monto = float(trans_data.get('amount', 0))
                fecha_str = trans_data.get('timestamp', '')
                if fecha_str:
                    fecha = datetime.strptime(fecha_str, '%Y-%m-%d %H:%M:%S').date()
                    
                    total_transacciones += 1
                    if fecha == hoy:
                        ingresos_hoy += monto
                    if fecha.month == hoy.month and fecha.year == hoy.year:
                        ingresos_mes += monto
            except (ValueError, TypeError):
                continue

        # 4. Datos de infracciones mejorados
        infracciones_ref = realtime_db.reference('infractions')
        infracciones_data = infracciones_ref.get() or {}
        infracciones_hoy = 0
        total_infracciones = len(infracciones_data)
        infracciones_lista = []
        
        # Función auxiliar para formatear timestamp
        def formatear_fecha_infraccion(timestamp_data):
            if not isinstance(timestamp_data, dict):
                return 'Fecha no disponible'
            
            try:
                year = timestamp_data.get('year', 0)
                month = timestamp_data.get('month', 0)
                day = timestamp_data.get('day', 0)
                hours = timestamp_data.get('hours', 0)
                minutes = timestamp_data.get('minutes', 0)
                
                fecha = datetime(year, month, day, hours, minutes)
                return fecha.strftime('%d/%m/%Y %H:%M')
            except (ValueError, TypeError):
                return 'Fecha inválida'

        def formatear_fecha_corta(timestamp_data):
            if not isinstance(timestamp_data, dict):
                return None
            
            try:
                year = timestamp_data.get('year', 0)
                month = timestamp_data.get('month', 0)
                day = timestamp_data.get('day', 0)
                
                fecha = datetime(year, month, day)
                return fecha.date()
            except (ValueError, TypeError):
                return None

        # Procesar infracciones
        for inf_id, inf_data in infracciones_data.items():
            if not isinstance(inf_data, dict):
                continue
            
            timestamp_data = inf_data.get('timestamp', {})
            fecha_formateada = formatear_fecha_infraccion(timestamp_data)
            fecha_obj = formatear_fecha_corta(timestamp_data)
            
            # Contar infracciones de hoy
            if fecha_obj and fecha_obj == hoy:
                infracciones_hoy += 1
            
            # Agregar a la lista para mostrar
            infraccion = {
                'id': inf_id,
                'infraction_id': inf_data.get('infractionId', inf_id),
                'descripcion': inf_data.get('description', 'Sin descripción'),
                'tipo': inf_data.get('infractionType', 'Desconocido'),
                'usuario_id': inf_data.get('userId', 'No identificado'),
                'session_id': inf_data.get('sessionId', 'Sin sesión'),
                'multa': inf_data.get('fine', 0),
                'estado': inf_data.get('status', 'pending'),
                'fecha_completa': fecha_formateada,
                'fecha_obj': fecha_obj
            }
            
            infracciones_lista.append(infraccion)

        # Ordenar infracciones por fecha (más recientes primero)
        infracciones_lista.sort(key=lambda x: x['fecha_obj'] or datetime.min.date(), reverse=True)

        # 5. Datos de vehículos
        vehiculos_ref = realtime_db.reference('vehicles')
        vehiculos_data = vehiculos_ref.get() or {}
        total_vehiculos = len(vehiculos_data)
        vehiculos_registrados_hoy = sum(
            1 for v in vehiculos_data.values() 
            if isinstance(v, dict) and 
            v.get('registrationDate', '').startswith(hoy.strftime('%Y-%m-%d'))
        )

        # Preparar contexto
        context = {
            # Espacios
            'espacios': espacios_lista[:8],  # Mostrar solo 8 para el preview
            'espacios_disponibles': espacios_disponibles,
            'vehiculos_actuales': vehiculos_actuales,
            'capacidad_total': capacidad_total,
            'ocupacion_porcentaje': ocupacion_porcentaje,
            'espacios_vip': espacios_vip,
            
            # Usuarios
            'total_usuarios': total_usuarios,
            'usuarios_activos': usuarios_activos,
            'usuarios_nuevos_hoy': 0,  # Puedes agregar esta métrica
            
            # Transacciones
            'ingresos_hoy': round(ingresos_hoy, 2),
            'ingresos_mes': round(ingresos_mes, 2),
            'total_transacciones': total_transacciones,
            'transacciones_hoy': sum(1 for t in transacciones_data.values() 
                                   if isinstance(t, dict) and 
                                   t.get('timestamp', '').startswith(hoy.strftime('%Y-%m-%d'))),
            
            # Infracciones - datos reales
            'infracciones_hoy': infracciones_hoy,
            'total_infracciones': total_infracciones,
            'infracciones_lista': infracciones_lista[:5],  # Mostrar solo las 5 más recientes
            
            # Vehículos
            'total_vehiculos': total_vehiculos,
            'vehiculos_registrados_hoy': vehiculos_registrados_hoy,
            
            # General
            'ultima_actualizacion': datetime.now().strftime('%d/%m/%Y %H:%M')
        }
        
        return render(request, 'home.html', context)

    except Exception as e:
        logging.error(f"Error en dashboard: {str(e)}")
        return render(request, 'home.html', {
            'error': 'Error al cargar datos del sistema',
            'espacios': [],
            'total_usuarios': 0,
            'ingresos_hoy': 0,
            'infracciones_hoy': 0,
            'total_infracciones': 0,
            'infracciones_lista': [],
            'total_vehiculos': 0
        })

################################################### lOGIN ########################################################

class LoginView(View):
    template_name = 'login.html'
    
    def get(self, request):
        if request.session.get('firebase_user'):
            return redirect('home')
            
        return render(request, self.template_name, {
            'next': request.GET.get('next', '/')
        })

    def post(self, request):
        username = request.POST.get('username')
        password = request.POST.get('password')
        next_url = request.POST.get('next', '/')
        
        try:
            users_ref = realtime_db.reference('users')  # Cambié a 'users' (mejor práctica)
            all_users = users_ref.get()
            
            # Si no existe el nodo o está vacío, lo creamos con el usuario admin
            if not all_users:
                admin_user = {
                    'admin': {
                        'username': 'admin',
                        'password': 'admin123',  # En producción usa hash!
                        'email': 'admin@ues.edu.sv',
                        'role': 'admin'
                    }
                }
                users_ref.set(admin_user)
                all_users = admin_user  # Usamos los datos recién creados
            
            # Si existe pero es string (error), lo convertimos a diccionario
            elif isinstance(all_users, str):
                users_ref.set({})  # Creamos estructura vacía
                all_users = {}
            
            user_data = None
            for user_id, user_dict in all_users.items():
                if isinstance(user_dict, dict) and user_dict.get('username') == username:
                    user_data = user_dict
                    user_data['id'] = user_id
                    break
            
            if not user_data:
                return render(request, self.template_name, {
                    'error': 'Usuario no encontrado',
                    'next': next_url
                })
            
            if user_data.get('password') == password:
                request.session['firebase_user'] = {
                    'id': user_id,
                    'username': user_data['username'],
                    'email': user_data.get('email', ''),
                    'role': user_data.get('role', 'user')
                }
                return redirect(next_url)
                
            return render(request, self.template_name, {
                'error': 'Contraseña incorrecta',
                'next': next_url
            })
            
        except Exception as e:
            print(f"Error completo: {str(e)}")
            return render(request, self.template_name, {
                'error': 'Error en el sistema. Intente más tarde.',
                'next': next_url
            })

def logout_view(request):
    if 'firebase_user' in request.session:
        del request.session['firebase_user']
    return redirect('login')

def listar_registros(request):
    # Obtener datos de Firebase Realtime Database
    if not FIREBASE_ENABLED:
        return render(request, 'registros_vehiculos.html', {
            'error': 'Firebase no está configurado correctamente',
            'registros': {
                'object_list': [],
                'paginator': {'num_pages': 0, 'count': 0},
                'has_previous': False,
                'has_next': False,
                'previous_page_number': 1,
                'next_page_number': 1,
                'start_index': 0,
                'end_index': 0,
            }
        })

    try:
        # Obtener datos del nodo /paking
        paking_ref = db.reference('paking')
        paking_data = paking_ref.get() or {}

        registros = []
        for espacio_id, espacio_data in paking_data.items():
            if not isinstance(espacio_data, dict):
                continue
                
            # Solo procesar espacios ocupados
            if espacio_data.get('disponible', True) == False and 'placa' in espacio_data:
                hora_entrada = espacio_data.get('hora_ocupacion')
                hora_salida = espacio_data.get('hora_salida')
                
                # Calcular tiempo transcurrido o estacionado
                tiempo_info = ''
                if hora_entrada:
                    try:
                        entrada_dt = datetime.strptime(hora_entrada, '%Y-%m-%d %H:%M:%S')
                        if hora_salida:
                            salida_dt = datetime.strptime(hora_salida, '%Y-%m-%d %H:%M:%S')
                            delta = salida_dt - entrada_dt
                            horas = delta.seconds // 3600
                            minutos = (delta.seconds % 3600) // 60
                            tiempo_info = f'{horas} horas {minutos} minutos'
                        else:
                            delta = datetime.now() - entrada_dt
                            horas = delta.seconds // 3600
                            minutos = (delta.seconds % 3600) // 60
                            tiempo_info = f'{horas} horas {minutos} minutos'
                    except:
                        tiempo_info = 'No disponible'

                registros.append({
                    'id': espacio_id,
                    'placa': espacio_data.get('placa', ''),
                    'tipo_vehiculo': espacio_data.get('tipo_vehiculo', 'No Residente'),
                    'espacio': {'numero': espacio_data.get('numero', '')},
                    'hora_entrada': hora_entrada,
                    'hora_salida': hora_salida,
                    'tarifa': espacio_data.get('tarifa'),
                    'tiempo_transcurrido': tiempo_info if not hora_salida else '',
                    'tiempo_estacionado': tiempo_info if hora_salida else ''
                })

        # Aplicar filtros
        placa = request.GET.get('placa', '')
        estado = request.GET.get('estado', 'todos')
        
        registros_filtrados = registros
        
        if placa:
            registros_filtrados = [r for r in registros_filtrados if placa.lower() in r['placa'].lower()]
        
        if estado == 'activos':
            registros_filtrados = [r for r in registros_filtrados if not r['hora_salida']]
        elif estado == 'finalizados':
            registros_filtrados = [r for r in registros_filtrados if r['hora_salida']]

        # Paginación
        page = int(request.GET.get('page', 1))
        items_per_page = 3
        total_items = len(registros_filtrados)
        total_pages = (total_items + items_per_page - 1) // items_per_page
        
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        registros_paginados = registros_filtrados[start_idx:end_idx]

        # Calcular información de paginación
        has_previous = page > 1
        has_next = page < total_pages
        previous_page = page - 1 if has_previous else 1
        next_page = page + 1 if has_next else total_pages

        # Calcular totales para el resumen
        totales = {
            'registros': len(registros),
            'activos': len([r for r in registros if not r['hora_salida']]),
            'finalizados': len([r for r in registros if r['hora_salida']]),
            'recaudado': sum([r['tarifa'] for r in registros if r['tarifa'] is not None])
        }

        context = {
            'registros': {
                'object_list': registros_paginados,
                'number': page,
                'paginator': {
                    'num_pages': total_pages,
                    'count': total_items
                },
                'has_previous': has_previous,
                'has_next': has_next,
                'previous_page_number': previous_page,
                'next_page_number': next_page,
                'start_index': start_idx + 1,
                'end_index': min(end_idx, total_items),
            },
            'totales': totales,
            'request': request
        }

        return render(request, 'registros_vehiculos.html', context)

    except Exception as e:
        return render(request, 'registros_vehiculos.html', {
            'error': f'Error al obtener datos: {str(e)}',
            'registros': {
                'object_list': [],
                'paginator': {'num_pages': 0, 'count': 0},
                'has_previous': False,
                'has_next': False,
                'previous_page_number': 1,
                'next_page_number': 1,
                'start_index': 0,
                'end_index': 0,
            },
            'totales': {
                'registros': 0,
                'activos': 0,
                'finalizados': 0,
                'recaudado': 0
            }
        })

def detalle_registro(request, registro_id):
    # Datos de ejemplo - normalmente esto vendría de la base de datos
    registros_ejemplo = [
        {
            'id': 1,
            'placa': 'ABC-123',
            'tipo_vehiculo': 'Residente',
            'espacio': {'numero': 'A-12', 'tipo': 'Público'},
            'hora_entrada': datetime.now() - timedelta(hours=2),
            'hora_salida': None,
            'tarifa': None,
            'tiempo_transcurrido': '2 horas 15 minutos',
            'conductor': 'Juan Pérez',
            'telefono': '555-1234',
            'observaciones': 'Vehículo corporativo'
        },
        # ... otros registros de ejemplo
    ]
    
    registro = next((r for r in registros_ejemplo if r['id'] == int(registro_id)), None)
    
    if not registro:
        from django.http import Http404
        raise Http404("Registro no encontrado")
    
    context = {
        'registro': registro
    }
    
    return render(request, 'detalle_registro.html', context)

from datetime import datetime
import json

def formatear_timestamp(timestamp_data):
    """
    Convierte el objeto timestamp de Firebase a formato legible
    """
    if not timestamp_data:
        return "-"
    
    try:
        # Si es un string JSON, parsearlo
        if isinstance(timestamp_data, str):
            timestamp_data = json.loads(timestamp_data)
        
        # Si es un diccionario con la estructura de Firebase timestamp
        if isinstance(timestamp_data, dict):
            # Obtener el timestamp en segundos
            seconds = timestamp_data.get('_seconds', 0)
            if not seconds:
                # Intentar con la estructura alternativa
                seconds = timestamp_data.get('seconds', 0)
            
            if seconds:
                # Convertir a datetime
                dt = datetime.fromtimestamp(seconds)
                return dt.strftime('%d/%m/%Y %H:%M:%S')
        
        return "-"
    except Exception as e:
        print(f"Error formateando timestamp: {e}")
        return "-"

def calcular_tiempo_ocupacion(inicio_timestamp):
    """
    Calcula el tiempo transcurrido desde que se ocupó el espacio
    """
    if not inicio_timestamp:
        return "-"
    
    try:
        # Si es un string JSON, parsearlo
        if isinstance(inicio_timestamp, str):
            inicio_timestamp = json.loads(inicio_timestamp)
        
        if isinstance(inicio_timestamp, dict):
            seconds = inicio_timestamp.get('_seconds', 0) or inicio_timestamp.get('seconds', 0)
            
            if seconds:
                inicio = datetime.fromtimestamp(seconds)
                ahora = datetime.now()
                diferencia = ahora - inicio
                
                # Formatear la diferencia
                horas = diferencia.seconds // 3600
                minutos = (diferencia.seconds % 3600) // 60
                
                if diferencia.days > 0:
                    return f"{diferencia.days} día(s), {horas}h {minutos}m"
                elif horas > 0:
                    return f"{horas}h {minutos}m"
                else:
                    return f"{minutos}m"
        
        return "-"
    except Exception as e:
        print(f"Error calculando tiempo de ocupación: {e}")
        return "-"

def gestion_espacios(request):
    """
    Vista para gestionar espacios de parqueo (4 normales y 4 VIP)
    """
    if not FIREBASE_ENABLED:
        return render(request, 'estacionamientos.html', {
            'error': 'Firebase no está configurado correctamente',
            'espacios': []
        })
    
    try:
        espacios_ref = realtime_db.reference('parking_spaces')
        espacios_data = espacios_ref.get()
        
        if not espacios_data or isinstance(espacios_data, str):
            espacios_data = {}
        
        espacios_lista = []
        for espacio_id, espacio_data in espacios_data.items():
            if not isinstance(espacio_data, dict):
                continue
            
            # Determinar tipo basado en el ID o la sección
            tipo = 'privado' if espacio_data.get('section') == 'vip' else 'publico'
            
            # Obtener número del espacio (último carácter del ID)
            numero = espacio_id.split('_')[-1]
            
            # Formatear los timestamps
            hora_ocupacion_raw = espacio_data.get('occupationStartTime')
            ultima_actualizacion_raw = espacio_data.get('lastUpdated')
            
            # Calcular tiempo de ocupación si está ocupado
            tiempo_ocupacion = "-"
            if not espacio_data.get('occupied', False) == False:  # Si está ocupado
                tiempo_ocupacion = calcular_tiempo_ocupacion(hora_ocupacion_raw)
            
            espacios_lista.append({
                'id': espacio_id,
                'numero': numero,
                'tipo': tipo,
                'disponible': not espacio_data.get('occupied', False),
                'placa': espacio_data.get('licensePlate', ''),  # Incluir placa si está disponible
                'hora_ocupacion': formatear_timestamp(hora_ocupacion_raw),
                'ultima_actualizacion': formatear_timestamp(ultima_actualizacion_raw),
                'ocupado_por': espacio_data.get('occupiedByUserId', ''),
                'tiempo_ocupacion': tiempo_ocupacion,
                'reservado': espacio_data.get('reserved', False)
            })
        
        # Ordenar espacios por tipo y número
        espacios_lista.sort(key=lambda x: (x['tipo'], int(x['numero']) if x['numero'].isdigit() else 0))
        
        # Estadísticas adicionales
        total_espacios = len(espacios_lista)
        espacios_ocupados = len([e for e in espacios_lista if not e['disponible']])
        espacios_disponibles = total_espacios - espacios_ocupados
        
        # Calcular porcentaje de ocupación
        porcentaje_ocupacion = 0
        if total_espacios > 0:
            porcentaje_ocupacion = round((espacios_ocupados / total_espacios) * 100)
        
        context = {
            'espacios': espacios_lista,
            'total_espacios': total_espacios,
            'espacios_ocupados': espacios_ocupados,
            'espacios_disponibles': espacios_disponibles,
            'porcentaje_ocupacion': porcentaje_ocupacion,
            'request': request
        }
        
        return render(request, 'estacionamientos.html', context)
        
    except Exception as e:
        print(f"Error en gestion_espacios: {str(e)}")
        return render(request, 'estacionamientos.html', {
            'error': 'Error al obtener información de espacios',
            'espacios': []
        })

def listar_usuarios(request):
    if not FIREBASE_ENABLED:
        return render(request, 'Usuarios.html', {
            'error': 'Firebase no está configurado correctamente'
        })

    try:
        users_ref = realtime_db.reference('users')
        all_users = users_ref.get()
        
        if not all_users:
            all_users = {}
        elif isinstance(all_users, str):
            all_users = {}

        usuarios_lista = []
        for user_id, user_data in all_users.items():
            if not isinstance(user_data, dict):
                continue
                
            # Mapear los campos según la estructura de Firebase
            usuario = {
                'id': user_data.get('userId', user_id),  # Usar userId como ID principal
                'username': user_data.get('name', ''),  # 'name' es el nombre de usuario
                'nombre_completo': f"{user_data.get('name', '')} {user_data.get('apellido', '')}".strip(),
                'email': user_data.get('email', ''),
                'rol': user_data.get('role', 'cliente'),  # Mapear role a rol
                'activo': user_data.get('active', True),  # Mapear active a activo
                'foto_perfil': user_data.get('profileImage'),  # Agregar foto de perfil si existe
                'telefono': user_data.get('telefono', user_data.get('phone', '')),
                'plan_type': user_data.get('planType', 'none'),
                'user_firebase_id': user_id,  # Guardar el ID de Firebase
                'ultimo_login': datetime.now()  # Valor por defecto
            }
            
            # Procesar fecha de creación si existe
            if 'createdAt' in user_data and user_data['createdAt']:
                try:
                    # Convertir timestamp de Firebase a datetime
                    if isinstance(user_data['createdAt'], (int, float)):
                        usuario['fecha_registro'] = datetime.fromtimestamp(user_data['createdAt'] / 1000)
                    elif isinstance(user_data['createdAt'], str):
                        usuario['fecha_registro'] = datetime.strptime(user_data['createdAt'], '%Y-%m-%d %H:%M:%S')
                    else:
                        usuario['fecha_registro'] = datetime.now()
                except (ValueError, TypeError):
                    usuario['fecha_registro'] = datetime.now()
            else:
                usuario['fecha_registro'] = datetime.now()
            
            # Procesar último login si existe
            if 'lastLogin' in user_data and user_data['lastLogin']:
                try:
                    if isinstance(user_data['lastLogin'], (int, float)):
                        usuario['ultimo_login'] = datetime.fromtimestamp(user_data['lastLogin'] / 1000)
                    elif isinstance(user_data['lastLogin'], str):
                        usuario['ultimo_login'] = datetime.strptime(user_data['lastLogin'], '%Y-%m-%d %H:%M:%S')
                except (ValueError, TypeError):
                    pass
                    
            usuarios_lista.append(usuario)

        # Aplicar filtros
        busqueda = request.GET.get('busqueda', '').lower()
        rol = request.GET.get('rol', 'todos')
        estado = request.GET.get('estado', 'todos')

        usuarios_filtrados = usuarios_lista
        
        if busqueda:
            usuarios_filtrados = [
                u for u in usuarios_filtrados 
                if busqueda in u['nombre_completo'].lower() 
                or busqueda in u['username'].lower()
                or busqueda in u['email'].lower()
            ]
        
        if rol != 'todos':
            usuarios_filtrados = [u for u in usuarios_filtrados if u['rol'].lower() == rol.lower()]
        
        if estado != 'todos':
            usuarios_filtrados = [u for u in usuarios_filtrados if u['activo'] == (estado == 'activos')]

        # Paginación
        page = int(request.GET.get('page', 1))
        items_per_page = 10
        total_items = len(usuarios_filtrados)
        total_pages = max(1, (total_items + items_per_page - 1) // items_per_page)
        
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        usuarios_paginados = usuarios_filtrados[start_idx:end_idx]

        # Obtener roles únicos
        roles_disponibles = sorted(list({u['rol'].capitalize() for u in usuarios_lista if u['rol']}))

        # Calcular estadísticas
        stats = {
            'total': len(usuarios_lista),
            'activos': len([u for u in usuarios_lista if u['activo']]),
            'inactivos': len([u for u in usuarios_lista if not u['activo']]),
            'filtrados': len(usuarios_filtrados)
        }

        context = {
            'usuarios': {
                'object_list': usuarios_paginados,
                'number': page,
                'paginator': {
                    'num_pages': total_pages,
                    'count': total_items
                },
                'has_previous': page > 1,
                'has_next': page < total_pages,
                'previous_page_number': page - 1 if page > 1 else 1,
                'next_page_number': page + 1 if page < total_pages else total_pages,
                'start_index': start_idx + 1,
                'end_index': min(end_idx, total_items),
                'page_range': range(1, total_pages + 1)
            },
            'roles': roles_disponibles,
            'stats': stats,
            'request': request,
            'filtros': {
                'busqueda': busqueda,
                'rol': rol,
                'estado': estado
            },
            'modo_offline': False  # Agregar indicador de modo offline
        }

        return render(request, 'Usuarios.html', context)

    except Exception as e:
        print(f"Error al listar usuarios: {str(e)}")
        return render(request, 'Usuarios.html', {
            'error': 'Error en el sistema. Intente más tarde.',
            'usuarios': {
                'object_list': [],
                'number': 1,
                'paginator': {
                    'num_pages': 1,
                    'count': 0
                },
                'has_previous': False,
                'has_next': False,
                'page_range': range(1, 2)
            },
            'roles': [],
            'stats': {'total': 0, 'activos': 0, 'inactivos': 0, 'filtrados': 0},
            'request': request,
            'modo_offline': True
        })


def detalle_usuario(request, user_id):
    if not FIREBASE_ENABLED:
        return render(request, 'Detalles_Usuarios.html', {
            'error': 'Firebase no está configurado correctamente'
        })

    try:
        # Buscar usuario directamente por su ID de Firebase
        users_ref = realtime_db.reference('users')
        user_data = users_ref.child(user_id).get()
        
        if not user_data or not isinstance(user_data, dict):
            raise Http404("Usuario no encontrado")

        # Procesar fechas
        def parse_date(date_value):
            if date_value:
                try:
                    if isinstance(date_value, (int, float)):
                        return datetime.fromtimestamp(date_value / 1000)
                    elif isinstance(date_value, str):
                        return datetime.strptime(date_value, '%Y-%m-%d %H:%M:%S')
                except (ValueError, TypeError):
                    pass
            return datetime.now()

        # Estructurar datos para el template
        usuario = {
            'id': user_id,
            'user_id': user_data.get('userId', user_id),
            'username': user_data.get('name', user_data.get('userId', user_id)),
            'nombre_completo': f"{user_data.get('name', '')} {user_data.get('apellido', '')}".strip(),
            'nombre': user_data.get('name', ''),
            'apellido': user_data.get('apellido', ''),
            'email': user_data.get('email', ''),
            'rol': user_data.get('role', 'cliente').capitalize(),
            'fecha_registro': parse_date(user_data.get('createdAt')),
            'ultimo_login': parse_date(user_data.get('lastLogin')),
            'activo': user_data.get('active', True),
            'foto_perfil': user_data.get('profileImage'),
            'telefono': user_data.get('telefono', user_data.get('phone', 'No especificado')),
            'direccion': user_data.get('direccion', 'No especificada'),
            'plan_type': user_data.get('planType', 'none'),
            'permisos': user_data.get('permisos', []),
            'notas': user_data.get('notas', 'Sin notas adicionales'),
            'firebase_id': user_id
        }

        context = {
            'usuario': usuario
        }
        
        return render(request, 'Detalles_Usuarios.html', context)

    except Http404:
        raise
    except Exception as e:
        logging.error(f"Error al obtener detalle de usuario {user_id}: {str(e)}")
        return render(request, 'Detalles_Usuarios.html', {
            'error': 'Error al cargar los datos del usuario',
            'usuario': None
        })


# Función adicional para verificar conectividad (para el template)
def check_connectivity(request):
    """Endpoint para verificar conectividad con Firebase"""
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            # Intentar una operación simple en Firebase
            users_ref = realtime_db.reference('users')
            users_ref.get()
            return JsonResponse({'online': True})
        except Exception:
            return JsonResponse({'online': False})
    return JsonResponse({'online': False})


# Función adicional para sincronización manual
def sync_users(request):
    """Endpoint para sincronización manual de usuarios"""
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            # Aquí puedes implementar lógica de sincronización
            # Por ejemplo, limpiar caché, recargar datos, etc.
            users_ref = realtime_db.reference('users')
            users_count = len(users_ref.get() or {})
            
            return JsonResponse({
                'success': True,
                'message': f'Sincronización completada. {users_count} usuarios encontrados.'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error en la sincronización: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Método no permitido'})

class ReporteVehiculosView(View):
    template_name = 'Reportes.html'
    
    def get(self, request):
        # Obtener parámetros de filtrado
        filtros = {
            'tipo_reporte': request.GET.get('tipo_reporte', 'diario'),
            'tipo_vehiculo': request.GET.get('tipo_vehiculo', ''),
            'fecha_inicio': request.GET.get('fecha_inicio', ''),
            'fecha_fin': request.GET.get('fecha_fin', ''),
            'formato': request.GET.get('formato', 'html'),
        }
        
        # Validar y convertir fechas
        try:
            fecha_inicio = datetime.strptime(filtros['fecha_inicio'], '%Y-%m-%d').date() if filtros['fecha_inicio'] else None
            fecha_fin = datetime.strptime(filtros['fecha_fin'], '%Y-%m-%d').date() if filtros['fecha_fin'] else None
        except ValueError:
            fecha_inicio = fecha_fin = None
        
        # Determinar rango de fechas según tipo de reporte
        if filtros['tipo_reporte'] == 'diario':
            fecha_inicio = datetime.now().date()
            fecha_fin = fecha_inicio
        elif filtros['tipo_reporte'] == 'semanal':
            fecha_fin = datetime.now().date()
            fecha_inicio = fecha_fin - timedelta(days=6)
        elif filtros['tipo_reporte'] == 'mensual':
            fecha_fin = datetime.now().date()
            fecha_inicio = fecha_fin.replace(day=1)
        
        # Actualizar filtros con fechas calculadas
        filtros.update({
            'fecha_inicio': fecha_inicio.strftime('%Y-%m-%d') if fecha_inicio else '',
            'fecha_fin': fecha_fin.strftime('%Y-%m-%d') if fecha_fin else '',
        })
        
        
        return render(request, self.template_name)
    
    def generar_pdf(self, registros, filtros, total_recaudado):
        template = get_template('Reportes.html')
        context = {
            'registros': registros,
            'filtros': filtros,
            'total_recaudado': total_recaudado,
            'fecha_generacion': datetime.now().strftime('%d/%m/%Y %H:%M')
        }
        html = template.render(context)
        
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="reporte_vehiculos_{datetime.now().date()}.pdf"'
        
        pisa_status = pisa.CreatePDF(html, dest=response)
        if pisa_status.err:
            return HttpResponse('Error al generar PDF', status=500)
        
        return response
    
    def generar_excel(self, registros, filtros):
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="reporte_vehiculos_{datetime.now().date()}.xlsx"'
        
        wb = Workbook()
        ws = wb.active
        ws.title = "Registros de Vehículos"
        
        # Encabezados
        headers = [
            'ID', 'Placa', 'Tipo Vehículo', 'Espacio',
            'Hora Entrada', 'Hora Salida', 'Tiempo Estacionado', 'Tarifa', 'Estado'
        ]
        ws.append(headers)
        
        # Datos
        for r in registros:
            estado = 'Activo' if not r.hora_salida else 'Finalizado'
            tiempo = r.tiempo_transcurrido if not r.hora_salida else r.tiempo_estacionado
            
            ws.append([
                r.id,
                r.placa,
                r.tipo_vehiculo,
                r.espacio.numero,
                r.hora_entrada.strftime('%d/%m/%Y %H:%M'),
                r.hora_salida.strftime('%d/%m/%Y %H:%M') if r.hora_salida else 'N/A',
                tiempo,
                f"${r.tarifa:.2f}" if r.tarifa else 'N/A',
                estado
            ])
        
        wb.save(response)
        return response
    
    def generar_json(self, registros, filtros):
        data = {
            'meta': {
                'fecha_generacion': datetime.now().isoformat(),
                'tipo_reporte': filtros['tipo_reporte'],
                'filtros_aplicados': filtros,
                'total_registros': registros.count()
            },
            'data': [
                {
                    'id': r.id,
                    'placa': r.placa,
                    'tipo_vehiculo': r.tipo_vehiculo,
                    'espacio': r.espacio.numero,
                    'hora_entrada': r.hora_entrada.isoformat(),
                    'hora_salida': r.hora_salida.isoformat() if r.hora_salida else None,
                    'tarifa': float(r.tarifa) if r.tarifa else None,
                    'estado': 'activo' if not r.hora_salida else 'finalizado'
                }
                for r in registros
            ]
        }
        return JsonResponse(data, safe=False)    

class GestionUsuarioView(View):
    template_name = 'formulario_usuario.html'
    
    def get(self, request, username=None):
        """Muestra el formulario para crear/editar usuario"""
        if not FIREBASE_ENABLED:
            messages.error(request, 'Firebase no está configurado')
            return redirect('listar_usuarios')
        
        context = {'roles': ['admin', 'gerente', 'operador', 'client']}
        
        # Modo edición
        if username:
            try:
                user_data = self._obtener_usuario_por_username(username)
                if not user_data:
                    messages.error(request, 'Usuario no encontrado')
                    return redirect('listar_usuarios')
                
                context['usuario'] = user_data
                context['modo_edicion'] = True
                
            except Exception as e:
                logging.error(f"Error al obtener usuario {username}: {str(e)}")
                messages.error(request, 'Error al cargar usuario')
                return redirect('listar_usuarios')
        
        return render(request, self.template_name, context)
    
    def post(self, request, username=None):
        """Procesa el formulario para crear/editar usuario"""
        if not FIREBASE_ENABLED:
            messages.error(request, 'Firebase no está configurado')
            return redirect('listar_usuarios')
        
        # Obtener datos del formulario
        form_data = {
            'username': request.POST.get('username'),
            'nombre_completo': request.POST.get('nombre_completo'),
            'email': request.POST.get('email'),
            'role': request.POST.get('role'),
            'activo': request.POST.get('activo') == 'on',
            'telefono': request.POST.get('telefono'),
            'direccion': request.POST.get('direccion'),
            'permisos': request.POST.getlist('permisos'),
            'notas': request.POST.get('notas')
        }
        
        # Validación básica
        if not form_data['username']:
            messages.error(request, 'El nombre de usuario es requerido')
            return self._render_con_errores(request, form_data, username)
        
        try:
            users_ref = realtime_db.reference('users')
            
            # En edición, verificar que el usuario exista
            if username:
                user_ref = self._obtener_ref_usuario(username)
                if not user_ref.get():
                    messages.error(request, 'Usuario no encontrado')
                    return redirect('listar_usuarios')
                
                # Actualizar datos
                user_ref.update(form_data)
                messages.success(request, 'Usuario actualizado correctamente')
                return redirect('detalle_usuario', username=form_data['username'])
            
            # En creación, verificar que no exista
            else:
                if self._existe_usuario(form_data['username']):
                    messages.error(request, 'El nombre de usuario ya existe')
                    return self._render_con_errores(request, form_data)
                
                # Crear nuevo usuario
                nuevo_usuario = {
                    **form_data,
                    'fecha_registro': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'ultimo_login': None
                }
                
                # Usamos el username como key en Firebase
                users_ref.child(form_data['username']).set(nuevo_usuario)
                messages.success(request, 'Usuario creado correctamente')
                return redirect('detalle_usuario', username=form_data['username'])
                
        except Exception as e:
            logging.error(f"Error al guardar usuario: {str(e)}")
            messages.error(request, 'Error al guardar el usuario')
            return self._render_con_errores(request, form_data, username)
    
    def _obtener_usuario_por_username(self, username):
        """Obtiene un usuario por su username desde Firebase"""
        users_ref = realtime_db.reference('users')
        all_users = users_ref.get() or {}
        
        for user_id, user_data in all_users.items():
            if isinstance(user_data, dict) and user_data.get('username') == username:
                return {
                    'id': user_id,
                    **user_data
                }
        return None
    
    def _obtener_ref_usuario(self, username):
        """Obtiene la referencia al usuario en Firebase"""
        user_id = None
        users_ref = realtime_db.reference('users')
        all_users = users_ref.get() or {}
        
        for uid, data in all_users.items():
            if isinstance(data, dict) and data.get('username') == username:
                user_id = uid
                break
                
        return users_ref.child(user_id) if user_id else None
    
    def _existe_usuario(self, username):
        """Verifica si un usuario ya existe"""
        users_ref = realtime_db.reference('users')
        all_users = users_ref.get() or {}
        
        return any(
            isinstance(data, dict) and data.get('username') == username
            for data in all_users.values()
        )
    
    def _render_con_errores(self, request, form_data, username=None):
        """Renderiza el formulario con errores"""
        context = {
            'usuario': form_data,
            'roles': ['admin', 'gerente', 'operador', 'client'],
            'modo_edicion': bool(username)
        }
        return render(request, self.template_name, context)

def perfil_admin(request):
    # Verificación manual de autenticación
    if not request.user.is_authenticated:
        messages.error(request, 'Debes iniciar sesión para acceder a esta página')
        return redirect('login')  # Asegúrate que 'login' sea el nombre de tu URL de login
    
    try:
        # Obtener datos de Firebase RTDB
        user_ref = db.reference(f'usuarios/{request.user.username}')
        user_data = user_ref.get() or {}
        
        # Obtener datos de autenticación de Firebase
        firebase_user = auth.get_user(request.user.uid)
        
        # Combinar datos para el template
        profile_data = {
            'username': request.user.username,
            'email': firebase_user.email,
            'nombre': user_data.get('nombre', ''),
            'apellido': user_data.get('apellido', ''),
            'foto_perfil': user_data.get('foto_perfil', ''),
            'ultima_actualizacion': user_data.get('actualizado_en', '')
        }

        if request.method == 'POST':
            # Procesar actualización
            updated_data = {
                'nombre': request.POST.get('nombre', '').strip(),
                'apellido': request.POST.get('apellido', '').strip(),
                'actualizado_en': datetime.datetime.now().isoformat()
            }

            # Actualizar en RTDB
            user_ref.update(updated_data)
            
            # Actualizar en Authentication (email)
            if 'email' in request.POST and request.POST['email'] != firebase_user.email:
                auth.update_user(
                    request.user.uid,
                    email=request.POST['email'].strip(),
                    display_name=f"{updated_data['nombre']} {updated_data['apellido']}"
                )
            
            messages.success(request, 'Perfil actualizado correctamente')
            return redirect('perfil_admin')
            
        return render(request, 'perfil_admin.html', {
            'profile': profile_data,
            'seccion_activa': 'perfil'
        })

    except auth.EmailAlreadyExistsError:
        messages.error(request, 'El correo electrónico ya está en uso por otra cuenta')
        return redirect('perfil_admin')
    except Exception as e:
        messages.error(request, f'Error al actualizar el perfil: {str(e)}')
        return redirect('perfil_admin')
