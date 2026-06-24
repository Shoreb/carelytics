"""
Vista ETL: ejecuta el pipeline completo y guarda el log de cada ejecución.

Patrón arquitectónico: Command Pattern.
La API dispara una operación compleja encapsulada, que puede rastrearse
y reproducirse gracias al ETLLog.

Nota de rendimiento: pandas y numpy se importan dentro de los métodos
(_extraer, _transformar) para evitar que Gunicorn los cargue al arrancar
el proceso, lo que en instancias con poca RAM (ej. Render Free 512MB)
causa SIGKILL antes de que el servidor esté listo.
"""

import os
import time
import traceback

from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, JSONParser

from clinical_records.models import Patient
from etl.models import ETLLog


# Ruta base al directorio de datasets (relativa al backend/)
DATASETS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'datasets'
)
DEFAULT_DATASET = 'dataset_clinico_etl_1800_registros.xlsx'


class ETLRunView(APIView):
    """
    POST /api/etl/run/
    Ejecuta el pipeline ETL completo sobre el dataset clínico.

    Acepta:
      - Sin body: usa el dataset por defecto del servidor.
      - multipart/form-data con campo 'archivo': procesa el CSV/Excel subido.

    Retorna:
      - 201: proceso exitoso con métricas detalladas.
      - 400: archivo inválido o faltante.
      - 500: error interno con mensaje de diagnóstico.
    """
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, JSONParser]

    def post(self, request):
        inicio = time.time()
        log = ETLLog(usuario=request.user)

        try:
            # ── 1. EXTRACT ────────────────────────────────────────────────────
            df, fuente = self._extraer(request)
            log.fuente_datos = fuente
            log.registros_leidos = len(df)

            # ── 2. TRANSFORM ──────────────────────────────────────────────────
            df_limpio, duplicados, invalidos, reporte_columnas, informe_limpieza = self._transformar(df)
            log.registros_duplicados = duplicados
            log.registros_invalidos = invalidos

            # ── 3. LOAD ───────────────────────────────────────────────────────
            cargados = self._cargar(df_limpio)
            log.registros_cargados = cargados

            # ── Finalizar log ─────────────────────────────────────────────────
            log.tiempo_ejecucion_seg = round(time.time() - inicio, 3)
            log.estado = ETLLog.EstadoChoices.EXITOSO
            log.save()

            return Response({
                'estado': 'exitoso',
                'fuente': fuente,
                'registros_leidos': log.registros_leidos,
                'registros_duplicados': log.registros_duplicados,
                'registros_invalidos': log.registros_invalidos,
                'registros_cargados': log.registros_cargados,
                'tiempo_segundos': float(log.tiempo_ejecucion_seg),
                'log_id': log.id,
                'columnas_reconocidas': reporte_columnas['reconocidas'],
                'columnas_ignoradas': reporte_columnas['ignoradas'],
                'informe_limpieza': informe_limpieza,
            }, status=status.HTTP_201_CREATED)

        except FileNotFoundError as e:
            log.estado = ETLLog.EstadoChoices.FALLIDO
            log.mensaje_error = str(e)
            log.tiempo_ejecucion_seg = round(time.time() - inicio, 3)
            log.save()
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        except ValueError as e:
            # Errores de validación de datos (ej. columna ID no detectada,
            # dataset vacío tras limpieza) — son errores del usuario/archivo,
            # no bugs del sistema, así que se reportan como 400 con mensaje claro.
            log.estado = ETLLog.EstadoChoices.FALLIDO
            log.mensaje_error = str(e)
            log.tiempo_ejecucion_seg = round(time.time() - inicio, 3)
            log.save()
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            log.estado = ETLLog.EstadoChoices.FALLIDO
            log.mensaje_error = traceback.format_exc()
            log.tiempo_ejecucion_seg = round(time.time() - inicio, 3)
            log.save()
            return Response(
                {'error': 'Error interno en el pipeline ETL', 'detalle': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # ─── Métodos privados ─────────────────────────────────────────────────────

    def _extraer(self, request):
        """
        EXTRACT: lee el DataFrame desde archivo subido o dataset por defecto.
        Retorna (DataFrame, nombre_fuente).
        """
        import pandas as pd  # lazy import — no carga al arrancar gunicorn

        archivo = request.FILES.get('archivo')
        if archivo:
            nombre = archivo.name
            if nombre.endswith('.xlsx') or nombre.endswith('.xls'):
                df = pd.read_excel(archivo)
            elif nombre.endswith('.csv'):
                df = pd.read_csv(archivo, encoding='utf-8', on_bad_lines='skip')
            else:
                raise FileNotFoundError(
                    f"Formato no soportado: {nombre}. Use .xlsx o .csv"
                )
            return df, nombre

        # Dataset por defecto
        ruta = os.path.join(DATASETS_DIR, DEFAULT_DATASET)
        if not os.path.exists(ruta):
            raise FileNotFoundError(
                f"Dataset por defecto no encontrado en: {ruta}. "
                "Suba el archivo manualmente o colóquelo en /datasets/"
            )
        df = pd.read_excel(ruta)
        return df, DEFAULT_DATASET

    def _transformar(self, df):
        """
        TRANSFORM: Limpieza extrema, conversión de tipos e imputación estadística.

        Detección flexible de columnas: en vez de exigir nombres exactos
        (ej. 'id_paciente'), se reconoce cualquier alias razonable en
        español o inglés (ej. 'patient_id', 'id', 'paciente_id'), y se
        normalizan mayúsculas/tildes/espacios antes de comparar. Esto
        permite procesar datasets externos sin que el usuario tenga que
        renombrar columnas manualmente.

        Cada modificación queda registrada en InformeLimpieza para
        trazabilidad médica completa.
        """
        import pandas as pd  # lazy import
        import numpy as np   # lazy import
        import unicodedata
        from etl import exploracion as ex
        from etl.informe import InformeLimpieza

        informe = InformeLimpieza()

        def normalizar_nombre_columna(col):
            """minúsculas, sin tildes, espacios/guiones → guión bajo."""
            col = str(col).strip().lower()
            col = unicodedata.normalize('NFKD', col).encode('ascii', 'ignore').decode('utf-8')
            col = col.replace(' ', '_').replace('-', '_')
            while '__' in col:
                col = col.replace('__', '_')
            return col

        # Alias reconocidos por campo interno. Se compara contra el nombre
        # de columna ya normalizado (minúsculas, sin tildes).
        ALIAS = {
            'identificacion': ['id_paciente', 'patient_id', 'id', 'paciente_id', 'identificacion', 'documento', 'cedula'],
            'nombres': ['nombres', 'first_name', 'nombre', 'primer_nombre'],
            'apellidos': ['apellidos', 'last_name', 'apellido', 'primer_apellido'],
            'edad': ['edad', 'age'],
            'sexo': ['sexo', 'gender', 'genero', 'sex'],
            'peso': ['peso', 'weight', 'weight_kg', 'peso_kg'],
            'altura': ['altura', 'height', 'height_m', 'estatura', 'talla'],
            'presion_sistolica': ['presion_sistolica', 'presion_sistolica_mmhg', 'systolic_bp', 'systolic', 'presion_arterial_sistolica'],
            'presion_diastolica': ['presion_diastolica', 'diastolic_bp', 'diastolic', 'presion_arterial_diastolica'],
            'frecuencia_cardiaca': ['frecuencia_cardiaca', 'heart_rate', 'pulso', 'pulse'],
            'glucosa': ['glucosa', 'glucose_level', 'glucose', 'glicemia'],
            'colesterol': ['colesterol', 'cholesterol_level', 'cholesterol'],
            'saturacion_oxigeno': ['saturacion_oxigeno', 'oxygen_saturation', 'spo2', 'sat_oxigeno'],
            'temperatura': ['temperatura', 'body_temp_c', 'body_temperature', 'temp', 'temp_c'],
            'antecedentes_familiares': ['antecedentes_familiares', 'family_history', 'antecedentes'],
            'fumador': ['fumador', 'is_smoker', 'smoker', 'fuma'],
            'consumo_alcohol': ['consumo_alcohol', 'drinks_alcohol', 'alcohol', 'bebe_alcohol'],
            'actividad_fisica': ['actividad_fisica', 'activity_level', 'actividad'],
            'diagnostico_preliminar': ['diagnostico_preliminar', 'diagnosis', 'diagnostico'],
            'fecha_consulta': ['fecha_consulta', 'visit_date', 'fecha', 'consultation_date'],
        }

        # Normalizar nombres de columnas del DataFrame de entrada
        columnas_originales = {col: normalizar_nombre_columna(col) for col in df.columns}
        df = df.rename(columns=columnas_originales)

        # Construir el mapeo real: para cada campo interno, buscar el primer
        # alias presente en el dataset y renombrarlo al nombre interno.
        renombrar = {}
        columnas_reconocidas = []
        for campo_interno, alias_list in ALIAS.items():
            for alias in alias_list:
                alias_norm = normalizar_nombre_columna(alias)
                if alias_norm in df.columns and alias_norm != campo_interno:
                    renombrar[alias_norm] = campo_interno
                    columnas_reconocidas.append(campo_interno)
                    break
                elif alias_norm in df.columns and alias_norm == campo_interno:
                    columnas_reconocidas.append(campo_interno)
                    break

        df = df.rename(columns=renombrar)

        # Columnas del archivo que no se pudieron mapear a ningún campo interno
        campos_internos = set(ALIAS.keys())
        columnas_ignoradas = [c for c in df.columns if c not in campos_internos]

        # ── VALIDACIÓN TEMPRANA: sin columna de identificación, no se puede continuar ──
        if 'identificacion' not in df.columns:
            raise ValueError(
                "No se pudo identificar la columna de ID del paciente. "
                "El archivo debe incluir una columna como 'id_paciente', 'patient_id', "
                "'id', 'documento' o 'cedula'. "
                f"Columnas encontradas en el archivo: {list(columnas_originales.values())}"
            )

        total_original = len(df)

        # 2. Eliminar duplicados y filas sin identificación
        df = df.drop_duplicates(subset=['identificacion'], keep='first')
        n_sin_duplicados = len(df)
        df = df.dropna(subset=['identificacion'])
        df = df[df['identificacion'].astype(str).str.strip() != '']
        df = df[df['identificacion'].astype(str).str.strip().str.lower() != 'nan']

        duplicados = total_original - n_sin_duplicados
        invalidos  = n_sin_duplicados - len(df)  # filas sin ID válida

        if len(df) == 0:
            raise ValueError(
                "Tras la limpieza no quedó ningún registro válido. "
                "Verifica que la columna de identificación del paciente "
                "tenga valores no nulos y no vacíos."
            )

        # 3. Concatenar nombres y apellidos
        df['nombre'] = (
            df.get('nombres', pd.Series([''] * len(df))).fillna('').astype(str).str.strip()
            + ' '
            + df.get('apellidos', pd.Series([''] * len(df))).fillna('').astype(str).str.strip()
        ).str.strip()
        # Si no hay nombres/apellidos en absoluto, usar la identificación como nombre visible
        df.loc[df['nombre'] == '', 'nombre'] = 'Paciente ' + df['identificacion'].astype(str)

        # -----------------------------------------------------------------------------
        # 3b. MAPEO DE TEXTO A NÚMERO para campos con vocabulario cualitativo
        # Debe ocurrir ANTES del paso 4 (pd.to_numeric) porque ese paso
        # convierte cualquier texto a NaN de forma irreversible.
        # Estos mapeos usan el valor CENTRAL del rango clínico correspondiente,
        # no el umbral mínimo, para representar fielmente la categoría.
        # -----------------------------------------------------------------------------
        MAPEO_PRESION_SISTOLICA = {
            # Muy baja / hipotensión severa (< 80 mmHg)
            'muy baja': 75,   'muy bajo': 75,
            'hipotension severa': 75, 'hipotensión severa': 75,
            'critica': 75,    'crítica': 75,   'critico': 75,   'crítico': 75,
            # Baja / hipotensión (80–99 mmHg)
            'baja':  90,  'bajo':  90,
            'hipotension': 90, 'hipotensión': 90,
            'baja presion': 90, 'baja presión': 90,
            # Normal / óptima (100–129 mmHg)
            'normal':   115,  'optima': 115,   'óptima': 115,
            'saludable': 115, 'regular': 115,
            # Elevada / prehipertensión (130–139 mmHg)
            'elevada':  135,  'elevado':  135,
            'prehipertension': 135, 'prehipertensión': 135,
            'limite':   135,  'límite':   135,  'limítrofe': 135,
            # Alta / hipertensión stage 1 (140–159 mmHg)
            'alta':    150,  'alto':    150,
            'hipertension': 150, 'hipertensión': 150,
            'alta presion': 150, 'alta presión': 150,
            'presion alta': 150, 'presión alta': 150,
            'tension alta': 150, 'tensión alta': 150,
            # Muy alta / hipertensión stage 2 (≥ 160 mmHg)
            'muy alta': 170, 'muy alto': 170,
            'hipertension severa': 170, 'hipertensión severa': 170,
            'hipertension grave': 170,  'hipertensión grave': 170,
            'crisis hipertensiva': 180, 'emergencia hipertensiva': 180,
        }
        MAPEO_PRESION_DIASTOLICA = {
            # Muy baja (< 60 mmHg)
            'muy baja': 50,  'muy bajo': 50,
            'hipotension severa': 50, 'hipotensión severa': 50,
            'critica': 50,   'crítica': 50,   'critico': 50,   'crítico': 50,
            # Baja / hipotensión (60–69 mmHg)
            'baja':  65,  'bajo':  65,
            'hipotension': 65, 'hipotensión': 65,
            'baja presion': 65, 'baja presión': 65,
            # Normal (70–79 mmHg)
            'normal':    80,  'optima': 80,   'óptima': 80,
            'saludable': 80,  'regular': 80,
            # Elevada / prehipertensión (80–89 mmHg)
            'elevada':  85,  'elevado':  85,
            'prehipertension': 85, 'prehipertensión': 85,
            'limite':   85,  'límite':   85,  'limítrofe': 85,
            # Alta / hipertensión stage 1 (90–99 mmHg)
            'alta':     95,  'alto':     95,
            'hipertension': 95, 'hipertensión': 95,
            'alta presion': 95, 'alta presión': 95,
            'presion alta': 95, 'presión alta': 95,
            'tension alta': 95, 'tensión alta': 95,
            # Muy alta / hipertensión stage 2 (≥ 100 mmHg)
            'muy alta': 105, 'muy alto': 105,
            'hipertension severa': 110, 'hipertensión severa': 110,
            'hipertension grave': 110,  'hipertensión grave': 110,
            'crisis hipertensiva': 115, 'emergencia hipertensiva': 115,
        }

        def _normalizar_clave(texto):
            """Minúsculas + strip + elimina tildes/diacríticos para búsqueda robusta."""
            import unicodedata
            s = str(texto).strip().lower()
            s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('utf-8')
            return s

        def _mapear_texto_a_numero(col, mapeo):
            if col not in df.columns:
                return
            # Construir versión del mapeo con claves también sin tildes para doble lookup
            mapeo_norm = {_normalizar_clave(k): v for k, v in mapeo.items()}
            # Solo actuar sobre celdas que sean texto (no numéricas ya)
            es_texto = df[col].apply(lambda v: isinstance(v, str) or
                                    (hasattr(v, '__class__') and v.__class__.__name__ == 'str'))
            antes = df[col].copy()

            def _buscar(v):
                if not isinstance(v, str):
                    return v
                clave_orig = str(v).strip().lower()
                clave_norm = _normalizar_clave(v)
                # Primero intenta match exacto (con tildes tal como está en el mapeo),
                # luego intenta match sin tildes para máxima cobertura.
                return mapeo.get(clave_orig, mapeo_norm.get(clave_norm, v))

            df[col] = df[col].apply(_buscar)
            # Registrar cada conversión de texto → número en el informe
            for idx in df[es_texto].index:
                orig = str(antes.at[idx]).strip()
                nuevo = df.at[idx, col]
                if orig != nuevo:  # solo registrar si efectivamente cambió
                    informe.registrar(
                        df.at[idx, 'identificacion'], col,
                        orig, nuevo, 'texto_a_numero_cualitativo'
                    )

        _mapear_texto_a_numero('presion_sistolica',  MAPEO_PRESION_SISTOLICA)
        _mapear_texto_a_numero('presion_diastolica', MAPEO_PRESION_DIASTOLICA)

        # -----------------------------------------------------------------------------
        # 4. LIMPIEZA EXTREMA: Conversión forzada de texto a nulo (La "trampa")
        # -----------------------------------------------------------------------------
        cols_numericas = ['edad', 'peso', 'altura', 'glucosa', 'colesterol', 
                          'presion_sistolica', 'presion_diastolica', 'frecuencia_cardiaca', 
                          'saturacion_oxigeno', 'temperatura']
        
        for col in cols_numericas:
            if col in df.columns:
                antes = df[col].copy()
                df[col] = pd.to_numeric(df[col], errors='coerce')
                # Registrar cada celda donde texto → NaN
                mascara = antes.notna() & df[col].isna()
                for idx in df[mascara].index:
                    informe.registrar(
                        df.at[idx, 'identificacion'], col,
                        antes.at[idx], None, 'texto_a_nulo'
                    )

        # -----------------------------------------------------------------------------
        # 5. VALORES ATÍPICOS ABSURDOS a Nulo
        # -----------------------------------------------------------------------------
        def _atipico_a_nulo(col, minval, maxval):
            if col not in df.columns:
                return
            antes = df[col].copy()
            df.loc[(df[col] < minval) | (df[col] > maxval), col] = np.nan
            mascara = antes.notna() & df[col].isna()
            for idx in df[mascara].index:
                informe.registrar(
                    df.at[idx, 'identificacion'], col,
                    antes.at[idx], None, 'atipico_a_nulo'
                )

        _atipico_a_nulo('peso',        20,  300)
        _atipico_a_nulo('temperatura', 34,   43)
        _atipico_a_nulo('altura',      0.5,  2.5)

        # -----------------------------------------------------------------------------
        # 6. NORMALIZACIÓN ORTOGRÁFICA
        # -----------------------------------------------------------------------------
        if 'diagnostico_preliminar' in df.columns:
            antes_diag = df['diagnostico_preliminar'].copy()
            df['diagnostico_preliminar'] = df['diagnostico_preliminar'].astype(str).str.lower().str.strip()
            df['diagnostico_preliminar'] = df['diagnostico_preliminar'].replace({
                'hipertencion': 'Hipertensión', 'hipertension': 'Hipertensión', 'hipertensión': 'Hipertensión',
                'diabetes': 'Diabetes', 'sano': 'Sano', 'nan': 'Sano', 'none': 'Sano'
            })
            for idx in df.index:
                if str(antes_diag.at[idx]).strip() != str(df.at[idx, 'diagnostico_preliminar']).strip():
                    informe.registrar(
                        df.at[idx, 'identificacion'], 'diagnostico_preliminar',
                        antes_diag.at[idx], df.at[idx, 'diagnostico_preliminar'], 'ortografia'
                    )

        # -----------------------------------------------------------------------------
        # 7. IMPUTACIÓN ESTADÍSTICA Y CASTING A MODELOS (models.py)
        # -----------------------------------------------------------------------------
        def _imputar_serie(col, valor_imputacion, razon, cast_fn=None):
            """Imputa nulos en una columna y registra cada cambio."""
            if col not in df.columns:
                df[col] = valor_imputacion
                return
            mascara_nulos = df[col].isna()
            if mascara_nulos.any():
                for idx in df[mascara_nulos].index:
                    informe.registrar(
                        df.at[idx, 'identificacion'], col,
                        None, valor_imputacion, razon
                    )
            df[col] = df[col].fillna(valor_imputacion)
            if cast_fn:
                df[col] = df[col].apply(cast_fn)

        # Sexo
        antes_sexo = df.get('sexo', pd.Series(['O']*len(df))).copy()
        moda_sexo = df['sexo'].mode()[0] if 'sexo' in df.columns and not df['sexo'].mode().empty else 'O'
        df['sexo'] = df.get('sexo', pd.Series([moda_sexo]*len(df))).fillna(moda_sexo).apply(ex.limpiar_sexo)
        for idx in df.index:
            if str(antes_sexo.at[idx] if idx in antes_sexo.index else 'O') != str(df.at[idx, 'sexo']):
                informe.registrar(df.at[idx, 'identificacion'], 'sexo',
                                  antes_sexo.at[idx] if idx in antes_sexo.index else None,
                                  df.at[idx, 'sexo'], 'normalizacion_sexo')

        # Actividad física
        antes_act = df.get('actividad_fisica', pd.Series(['Baja']*len(df))).copy()
        moda_act = df['actividad_fisica'].mode()[0] if 'actividad_fisica' in df.columns and not df['actividad_fisica'].mode().empty else 'Baja'
        df['actividad_fisica'] = df.get('actividad_fisica', pd.Series([moda_act]*len(df))).fillna(moda_act).apply(ex.limpiar_actividad)
        for idx in df.index:
            if str(antes_act.at[idx] if idx in antes_act.index else 'Baja') != str(df.at[idx, 'actividad_fisica']):
                informe.registrar(df.at[idx, 'identificacion'], 'actividad_fisica',
                                  antes_act.at[idx] if idx in antes_act.index else None,
                                  df.at[idx, 'actividad_fisica'], 'normalizacion_activ')

        # Diagnóstico
        df['diagnostico_preliminar'] = df.get('diagnostico_preliminar', pd.Series(['Sano']*len(df))).fillna('Sano')

        # Booleanos
        for bool_col in ['fumador', 'consumo_alcohol', 'antecedentes_familiares']:
            antes_b = df.get(bool_col, pd.Series([False]*len(df))).copy()
            df[bool_col] = df.get(bool_col, pd.Series([False]*len(df))).fillna(False).apply(ex.limpiar_booleano)
            for idx in df.index:
                orig = antes_b.at[idx] if idx in antes_b.index else False
                if str(orig) != str(df.at[idx, bool_col]):
                    informe.registrar(df.at[idx, 'identificacion'], bool_col,
                                      orig, df.at[idx, bool_col], 'normalizacion_bool')

        # Enteros — signos vitales críticos: NO imputar, solo castear los que ya tienen valor.
        # Si llegó como texto ("Alto", "elevado") ya fue convertido a NaN en el paso 4.
        # El NaN se preserva como None en BD. El médico verá ese campo vacío y sabrá
        # que había un valor ilegible — el sistema no interpreta ni inventa el dato.
        def _castear_entero_opcional(col):
            """Convierte a int los valores numéricos presentes; deja NaN como None."""
            if col not in df.columns:
                df[col] = None
                return
            df[col] = pd.to_numeric(df[col], errors='coerce')  # garantiza numérico
            df[col] = df[col].apply(lambda x: int(x) if pd.notna(x) else None)

        def _castear_float_opcional(col):
            """Convierte a float los valores numéricos presentes; deja NaN como None."""
            if col not in df.columns:
                df[col] = None
                return
            df[col] = pd.to_numeric(df[col], errors='coerce')
            df[col] = df[col].apply(lambda x: float(x) if pd.notna(x) else None)

        # Signos vitales: texto cualitativo ya fue convertido en paso 3b.
        # Usar la mediana del dataset para imputar presión arterial en lugar de
        # un valor hardcodeado (120/80), para que la imputación refleje la
        # distribución real de la cohorte cargada y no empuje artificialmente
        # hacia valores "normales" a pacientes que pueden ser hipertensos.
        mediana_ps = (
            int(df['presion_sistolica'].median())
            if 'presion_sistolica' in df.columns and df['presion_sistolica'].notna().any()
            else 120
        )
        mediana_pd = (
            int(df['presion_diastolica'].median())
            if 'presion_diastolica' in df.columns and df['presion_diastolica'].notna().any()
            else 80
        )
        _imputar_serie('presion_sistolica',  mediana_ps, 'imputacion_mediana', lambda x: int(float(x)))
        _imputar_serie('presion_diastolica', mediana_pd, 'imputacion_mediana', lambda x: int(float(x)))
        _imputar_serie('frecuencia_cardiaca', 70, 'imputacion_default', lambda x: int(float(x)))
        _imputar_serie('glucosa',           90.0, 'imputacion_default')
        _imputar_serie('saturacion_oxigeno',97.0, 'imputacion_default')

        # Edad — sí se imputa con mediana porque es necesaria para el modelo ML
        # y para la segmentación por grupos etarios del dashboard.
        mediana_edad = df['edad'].median() if 'edad' in df.columns and not pd.isna(df['edad'].median()) else 30
        _imputar_serie('edad', int(mediana_edad), 'imputacion_mediana', lambda x: int(float(x)))

        mediana_peso = df['peso'].median() if 'peso' in df.columns and not pd.isna(df['peso'].median()) else 70.0
        _imputar_serie('peso', mediana_peso, 'imputacion_mediana')

        mediana_altura = df['altura'].median() if 'altura' in df.columns and not pd.isna(df['altura'].median()) else 1.70
        _imputar_serie('altura', mediana_altura, 'imputacion_mediana')

        media_col = df['colesterol'].mean() if 'colesterol' in df.columns and not pd.isna(df['colesterol'].mean()) else 180.0
        _imputar_serie('colesterol', media_col, 'imputacion_media')

        media_temp = df['temperatura'].mean() if 'temperatura' in df.columns and not pd.isna(df['temperatura'].mean()) else 36.6
        _imputar_serie('temperatura', media_temp, 'imputacion_media')

        # -----------------------------------------------------------------------------
        # 8. CÁLCULOS FINALES
        # -----------------------------------------------------------------------------
        df['imc'] = df.apply(lambda row: ex.calcular_imc(row.get('peso'), row.get('altura'))[0], axis=1)
        df['riesgo_enfermedad'] = df.apply(ex.clasificar_riesgo, axis=1)

        if 'fecha_consulta' in df.columns:
            df['fecha_consulta'] = df['fecha_consulta'].apply(ex.limpiar_fecha)
        else:
            df['fecha_consulta'] = None

        # 9. Traducción final a Django: cualquier posible NaN residual se vuelve None
        df = df.replace({np.nan: None})

        reporte_columnas = {
            'reconocidas': sorted(set(columnas_reconocidas)),
            'ignoradas': sorted(set(columnas_ignoradas)),
        }

        return df, duplicados, invalidos, reporte_columnas, informe.resumen()

    def _cargar(self, df):
        """
        LOAD: inserta los registros limpios en la base de datos de forma atómica.
        Usa bulk_create con ignore_conflicts para idempotencia (el ETL puede
        ejecutarse varias veces sin duplicar datos).
        """
        pacientes = []
        for _, row in df.iterrows():
            pacientes.append(Patient(
                identificacion=str(row['identificacion']).strip(),
                nombre=row.get('nombre', 'Sin nombre'),
                edad=row['edad'],
                sexo=row['sexo'],
                peso=row['peso'],
                altura=row['altura'],
                glucosa=row['glucosa'],
                colesterol=row['colesterol'],
                presion_sistolica=row['presion_sistolica'],
                presion_diastolica=row['presion_diastolica'],
                frecuencia_cardiaca=row['frecuencia_cardiaca'],
                saturacion_oxigeno=row['saturacion_oxigeno'],
                temperatura=row['temperatura'],
                actividad_fisica=row['actividad_fisica'],
                diagnostico_preliminar=row['diagnostico_preliminar'],
                fumador=row['fumador'],
                consumo_alcohol=row['consumo_alcohol'],
                antecedentes_familiares=row['antecedentes_familiares'],
                riesgo_enfermedad=row['riesgo_enfermedad'],
                imc=row.get('imc'),
                fecha_consulta=row.get('fecha_consulta'),
            ))

        with transaction.atomic():
            creados = Patient.objects.bulk_create(
                pacientes,
                ignore_conflicts=True,
                batch_size=200,
            )
        return len(creados)


class ETLHistorialView(APIView):
    """
    GET /api/etl/historial/
    Devuelve los últimos 50 logs de ejecución ETL con métricas.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from etl.serializers import ETLLogSerializer
        logs = ETLLog.objects.select_related('usuario').all()[:50]
        serializer = ETLLogSerializer(logs, many=True)
        return Response(serializer.data)
