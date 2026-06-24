"""
Módulo de transformación y limpieza de datos clínicos.

Patrón: Pure Functions (sin efectos secundarios, fáciles de testear).
Cada función recibe un valor crudo y devuelve el valor limpio o un default seguro.
"""

import pandas as pd
import numpy as np


# ── Rangos clínicos aceptables ────────────────────────────────────────────────
RANGOS = {
    'peso':              (2.0,   250.0),
    'altura':            (0.5,   2.5),
    'temperatura':       (35.0,  42.0),
    'glucosa':           (20.0,  700.0),
    'colesterol':        (50.0,  600.0),
    'presion_sistolica': (40,    250),
    'presion_diastolica':(20,    150),
    'frecuencia_cardiaca':(20,   220),
    'saturacion_oxigeno':(50.0,  100.0),
    'edad':              (0,     120),
    'imc':               (8.0,   80.0),
}

DEFAULTS = {
    'peso': None,
    'altura': 1.70,
    'temperatura': 36.6,
    'glucosa': 90.0,
    'colesterol': 180.0,
    'presion_sistolica': None,
    'presion_diastolica': None,
    'frecuencia_cardiaca': 70,
    'saturacion_oxigeno': 97.0,
    'edad': 0,
}


def es_nulo(valor):
    """Verifica si un valor es nulo/NaN/vacío de forma segura."""
    if valor is None:
        return True
    try:
        return pd.isna(valor)
    except (TypeError, ValueError):
        return False


def limpiar_sexo(valor):
    """
    Normaliza el campo sexo a los choices del modelo: 'M', 'F', 'O'.
    Maneja errores ortográficos comunes del dataset.
    """
    if es_nulo(valor):
        return 'O'
    mapeo = {
        'm': 'M', 'masculino': 'M', 'male': 'M', 'hombre': 'M', 'h': 'M',
        'f': 'F', 'femenino': 'F', 'female': 'F', 'mujer': 'F',
        'o': 'O', 'otro': 'O', 'other': 'O',
    }
    return mapeo.get(str(valor).strip().lower(), 'O')


def limpiar_diagnostico(valor):
    """
    Normaliza diagnósticos con errores ortográficos hacia términos estándar.
    Maneja variantes como 'hipertencion', 'hipertensíon', 'hipertension'.
    """
    if es_nulo(valor) or str(valor).strip() in ('', 'nan', 'NaN'):
        return 'Sano'

    v = str(valor).strip().lower()
    # Eliminar tildes para comparación robusta
    v_norm = (v.replace('á', 'a').replace('é', 'e').replace('í', 'i')
               .replace('ó', 'o').replace('ú', 'u').replace('ü', 'u'))

    if 'hiperten' in v_norm:
        return 'Hipertensión'
    if 'diabet' in v_norm:
        return 'Diabetes'
    if 'cardio' in v_norm or 'arritmia' in v_norm or 'infarto' in v_norm:
        return 'Cardiopatía'
    if 'obesi' in v_norm:
        return 'Obesidad'
    if 'asma' in v_norm or 'respirat' in v_norm:
        return 'Asma'
    if 'sano' in v_norm or 'normal' in v_norm or 'sin' in v_norm:
        return 'Sano'
    # Capitalizar como fallback preservando el valor si es legible
    return str(valor).strip().capitalize() or 'Sano'


def limpiar_actividad(valor):
    """Normaliza actividad física al vocabulario del modelo: Baja, Media, Alta."""
    if es_nulo(valor):
        return 'Baja'
    v = str(valor).strip().lower()
    mapeo = {
        'sedentario': 'Baja',
        'muy baja': 'Baja',
        'baja': 'Baja',
        'ninguna': 'Baja',
        'media': 'Media',
        'moderada': 'Media',
        'regular': 'Media',
        'alta': 'Alta',
        'muy alta': 'Alta',
        'activa': 'Alta',
        'intensa': 'Alta',
    }
    if v in mapeo:
        return mapeo[v]
    # Intentar capitalizar directamente
    capitalizado = v.capitalize()
    return capitalizado if capitalizado in ('Baja', 'Media', 'Alta') else 'Baja'


def limpiar_entero(valor, default=0, campo=None):
    """
    Convierte valores a entero limpio.
    Maneja casos como edad='Treinta' o presión='Alta'.
    Aplica rangos clínicos si se especifica el campo.
    """
    if es_nulo(valor):
        return default
    # Mapa de palabras numéricas en español
    palabras = {
        'cero': 0, 'uno': 1, 'dos': 2, 'tres': 3, 'cuatro': 4, 'cinco': 5,
        'seis': 6, 'siete': 7, 'ocho': 8, 'nueve': 9, 'diez': 10,
        'veinte': 20, 'treinta': 30, 'cuarenta': 40, 'cincuenta': 50,
        'sesenta': 60, 'setenta': 70, 'ochenta': 80, 'noventa': 90,
    }
    try:
        resultado = int(float(str(valor)))
    except (ValueError, TypeError):
        key = str(valor).strip().lower()
        resultado = palabras.get(key, default)

    if campo and campo in RANGOS:
        mn, mx = RANGOS[campo]
        if not (mn <= resultado <= mx):
            return default
    return resultado


def limpiar_float(valor, campo=None, default=None):
    """
    Convierte valores a float limpio aplicando rangos clínicos.
    Retorna None (no un cero) para valores ausentes/inválidos en campos opcionales.
    """
    if es_nulo(valor):
        return default if default is not None else DEFAULTS.get(campo)
    try:
        resultado = float(str(valor).replace(',', '.'))
    except (ValueError, TypeError):
        return default if default is not None else DEFAULTS.get(campo)

    if campo and campo in RANGOS:
        mn, mx = RANGOS[campo]
        if not (mn <= resultado <= mx):
            return default if default is not None else DEFAULTS.get(campo)
    return resultado


def limpiar_presion(valor, campo='presion_sistolica'):
    """
    Especializado para presión: maneja texto cualitativo → valor numérico clínico.
    Devuelve None si el valor es nulo, para que el ETL decida cómo imputar.
    """
    if es_nulo(valor):
        return None  # No imponer un default aquí; lo maneja el pipeline ETL
    v_str = str(valor).strip().lower()
    import unicodedata
    v_norm = unicodedata.normalize('NFKD', v_str).encode('ascii', 'ignore').decode('utf-8')
    mapeo = {
        'muy baja': 75,   'muy bajo': 75,   'hipotension': 90,
        'baja': 90,       'bajo': 90,
        'normal': 115,    'optima': 115,    'saludable': 115,
        'elevada': 135,   'elevado': 135,   'prehipertension': 135,  'limite': 135,
        'alta': 150,      'alto': 150,      'hipertension': 150,
        'alta presion': 150, 'presion alta': 150, 'tension alta': 150,
        'muy alta': 170,  'muy alto': 170,  'hipertension severa': 170,
        'crisis hipertensiva': 180,
    }
    if v_norm in mapeo:
        return mapeo[v_norm]
    return limpiar_entero(valor, default=None, campo=campo)


def limpiar_booleano(valor):
    """Convierte strings/números variados a booleano."""
    if es_nulo(valor):
        return False
    if isinstance(valor, bool):
        return valor
    v = str(valor).strip().lower()
    return v in ('true', '1', 'si', 'sí', 'yes', 's', 'verdadero')


def calcular_imc(peso, altura):
    """
    Calcula el IMC y retorna (imc_value, clasificacion).
    IMC = peso(kg) / altura(m)²
    """
    try:
        p = float(peso)
        a = float(altura)
        if a <= 0 or p <= 0:
            return None, 'Sin datos'
        imc = round(p / (a ** 2), 2)
        if imc < 18.5:
            clasificacion = 'Bajo peso'
        elif imc < 25:
            clasificacion = 'Normal'
        elif imc < 30:
            clasificacion = 'Sobrepeso'
        else:
            clasificacion = 'Obesidad'
        return imc, clasificacion
    except (TypeError, ValueError, ZeroDivisionError):
        return None, 'Sin datos'


def clasificar_riesgo(row):
    """
    Clasifica el riesgo clínico de un paciente según criterios médicos.
    Retorna: 'Bajo', 'Medio', 'Alto', 'Crítico'

    Criterios basados en guías clínicas estándar:
    - Crítico: presión sistólica >180 O glucosa >300 O saturación <85
    - Alto:    presión sistólica >140 O glucosa >140 O IMC >35 O fumador + edad >60
    - Medio:   presión sistólica >120 O glucosa >100 O IMC >30
    - Bajo:    resto
    """
    try:
        ps = float(row.get('presion_sistolica') or 0)
        glucosa = float(row.get('glucosa') or 0)
        sat = float(row.get('saturacion_oxigeno') or 100)
        imc = float(row.get('imc') or 0)
        edad = int(row.get('edad') or 0)
        fumador = bool(row.get('fumador', False))
        antecedentes = bool(row.get('antecedentes_familiares', False))

        # Criterios críticos (cualquiera es suficiente)
        if ps > 180 or glucosa > 300 or sat < 85:
            return 'Crítico'

        # Criterios altos
        puntos_alto = sum([
            ps > 140,
            glucosa > 140,
            imc > 35,
            fumador and edad > 60,
            antecedentes and (ps > 130 or glucosa > 126),
        ])
        if puntos_alto >= 2:
            return 'Alto'

        # Criterios medios
        puntos_medio = sum([
            ps > 130,
            glucosa > 100,
            imc > 30,
            fumador,
            edad > 65,
        ])
        if puntos_medio >= 2:
            return 'Medio'

        return 'Bajo'

    except (TypeError, ValueError):
        return 'Bajo'


def limpiar_fecha(valor):
    """Parsea fecha con múltiples formatos. Retorna None si no es parseable."""
    if es_nulo(valor):
        return None
    try:
        return pd.to_datetime(valor, dayfirst=True, errors='coerce')
    except Exception:
        return None
