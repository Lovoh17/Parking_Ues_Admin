###################################### IMPORTES NECESARIOS PARA LAS VISTAS ######################################
from django.shortcuts import render, redirect,Http404
from django.views.generic import View
import logging
from django.core.paginator import Paginator
from pathlib import Path
from django.http import JsonResponse
from django.views.generic import TemplateView
from firebase_admin import db as realtime_db
from firebase_admin import db, auth
from datetime import datetime
from datetime import datetime, timedelta
from django.contrib import messages
import hashlib
from django.views import View
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.template.loader import get_template
from datetime import datetime
import xlsxwriter
from io import BytesIO
from xhtml2pdf import pisa
import json
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
from datetime import datetime
import json
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
            reservado = espacio_data.get('reserved', False)
            es_vip = espacio_data.get('section', 'normal') == 'vip'
            
            espacio = {
                'id': espacio_id,
                'numero': espacio_data.get('spaceNumber', espacio_id.split('_')[-1]),
                'disponible': not (ocupado or reservado),
                'ocupado': ocupado,
                'reservado': reservado,
                'tipo': 'vip' if es_vip else 'normal',
                'ultima_actualizacion': espacio_data.get('lastUpdated', ''),
            }
            
            espacios_lista.append(espacio)
            if not (ocupado or reservado):
                espacios_disponibles += 1
            if ocupado:
                vehiculos_actuales += 1
                
            if es_vip:
                espacios_vip += 1

        capacidad_total = len(espacios_lista)
        ocupacion_porcentaje = round((vehiculos_actuales / capacidad_total) * 100) if capacidad_total > 0 else 0

        usuarios_ref = realtime_db.reference('users')
        usuarios_data = usuarios_ref.get() or {}
        total_usuarios = len(usuarios_data)
        usuarios_activos = sum(1 for u in usuarios_data.values() if isinstance(u, dict) and u.get('active', False))

        transacciones_ref = realtime_db.reference('transacciones')
        transacciones_data = transacciones_ref.get() or {}
        
        hoy = datetime.now().date()
        ingresos_hoy = 0
        egresos_hoy = 0
        ingresos_mes = 0
        egresos_mes = 0
        total_transacciones = 0
        transacciones_hoy = 0
        transacciones_lista = []
        
        for trans_id, trans_data in transacciones_data.items():
            if not isinstance(trans_data, dict):
                continue
                
            try:
                monto = float(trans_data.get('monto', trans_data.get('amount', 0)))
                tipo = trans_data.get('tipo', 'Egreso')  # Default a Egreso si no está especificado
                descripcion = trans_data.get('descripcion', trans_data.get('description', 'Sin descripción'))
                rubro = trans_data.get('rubro', trans_data.get('category', 'Otros'))
                fecha_str = trans_data.get('fecha', trans_data.get('timestamp', ''))
                
                if fecha_str:
                    fecha_obj = None
                    formatos_fecha = [
                        '%d/%m/%Y %H:%M',      
                        '%Y-%m-%d %H:%M:%S',   
                        '%Y-%m-%d %H:%M',      
                        '%d/%m/%Y',            
                        '%Y-%m-%d'            
                    ]
                    
                    for formato in formatos_fecha:
                        try:
                            fecha_obj = datetime.strptime(fecha_str, formato).date()
                            break
                        except ValueError:
                            continue
                    
                    if fecha_obj:
                        transaccion = {
                            'id': trans_id,
                            'fecha': fecha_obj.strftime('%d/%m/%Y %H:%M'),
                            'descripcion': descripcion,
                            'rubro': rubro,
                            'tipo': tipo,
                            'monto': monto,
                            'fecha_obj': fecha_obj
                        }
                        transacciones_lista.append(transaccion)
                        
                        total_transacciones += 1
                        
                        if fecha_obj == hoy:
                            if tipo == 'Ingreso':
                                ingresos_hoy += monto
                            else:
                                egresos_hoy += monto
                            transacciones_hoy += 1
                            
                        if fecha_obj.month == hoy.month and fecha_obj.year == hoy.year:
                            if tipo == 'Ingreso':
                                ingresos_mes += monto
                            else:
                                egresos_mes += monto
                            
            except (ValueError, TypeError) as e:
                print(f"Error procesando transacción {trans_id}: {e}")
                continue

        transacciones_lista.sort(key=lambda x: x['fecha_obj'], reverse=True)

        infracciones_ref = realtime_db.reference('infractions')
        infracciones_data = infracciones_ref.get() or {}
        infracciones_hoy = 0
        total_infracciones = len(infracciones_data)
        infracciones_lista = []
        
        for inf_id, inf_data in infracciones_data.items():
            if not isinstance(inf_data, dict):
                continue
            
            infraccion = {
                'id': inf_id,
                'descripcion': inf_data.get('description', 'Sin descripción'),
                'tipo': inf_data.get('infractionType', 'Desconocido'),
                'multa': inf_data.get('fine', 0),
                'estado': inf_data.get('status', 'pending'),
            }
            infracciones_lista.append(infraccion)

        infracciones_lista.sort(key=lambda x: x['id'], reverse=True)

        context = {
            'espacios': espacios_lista[:8],
            'espacios_disponibles': espacios_disponibles,
            'vehiculos_actuales': vehiculos_actuales,
            'capacidad_total': capacidad_total,
            'ocupacion_porcentaje': ocupacion_porcentaje,
            'espacios_vip': espacios_vip,
            
            'total_usuarios': total_usuarios,
            'usuarios_activos': usuarios_activos,
            
            'transacciones': transacciones_lista[:10],  # Mostrar solo las 10 más recientes
            'ingresos_hoy': round(ingresos_hoy, 2),
            'egresos_hoy': round(egresos_hoy, 2),
            'ingresos_mes': round(ingresos_mes, 2),
            'egresos_mes': round(egresos_mes, 2),
            'balance_hoy': round(ingresos_hoy - egresos_hoy, 2),
            'balance_mes': round(ingresos_mes - egresos_mes, 2),
            'total_transacciones': total_transacciones,
            'transacciones_hoy': transacciones_hoy,
            
            'infracciones_hoy': infracciones_hoy,
            'total_infracciones': total_infracciones,
            'infracciones_lista': infracciones_lista[:5],
            
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
            'egresos_hoy': 0,
            'infracciones_hoy': 0,
            'total_infracciones': 0,
            'infracciones_lista': []
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
            users_ref = realtime_db.reference('users')
            all_users = users_ref.get()
            if not all_users:
                admin_user = {
                    'admin': {
                        'username': 'admin',
                        'password': 'admin123', 
                        'email': 'admin@ues.edu.sv',
                        'role': 'admin'
                    }
                }
                users_ref.set(admin_user)
                all_users = admin_user 
            elif isinstance(all_users, str):
                users_ref.set({})
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

################################################## FUNCION PARA MOSTRAR LOS CERRAR SECCION #############################################
def logout_view(request):
    if 'firebase_user' in request.session:
        del request.session['firebase_user']
    return redirect('login')

################################################## FUNCION AUXILIAR PARA FORMATEAR LAS FECHAS #############################################
def formatear_timestamp(timestamp_data):
    """
    Convierte el objeto timestamp de Firebase a formato legible
    """
    if not timestamp_data:
        return "-"
    
    try:
        if isinstance(timestamp_data, str):
            timestamp_data = json.loads(timestamp_data)
        
        if isinstance(timestamp_data, dict):
            seconds = timestamp_data.get('_seconds', 0)
            if not seconds:
                seconds = timestamp_data.get('seconds', 0)
            
            if seconds:
                dt = datetime.fromtimestamp(seconds)
                return dt.strftime('%d/%m/%Y %H:%M:%S')
        
        return "-"
    except Exception as e:
        print(f"Error formateando timestamp: {e}")
        return "-"

################################################## FUNCION AUXILIAR GESTION DE PARQUEOS #############################################
def calcular_tiempo_ocupacion(inicio_timestamp):
    """
    Calcula el tiempo transcurrido desde que se ocupó el espacio
    """
    if not inicio_timestamp:
        return "-"
    
    try:
        if isinstance(inicio_timestamp, str):
            inicio_timestamp = json.loads(inicio_timestamp)
        
        if isinstance(inicio_timestamp, dict):
            seconds = inicio_timestamp.get('_seconds', 0) or inicio_timestamp.get('seconds', 0)
            
            if seconds:
                inicio = datetime.fromtimestamp(seconds)
                ahora = datetime.now()
                diferencia = ahora - inicio
                
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

################################################## FUNCION PARA GESTION DE PARQUEOS #############################################
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

            tipo = 'privado' if espacio_data.get('section') == 'vip' else 'publico'

            numero = espacio_id.split('_')[-1]

            hora_ocupacion_raw = espacio_data.get('occupationStartTime')
            ultima_actualizacion_raw = espacio_data.get('lastUpdated')
            
            tiempo_ocupacion = "-"
            if not espacio_data.get('occupied', False) == False: 
                tiempo_ocupacion = calcular_tiempo_ocupacion(hora_ocupacion_raw)
            
            espacios_lista.append({
                'id': espacio_id,
                'numero': numero,
                'tipo': tipo,
                'disponible': not espacio_data.get('occupied', False),
                'placa': espacio_data.get('licensePlate', ''), 
                'hora_ocupacion': formatear_timestamp(hora_ocupacion_raw),
                'ultima_actualizacion': formatear_timestamp(ultima_actualizacion_raw),
                'ocupado_por': espacio_data.get('occupiedByUserId', ''),
                'tiempo_ocupacion': tiempo_ocupacion,
                'reservado': espacio_data.get('reserved', False)
            })
        
        espacios_lista.sort(key=lambda x: (x['tipo'], int(x['numero']) if x['numero'].isdigit() else 0))
        
        total_espacios = len(espacios_lista)
        espacios_ocupados = len([e for e in espacios_lista if not e['disponible']])
        espacios_disponibles = total_espacios - espacios_ocupados

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

################################################## FUNCION PARA MOSTRAR LOS USUARIOS #############################################
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

            usuario = {
                'id': user_data.get('userId', user_id), 
                'username': user_data.get('name', ''),
                'nombre_completo': f"{user_data.get('name', '')} {user_data.get('apellido', '')}".strip(),
                'email': user_data.get('email', ''),
                'rol': user_data.get('role', 'cliente'),
                'activo': user_data.get('active', True),  
                'foto_perfil': user_data.get('profileImage'),  
                'telefono': user_data.get('telefono', user_data.get('phone', '')),
                'plan_type': user_data.get('planType', 'none'),
                'user_firebase_id': user_id,
                'ultimo_login': datetime.now()
            }
            

            if 'createdAt' in user_data and user_data['createdAt']:
                try:
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
            if 'lastLogin' in user_data and user_data['lastLogin']:
                try:
                    if isinstance(user_data['lastLogin'], (int, float)):
                        usuario['ultimo_login'] = datetime.fromtimestamp(user_data['lastLogin'] / 1000)
                    elif isinstance(user_data['lastLogin'], str):
                        usuario['ultimo_login'] = datetime.strptime(user_data['lastLogin'], '%Y-%m-%d %H:%M:%S')
                except (ValueError, TypeError):
                    pass
                    
            usuarios_lista.append(usuario)

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

        page = int(request.GET.get('page', 1))
        items_per_page = 10
        total_items = len(usuarios_filtrados)
        total_pages = max(1, (total_items + items_per_page - 1) // items_per_page)
        
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        usuarios_paginados = usuarios_filtrados[start_idx:end_idx]

        roles_disponibles = sorted(list({u['rol'].capitalize() for u in usuarios_lista if u['rol']}))

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
            'modo_offline': False 
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

################################################## FUNCION PARA MOSTRAR LOS DETALES DE USUARIOS #############################################
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

########################## Función adicional para verificar conectividad (para el template) ##########################################
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

################################### Función adicional para sincronización manual ######################################################
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

################################################## Funcion para generar reportes ######################################################
class ReportesRTDBView(View):
    template_name = 'Reportes.html'
    
    def get(self, request):
        tipo_reporte = request.GET.get('tipo_reporte', 'users')
        formato = request.GET.get('formato', 'html')
        raw_data = self.get_rtdb_data(tipo_reporte)
        processed_data = self.process_data(raw_data, tipo_reporte)
        
        if formato == 'pdf':
            return self.generar_pdf(processed_data, tipo_reporte)
        elif formato == 'excel':
            return self.generar_excel(processed_data, tipo_reporte)
        elif formato == 'json':
            return JsonResponse(processed_data, safe=False, json_dumps_params={'indent': 2})
        context = {
            'titulo': self.get_titulo_reporte(tipo_reporte),
            'tipo_reporte': tipo_reporte,
            'data': processed_data,
            'headers': self.get_headers(tipo_reporte),
            'total_registros': len(processed_data),
            'fecha_generacion': datetime.now().strftime('%d/%m/%Y %H:%M'),
            'tipos_reporte': self.get_tipos_reporte(),
        }
        return render(request, self.template_name, context)
    
    def get_rtdb_data(self, tipo_reporte):
        """Obtiene datos de Firebase RTDB según el tipo de reporte"""
        from firebase_admin import db
        
        ref = db.reference(tipo_reporte)
        snapshot = ref.get()
        if isinstance(snapshot, dict):
            return [{'id': key, **value} for key, value in snapshot.items()]
        return snapshot or []
    
    def process_data(self, raw_data, tipo_reporte):
        """Procesa y formatea los datos según el tipo de reporte"""
        if not raw_data:
            return []
        
        processed_data = []
        
        for item in raw_data:
            processed_item = {}
            if tipo_reporte == 'users':
                processed_item = self.process_user_data(item)
            elif tipo_reporte == 'user_memberships':
                processed_item = self.process_membership_data(item)
            elif tipo_reporte == 'parking_spaces':
                processed_item = self.process_parking_data(item)
            elif tipo_reporte == 'membership_plans':
                processed_item = self.process_plan_data(item)
            elif tipo_reporte == 'infractions':
                processed_item = self.process_infraction_data(item)
            else:
                processed_item = self.process_generic_data(item)
            
            processed_data.append(processed_item)
        
        return processed_data
    
    def process_user_data(self, item):
        """Procesa datos de usuarios"""
        return {
            'ID': item.get('id', '-'),
            'Nombre': item.get('name', '-'),
            'Email': item.get('email', '-'),
            'Teléfono': item.get('phone', '-'),
            'Estado': 'Activo' if item.get('active', False) else 'Inactivo',
            'Fecha Registro': self.format_date(item.get('created_at')),
            'Último Acceso': self.format_date(item.get('last_login')),
        }
    
    def process_membership_data(self, item):
        """Procesa datos de membresías"""
        plan_id = item.get('planId', '-')
        price = self.get_plan_price(plan_id)
        
        return {
            'ID': item.get('membershipId', item.get('id', '-')),
            'Usuario': item.get('userId', '-'),
            'Plan': item.get('planId', '-'),
            'Estado': self.format_membership_status(item.get('active')),
            'Precio': self.format_currency(price),
            'Método de Pago': item.get('paymentMethod', '-'),
            'Transacción': item.get('transactionId', '-'),
            'Fecha Inicio': self.format_timestamp_date(item.get('startDate')),
            'Fecha Fin': self.format_timestamp_date(item.get('endDate')),
            'Zona Horaria': f"UTC{item.get('timezoneOffset', 0)/60:+.0f}" if item.get('timezoneOffset') else '-',
        }
    
    def process_parking_data(self, item):
        """Procesa datos de espacios de estacionamiento"""
        return {
            'ID': item.get('spaceId', item.get('id', '-')),
            'Número': item.get('spaceNumber', '-'),
            'Zona': item.get('section', '-'),
            'Estado': self.format_parking_status(item.get('occupied')),
            'Reservado': 'Sí' if item.get('reserved', False) else 'No',
            'Tiempo Actual': self.format_duration(item.get('currentOccupationDuration', 0)),  # Tiempo parqueado
            'Ocupado por': item.get('occupied_by', '-'),
            'Última Actualización': self.format_date(item.get('lastUpdated')),  # Usar lastUpdated
        }
    
    def process_plan_data(self, item):
        """Procesa datos de planes de membresía"""
        return {
            'ID': item.get('id', '-'),
            'Nombre': item.get('name', '-'),
            'Descripción': item.get('description', '-'),
            'Precio': self.format_currency(item.get('price')),
            'Duración': f"{item.get('durationDays', 0)} días",
            'Activo': 'Sí' if item.get('active', False) else 'No',
            'Beneficios': self.format_list(item.get('benefits', [])),
        }
    
    def process_infraction_data(self, item):
        """Procesa datos de infracciones"""
        return {
            'ID': item.get('id', '-'),
            'Usuario': item.get('user_name', item.get('user_id', '-')),
            'Tipo': item.get('infactionType', '-'),
            'Descripción': item.get('description', '-'),
            'Multa': self.format_currency(item.get('fine')),
            'Estado': self.format_infraction_status(item.get('status')),
        }
    
    def process_generic_data(self, item):
        """Procesa datos genéricos"""
        processed = {}
        for key, value in item.items():
            formatted_key = key.replace('_', ' ').title()
            if isinstance(value, bool):
                processed[formatted_key] = 'Sí' if value else 'No'
            elif isinstance(value, list):
                processed[formatted_key] = self.format_list(value)
            elif isinstance(value, dict):
                processed[formatted_key] = self.format_dict(value)
            elif key in ['created_at', 'updated_at', 'date', 'start_date', 'end_date']:
                processed[formatted_key] = self.format_date(value)
            elif key in ['price', 'amount', 'cost', 'fine_amount']:
                processed[formatted_key] = self.format_currency(value)
            else:
                processed[formatted_key] = str(value) if value is not None else '-'
        
        return processed
    
    def format_date(self, date_value):
        """Formatea fechas"""
        if not date_value:
            return '-'
        
        try:
            if isinstance(date_value, str):
                for fmt in ['%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S']:
                    try:
                        dt = datetime.strptime(date_value, fmt)
                        return dt.strftime('%d/%m/%Y')
                    except ValueError:
                        continue
            return str(date_value)
        except:
            return str(date_value) if date_value else '-'
    
    def format_currency(self, amount):
        """Formatea moneda"""
        if amount is None:
            return '-'
        try:
            return f"${float(amount):,.2f}"
        except:
            return str(amount)
    
    def format_list(self, list_value):
        """Formatea listas"""
        if not list_value:
            return '-'
        if isinstance(list_value, list):
            return ', '.join(str(item) for item in list_value)
        return str(list_value)
    
    def format_dict(self, dict_value):
        """Formatea diccionarios"""
        if not dict_value:
            return '-'
        if isinstance(dict_value, dict):
            return ', '.join(f"{k}: {v}" for k, v in dict_value.items())
        return str(dict_value)
    
    def format_membership_status(self, status):
        """Formatea estado de membresía"""
        status_map = {
            'active': 'Activa',
            'expired': 'Expirada',
            'suspended': 'Suspendida',
            'cancelled': 'Cancelada',
        }
        return status_map.get(status, status or '-')
    
    def format_membership_status(self, active):
        """Convierte el estado booleano de membresía a texto"""
        if active is None:
            return 'Desconocido'
        return 'Activa' if active else 'Inactiva'

    def format_timestamp_date(self, timestamp_obj):
        """Formatea objeto de timestamp a fecha legible"""
        if not timestamp_obj or not isinstance(timestamp_obj, dict):
            return '-'
        
        try:
            # Extraer componentes del timestamp
            year = timestamp_obj.get('year', 0)
            month = timestamp_obj.get('month', 0)
            day = timestamp_obj.get('day', 0)
            hours = timestamp_obj.get('hours', 0)
            minutes = timestamp_obj.get('minutes', 0)
            
            if year and month and day:
                return f"{day:02d}/{month:02d}/{year} {hours:02d}:{minutes:02d}"
            return '-'
        except:
            return '-'

    def format_payment_method(self, method):
        """Formatea método de pago"""
        methods = {
            'credit_card': 'Tarjeta de Crédito',
            'debit_card': 'Tarjeta de Débito',
            'paypal': 'PayPal',
            'bank_transfer': 'Transferencia',
            'cash': 'Efectivo'
        }
        return methods.get(method, method or '-')
    
    def format_parking_status(self, occupied):
        """Convierte el estado booleano a texto legible"""
        if occupied is None:
            return 'Desconocido'
        return 'Ocupado' if occupied else 'Libre'
    
    def format_infraction_status(self, status):
        """Formatea estado de infracción"""
        status_map = {
            'pending': 'Pendiente',
            'paid': 'Pagada',
            'cancelled': 'Cancelada',
            'overdue': 'Vencida',
        }
        return status_map.get(status, status or '-')
    
    def format_duration(self, duration_minutes):
        """Convierte minutos a formato legible"""
        if not duration_minutes or duration_minutes == 0:
            return '0m'
        
        hours = duration_minutes // 60
        minutes = duration_minutes % 60
        
        if hours > 0:
            return f'{hours}h {minutes}m'
        return f'{minutes}m'
    
    def get_plan_price(self, plan_id):
        """Obtiene el precio según el tipo de plan"""
        prices = {
            'plan_silver': 20,
            'plan_gold': 30,
            'silver': 20, 
            'gold': 30,
        }
        return prices.get(plan_id, 0) 

    def format_currency(self, amount):
        """Formatea cantidad a moneda"""
        if amount is None or amount == 0:
            return '-'
        return f"${amount:.2f}"
    
    def get_titulo_reporte(self, tipo_reporte):
        """Obtiene el título del reporte"""
        titulos = {
            'users': 'Reporte de Usuarios',
            'user_memberships': 'Reporte de Membresías',
            'parking_spaces': 'Reporte de Espacios de Estacionamiento',
            'membership_plans': 'Reporte de Planes de Membresía',
            'infractions': 'Reporte de Infracciones',
        }
        return titulos.get(tipo_reporte, f"Reporte de {tipo_reporte.replace('_', ' ').title()}")
    
    def get_headers(self, tipo_reporte):
        """Obtiene los encabezados para el tipo de reporte"""
        headers_map = {
            'users': ['ID', 'Nombre', 'Email', 'Teléfono', 'Estado'],
            'user_memberships': ['ID', 'Usuario', 'Plan', 'Estado', 'Precio','Método de Pago', 'Transacción', 'Fecha Inicio', 'Fecha Fin', 'Zona Horaria'],
            'parking_spaces': ['ID', 'Número', 'Zona', 'Estado', 'Tipo', 'Ocupado por', 'Última Actualización'],
            'membership_plans': ['ID', 'Nombre', 'Descripción', 'Precio', 'Duración', 'Activo', 'Beneficios'],
            'infractions': ['ID', 'Usuario', 'Tipo', 'Descripción', 'Multa', 'Estado'],
        }
        return headers_map.get(tipo_reporte, [])
    
    def get_tipos_reporte(self):
        """Obtiene la lista de tipos de reporte disponibles"""
        return [
            {'value': 'users', 'label': 'Usuarios', 'icon': 'fas fa-users'},
            {'value': 'user_memberships', 'label': 'Membresías de Usuarios', 'icon': 'fas fa-id-card'},
            {'value': 'parking_spaces', 'label': 'Espacios de Estacionamiento', 'icon': 'fas fa-car'},
            {'value': 'membership_plans', 'label': 'Planes de Membresía', 'icon': 'fas fa-clipboard-list'},
            {'value': 'infractions', 'label': 'Infracciones', 'icon': 'fas fa-exclamation-triangle'},
        ]
        
    
    
    def generar_pdf(self, data, tipo_reporte):
        """Genera un reporte en formato PDF mejorado"""
        from django.template.loader import render_to_string
        from weasyprint import HTML, CSS
        from django.conf import settings
        import os
        from tempfile import NamedTemporaryFile
        
        
        # Contexto para la plantilla
        context = {
            'data': data,
            'titulo': self.get_titulo_reporte(tipo_reporte),
            'headers': self.get_headers(tipo_reporte),
            'total_registros': len(data),
            'fecha_generacion': datetime.now().strftime('%d/%m/%Y %H:%M'),
        }
        
        # Renderizar plantilla HTML
        html_string = render_to_string('Reportes_pdf.html', context)
        
        # Crear respuesta HTTP
        response = HttpResponse(content_type='application/pdf')
        filename = f"reporte_{tipo_reporte}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        # Configuración de WeasyPrint
        html = HTML(string=html_string, base_url=settings.BASE_DIR)
        
        # Estilos CSS adicionales
        css = CSS(string='''
            @page {
                size: A4;
                margin: 1.5cm;
                @top-center {
                    content: "''' + context['titulo'] + '''";
                    font-size: 10pt;
                }
                @bottom-center {
                    content: "Página " counter(page) " de " counter(pages);
                    font-size: 8pt;
                }
            }
        ''')
        
        # Generar PDF
        html.write_pdf(response, stylesheets=[css])
    
        return response
    
    def generar_excel(self, data, tipo_reporte):
        """Genera un reporte en formato Excel"""
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet()
        
        # Formatos
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 16,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#2C5282',
            'font_color': 'white',
            'border': 1
        })
        
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#3182CE',
            'font_color': 'white',
            'border': 1
        })
        
        cell_format = workbook.add_format({
            'border': 1,
            'valign': 'vcenter'
        })
        
        # Título del reporte
        titulo = self.get_titulo_reporte(tipo_reporte)
        worksheet.merge_range('A1:H1', titulo, title_format)
        
        # Información adicional
        info_format = workbook.add_format({'italic': True, 'font_size': 10})
        worksheet.write(1, 0, f"Generado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}", info_format)
        worksheet.write(2, 0, f"Total de registros: {len(data)}", info_format)
        
        if data:
            headers = self.get_headers(tipo_reporte) or list(data[0].keys())
            
            # Escribir encabezados
            for col_num, header in enumerate(headers):
                worksheet.write(4, col_num, header, header_format)
                worksheet.set_column(col_num, col_num, 15)  # Ajustar ancho de columna
            
            # Escribir datos
            for row_num, item in enumerate(data, start=5):
                for col_num, header in enumerate(headers):
                    value = item.get(header, '-')
                    worksheet.write(row_num, col_num, value, cell_format)
        
        workbook.close()
        output.seek(0)
        
        response = HttpResponse(
            output,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        filename = f"reporte_{tipo_reporte}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response

################################################## FUNCION PARA NUEVO USUARIO ##################################################
class GestionUsuarioView(View):
    template_name = 'formulario_usuario.html'
    
    def get(self, request, username=None):
        """Muestra el formulario para crear/editar usuario"""
        if not FIREBASE_ENABLED:
            messages.error(request, 'Firebase no está configurado')
            return redirect('listar_usuarios')
        
        context = {'roles': ['admin', 'gerente', 'operador', 'client']}
        
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
        
        if not form_data['username']:
            messages.error(request, 'El nombre de usuario es requerido')
            return self._render_con_errores(request, form_data, username)
        
        try:
            users_ref = realtime_db.reference('users')
            if username:
                user_ref = self._obtener_ref_usuario(username)
                if not user_ref.get():
                    messages.error(request, 'Usuario no encontrado')
                    return redirect('listar_usuarios')
                
                user_ref.update(form_data)
                messages.success(request, 'Usuario actualizado correctamente')
                return redirect('detalle_usuario', username=form_data['username'])
            
            else:
                if self._existe_usuario(form_data['username']):
                    messages.error(request, 'El nombre de usuario ya existe')
                    return self._render_con_errores(request, form_data)
                
                nuevo_usuario = {
                    **form_data,
                    'fecha_registro': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'ultimo_login': None
                }
                
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

################################################## FUNCION PARA MOSTRAR PERFIL DE ADMIN ##############################################
def perfil_admin(request):
    if not request.user.is_authenticated:
        messages.error(request, 'Debes iniciar sesión para acceder a esta página')
        return redirect('login')
    
    try:
        user_ref = db.reference(f'usuarios/{request.user.username}')
        user_data = user_ref.get() or {}
        firebase_user = auth.get_user(request.user.uid)
        profile_data = {
            'username': request.user.username,
            'email': firebase_user.email,
            'nombre': user_data.get('nombre', ''),
            'apellido': user_data.get('apellido', ''),
            'foto_perfil': user_data.get('foto_perfil', ''),
            'ultima_actualizacion': user_data.get('actualizado_en', '')
        }

        if request.method == 'POST':
            updated_data = {
                'nombre': request.POST.get('nombre', '').strip(),
                'apellido': request.POST.get('apellido', '').strip(),
                'actualizado_en': datetime.datetime.now().isoformat()
            }
            user_ref.update(updated_data)
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

######################################### FUNCION PARA MOSTRAR EL HISTORIAL DE ASIHNACIONES  #########################################
def historial_movimientos(request):
    """
    Vista para mostrar el historial de movimientos de asignaciones de parqueo
    """
    try:
        ref = db.reference('historial_asignaciones')
        historial_data = ref.get()
        
        if not historial_data:
            historial_lista = []
        else:
            historial_lista = []
            for key, value in historial_data.items():
                registro = value.copy()
                registro['id'] = key
                if 'timestamp' in registro and registro['timestamp']:
                    try:
                        fecha_dt = datetime.fromtimestamp(registro['timestamp'])
                        registro['fecha_formateada'] = fecha_dt.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        registro['fecha_formateada'] = registro.get('fecha', 'Sin fecha')
                else:
                    registro['fecha_formateada'] = registro.get('fecha', 'Sin fecha')
                
                historial_lista.append(registro)
            historial_lista.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        
        fecha_inicio = request.GET.get('fecha_inicio')
        fecha_fin = request.GET.get('fecha_fin')
        accion_filtro = request.GET.get('accion')
        espacio_filtro = request.GET.get('espacio')
        buscar = request.GET.get('buscar', '').strip()

        historial_filtrado = historial_lista.copy()
        
        if fecha_inicio:
            try:
                fecha_inicio_dt = datetime.strptime(fecha_inicio, '%Y-%m-%d')
                historial_filtrado = [
                    item for item in historial_filtrado 
                    if 'timestamp' in item and item['timestamp'] and
                    datetime.fromtimestamp(item['timestamp']).date() >= fecha_inicio_dt.date()
                ]
            except:
                pass
        
        if fecha_fin:
            try:
                fecha_fin_dt = datetime.strptime(fecha_fin, '%Y-%m-%d')
                historial_filtrado = [
                    item for item in historial_filtrado 
                    if 'timestamp' in item and item['timestamp'] and
                    datetime.fromtimestamp(item['timestamp']).date() <= fecha_fin_dt.date()
                ]
            except:
                pass
        
        if accion_filtro:
            historial_filtrado = [
                item for item in historial_filtrado 
                if item.get('accion', '') == accion_filtro
            ]
        
        if espacio_filtro:
            historial_filtrado = [
                item for item in historial_filtrado 
                if item.get('espacio_key', '') == espacio_filtro
            ]
        
        if buscar:
            historial_filtrado = [
                item for item in historial_filtrado 
                if buscar.lower() in str(item.get('accion', '')).lower() or
                   buscar.lower() in str(item.get('espacio_key', '')).lower() or
                   buscar.lower() in str(item.get('numero_parqueo', '')).lower() or
                   buscar.lower() in str(item.get('user_id', '')).lower()
            ]
        
        paginator = Paginator(historial_filtrado, 10)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        acciones_unicas = list(set([item.get('accion', '') for item in historial_lista if item.get('accion')]))
        espacios_unicos = list(set([item.get('espacio_key', '') for item in historial_lista if item.get('espacio_key')]))
        
        context = {
            'historial': page_obj,
            'acciones_unicas': acciones_unicas,
            'espacios_unicos': espacios_unicos,
            'filtros': {
                'fecha_inicio': fecha_inicio,
                'fecha_fin': fecha_fin,
                'accion': accion_filtro,
                'espacio': espacio_filtro,
                'buscar': buscar,
            },
            'total_registros': len(historial_filtrado)
        }
        
        return render(request, 'historial_movimientos.html', context)
        
    except Exception as e:
        context = {
            'error': f'Error al cargar el historial: {str(e)}',
            'historial': [],
            'acciones_unicas': [],
            'espacios_unicos': [],
            'filtros': {},
            'total_registros': 0
        }
        return render(request, 'historial_movimientos.html', context)

def exportar_historial(request):
    """
    Vista para exportar el historial a CSV
    """
    try:
        ref = db.reference('historial_asignaciones')
        historial_data = ref.get()
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="historial_movimientos.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['ID', 'Acción', 'Espacio', 'Fecha', 'Número Parqueo', 'Usuario ID', 'Timestamp'])
        
        if historial_data:
            for key, item in historial_data.items():
                fecha_formateada = 'Sin fecha'
                if 'timestamp' in item and item['timestamp']:
                    try:
                        fecha_dt = datetime.fromtimestamp(item['timestamp'])
                        fecha_formateada = fecha_dt.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        fecha_formateada = item.get('fecha', 'Sin fecha')
                
                writer.writerow([
                    key,
                    item.get('accion', ''),
                    item.get('espacio_key', ''),
                    fecha_formateada,
                    item.get('numero_parqueo', ''),
                    item.get('user_id', ''),
                    item.get('timestamp', '')
                ])
        
        return response
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

################################################## FUNCION PARA MOSTRAR LAS TRANSACCIONES #############################################
def listar_transacciones(request):
    """
    Vista para listar todas las transacciones con filtros y paginación
    """
    try:
        filtro_tipo = request.GET.get('tipo', '')
        filtro_rubro = request.GET.get('rubro', '')
        filtro_proveedor = request.GET.get('proveedor', '')
        fecha_inicio = request.GET.get('fecha_inicio', '')
        fecha_fin = request.GET.get('fecha_fin', '')
        busqueda = request.GET.get('busqueda', '')

        ref = db.reference('transacciones')
        transacciones_data = ref.get()
        
        transacciones = []
        proveedores_set = set()
        rubros_set = set()
        tipos_set = set()
        
        if transacciones_data:
            for transaccion_id, data in transacciones_data.items():
                # Agregar ID a los datos
                data['id'] = transaccion_id
                
                if 'fecha' in data:
                    if isinstance(data['fecha'], str):
                        data['fecha_formatted'] = data['fecha']
                    else:
                        data['fecha_formatted'] = str(data['fecha'])
                incluir = True
                
                if filtro_tipo and data.get('tipo', '') != filtro_tipo:
                    incluir = False
                
                if filtro_rubro and data.get('rubro', '') != filtro_rubro:
                    incluir = False
                
                if filtro_proveedor and data.get('proveedor', '') != filtro_proveedor:
                    incluir = False
                
                if (fecha_inicio or fecha_fin) and incluir:
                    try:
                        fecha_str = data.get('fecha', '')
                        if fecha_str:
                            fecha_transaccion = None
                            formatos = ['%d/%m/%Y %H:%M', '%d/%m/%Y', '%Y-%m-%d', '%Y-%m-%d %H:%M:%S']
                            
                            for formato in formatos:
                                try:
                                    fecha_transaccion = datetime.strptime(fecha_str.split(' ')[0] if ' ' in fecha_str else fecha_str, formato.split(' ')[0])
                                    break
                                except:
                                    continue
                            
                            if fecha_transaccion:
                                if fecha_inicio:
                                    fecha_ini = datetime.strptime(fecha_inicio, '%Y-%m-%d')
                                    if fecha_transaccion < fecha_ini:
                                        incluir = False
                                
                                if fecha_fin and incluir:
                                    fecha_final = datetime.strptime(fecha_fin, '%Y-%m-%d')
                                    if fecha_transaccion > fecha_final:
                                        incluir = False
                    except Exception as e:
                        print(f"Error procesando fecha: {e}")
                        pass
                
                if busqueda and incluir:
                    descripcion = data.get('descripcion', '').lower()
                    if busqueda.lower() not in descripcion:
                        incluir = False
                
                if incluir:
                    transacciones.append(data)
                    
                    if 'proveedor' in data and data['proveedor']:
                        proveedores_set.add(data['proveedor'])
                    if 'rubro' in data and data['rubro']:
                        rubros_set.add(data['rubro'])
                    if 'tipo' in data and data['tipo']:
                        tipos_set.add(data['tipo'])
        
        transacciones.sort(key=lambda x: x.get('fecha', ''), reverse=True)
        
        total_transacciones = len(transacciones)
        total_ingresos = sum(float(t.get('monto', 0)) for t in transacciones if t.get('tipo') == 'Ingreso')
        total_egresos = sum(float(t.get('monto', 0)) for t in transacciones if t.get('tipo') == 'Egreso')
        balance = total_ingresos - total_egresos
        
        paginator = Paginator(transacciones, 10)  # 10 transacciones por página
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'transacciones': page_obj,
            'total_transacciones': total_transacciones,
            'total_ingresos': total_ingresos,
            'total_egresos': total_egresos,
            'balance': balance,
            'proveedores': sorted(list(proveedores_set)),
            'rubros': sorted(list(rubros_set)),
            'tipos': sorted(list(tipos_set)),
            'filtro_actual': {
                'tipo': filtro_tipo,
                'rubro': filtro_rubro,
                'proveedor': filtro_proveedor,
                'fecha_inicio': fecha_inicio,
                'fecha_fin': fecha_fin,
                'busqueda': busqueda,
            }
        }
        
        return render(request, 'transacciones_listar.html', context)
        
    except Exception as e:
        print(f"Error al obtener transacciones: {e}")
        context = {
            'transacciones': [],
            'error': 'Error al cargar las transacciones',
            'total_transacciones': 0,
            'total_ingresos': 0,
            'total_egresos': 0,
            'balance': 0,
            'proveedores': [],
            'rubros': [],
            'tipos': [],
            'filtro_actual': {}
        }
        return render(request, 'transacciones_listar.html', context)