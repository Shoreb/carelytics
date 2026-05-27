import pandas as pd
import numpy as np

def limpiar_sexo(valor):
    mapeo = {'m': 'M', 'masculino': 'M', 'f': 'F', 'femenino': 'F', 'f': 'F'}
    return mapeo.get(str(valor).strip().lower(), 'O')

def limpiar_diagnostico(valor):
    if pd.isna(valor) or str(valor).strip() == "":
        return "Sano"
    v = str(valor).strip().lower()
    if 'hiperten' in v: return "Hipertensión"
    if 'cardio' in v: return "Cardiopatía"
    if 'obesi' in v: return "Obesidad"
    return "Sano"

def limpiar_actividad(valor):
    v = str(valor).strip().lower()
    mapeo = {'sedentario': 'Baja', 'muy baja': 'Baja', 'media': 'Media', 'muy alta': 'Alta', 'activa': 'Alta'}
    if v in mapeo: return mapeo[v]
    final = v.capitalize()
    return final if final in ['Baja', 'Media', 'Alta'] else 'Baja'

def limpiar_entero(valor, default=0):
    if pd.isna(valor): return default
    try:
        return int(float(valor))
    except (ValueError, TypeError):
        mapeo = {'diez': 10, 'veinte': 20, 'treinta': 30, 'cuarenta': 40}
        return mapeo.get(str(valor).strip().lower(), default)

def limpiar_presion(valor):
    if pd.isna(valor): return 120
    if str(valor).strip().lower() == 'alta': return 140
    try:
        val = int(float(valor))
        return max(40, min(250, val))
    except: return 120

def limpiar_outliers(valor, tipo):
    if pd.isna(valor): return None
    try:
        val = float(valor)
        if tipo == 'peso': return max(2.0, min(250.0, val))
        if tipo == 'temperatura': return max(35.0, min(42.0, val))
        return val
    except: return None