# templatetags/report_filters.py
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def lookup(dictionary, key):
    """
    Permite hacer lookup de valores en diccionarios desde templates
    Uso: {{ item|lookup:header }}
    """
    try:
        if dictionary is None or key is None:
            return '-'
        
        if isinstance(dictionary, dict):
            return dictionary.get(str(key), '-')
        
        # Si es un objeto con atributos
        if hasattr(dictionary, str(key)):
            return getattr(dictionary, str(key), '-')
        
        return str(dictionary) if dictionary else '-'
    except (AttributeError, TypeError, KeyError):
        return '-'

@register.filter
def format_status(value):
    """
    Formatea estados para mostrar con colores apropiados
    """
    if not value or value == '-' or value is None:
        return value
    
    try:
        value_str = str(value)
        value_lower = value_str.lower()
        
        # Estados positivos
        if any(word in value_lower for word in ['activo', 'disponible', 'sí', 'si', 'pagada', 'completado']):
            return mark_safe(f'<span class="badge bg-success">{value_str}</span>')
        
        # Estados negativos
        elif any(word in value_lower for word in ['inactivo', 'no', 'expirada', 'cancelada', 'rechazado']):
            return mark_safe(f'<span class="badge bg-danger">{value_str}</span>')
        
        # Estados de advertencia
        elif any(word in value_lower for word in ['pendiente', 'reservado', 'suspendida', 'en proceso']):
            return mark_safe(f'<span class="badge bg-warning text-dark">{value_str}</span>')
        
        # Estados neutrales
        elif any(word in value_lower for word in ['ocupado', 'mantenimiento', 'vencida']):
            return mark_safe(f'<span class="badge bg-secondary">{value_str}</span>')
        
        return value_str
    except (AttributeError, TypeError):
        return str(value) if value else '-'

@register.filter
def format_status_plain(value):
    """
    Formatea estados para PDF (sin HTML)
    """
    if not value or value == '-' or value is None:
        return value
    
    try:
        return str(value)
    except (AttributeError, TypeError):
        return '-'

@register.filter
def format_currency(value):
    """
    Formatea valores de moneda
    """
    if not value or value == '-' or value is None:
        return value
    
    try:
        # Remover símbolos existentes y convertir a float
        clean_value = str(value).replace('$', '').replace(',', '').strip()
        if not clean_value:
            return '-'
        
        amount = float(clean_value)
        return f'${amount:,.2f}'
    except (ValueError, TypeError, AttributeError):
        return str(value) if value else '-'

@register.filter
def format_date(value):
    """
    Formatea fechas de manera consistente
    """
    if not value or value == '-' or value is None:
        return '-'
    
    from datetime import datetime, date
    
    try:
        # Si ya es un objeto date o datetime
        if isinstance(value, (date, datetime)):
            return value.strftime('%d/%m/%Y')
        
        # Si es string, intentar convertir
        if isinstance(value, str):
            value = value.strip()
            if not value or value == '-':
                return '-'
            
            # Intentar diferentes formatos de fecha
            for fmt in ['%Y-%m-%d', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%d/%m/%Y']:
                try:
                    dt = datetime.strptime(value, fmt)
                    return dt.strftime('%d/%m/%Y')
                except ValueError:
                    continue
        
        return str(value) if value else '-'
    except (AttributeError, TypeError, ValueError):
        return str(value) if value else '-'

@register.filter
def pluralize_es(value, singular_plural):
    """
    Pluralización en español
    Uso: {{ count|pluralize_es:"registro,registros" }}
    """
    try:
        if value is None:
            return singular_plural
        
        count = int(value)
        forms = str(singular_plural).split(',')
        
        if len(forms) != 2:
            return singular_plural
        
        singular, plural = forms[0].strip(), forms[1].strip()
        
        return singular if count == 1 else plural
    except (ValueError, TypeError, AttributeError):
        return str(singular_plural) if singular_plural else ''

@register.filter
def safe_str(value):
    """
    Convierte cualquier valor a string de forma segura
    """
    if value is None:
        return ''
    try:
        return str(value)
    except (TypeError, AttributeError):
        return ''

@register.filter  
def default_if_none(value, default):
    """
    Retorna un valor por defecto si el valor es None o vacío
    """
    if value is None or value == '':
        return default
    return value

@register.filter
def get_item(obj, key):
    """
    Obtiene item de diccionario, lista o atributo de objeto de forma segura
    """
    try:
        if obj is None or key is None:
            return None
        
        if isinstance(obj, dict):
            return obj.get(str(key))
        elif isinstance(obj, (list, tuple)):
            return obj[int(key)]
        elif hasattr(obj, str(key)):
            return getattr(obj, str(key))
        
        return None
    except (KeyError, IndexError, ValueError, TypeError, AttributeError):
        return None

@register.filter
def length_safe(value):
    """
    Obtiene la longitud de forma segura
    """
    try:
        if value is None:
            return 0
        if hasattr(value, '__len__'):
            return len(value)
        return 0
    except (TypeError, AttributeError):
        return 0