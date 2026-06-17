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
            df_limpio, duplicados, invalidos, reporte_columnas = self._transformar(df)
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
        """
        import pandas as pd  # lazy import
        import numpy as np   # lazy import
        import unicodedata
        from etl import exploracion as ex

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
        # 4. LIMPIEZA EXTREMA: Conversión forzada de texto a nulo (La "trampa")
        # -----------------------------------------------------------------------------
        cols_numericas = ['edad', 'peso', 'altura', 'glucosa', 'colesterol', 
                          'presion_sistolica', 'presion_diastolica', 'frecuencia_cardiaca', 
                          'saturacion_oxigeno', 'temperatura']
        
        for col in cols_numericas:
            if col in df.columns:
                # Transforma letras como "Treinta" o "Alta" en np.nan para que puedan ser imputados
                df[col] = pd.to_numeric(df[col], errors='coerce')

        # -----------------------------------------------------------------------------
        # 5. VALORES ATÍPICOS ABSURDOS a Nulo
        # -----------------------------------------------------------------------------
        if 'peso' in df.columns: df.loc[(df['peso'] < 20) | (df['peso'] > 300), 'peso'] = np.nan
        if 'temperatura' in df.columns: df.loc[(df['temperatura'] < 34) | (df['temperatura'] > 43), 'temperatura'] = np.nan
        if 'altura' in df.columns: df.loc[(df['altura'] < 0.5) | (df['altura'] > 2.5), 'altura'] = np.nan

        # -----------------------------------------------------------------------------
        # 6. NORMALIZACIÓN ORTOGRÁFICA
        # -----------------------------------------------------------------------------
        if 'diagnostico_preliminar' in df.columns:
            df['diagnostico_preliminar'] = df['diagnostico_preliminar'].astype(str).str.lower().str.strip()
            df['diagnostico_preliminar'] = df['diagnostico_preliminar'].replace({
                'hipertencion': 'Hipertensión', 'hipertension': 'Hipertensión', 'hipertensión': 'Hipertensión',
                'diabetes': 'Diabetes', 'sano': 'Sano', 'nan': 'Sano', 'none': 'Sano'
            })

        # -----------------------------------------------------------------------------
        # 7. IMPUTACIÓN ESTADÍSTICA Y CASTING A MODELOS (models.py)
        # -----------------------------------------------------------------------------
        # Moda (Categóricos)
        moda_sexo = df['sexo'].mode()[0] if 'sexo' in df.columns and not df['sexo'].mode().empty else 'O'
        df['sexo'] = df.get('sexo', pd.Series([moda_sexo]*len(df))).fillna(moda_sexo).apply(ex.limpiar_sexo)

        moda_act = df['actividad_fisica'].mode()[0] if 'actividad_fisica' in df.columns and not df['actividad_fisica'].mode().empty else 'Baja'
        df['actividad_fisica'] = df.get('actividad_fisica', pd.Series([moda_act]*len(df))).fillna(moda_act).apply(ex.limpiar_actividad)

        # Reglas Clínicas / Categóricos por defecto
        df['diagnostico_preliminar'] = df.get('diagnostico_preliminar', pd.Series(['Sano']*len(df))).fillna('Sano')
        
        # Booleanos
        df['fumador'] = df.get('fumador', pd.Series([False]*len(df))).fillna(False).apply(ex.limpiar_booleano)
        df['consumo_alcohol'] = df.get('consumo_alcohol', pd.Series([False]*len(df))).fillna(False).apply(ex.limpiar_booleano)
        df['antecedentes_familiares'] = df.get('antecedentes_familiares', pd.Series([False]*len(df))).fillna(False).apply(ex.limpiar_booleano)

        # Enteros obligatorios para Django (PositiveSmallIntegerField)
        df['presion_sistolica'] = df.get('presion_sistolica', pd.Series([120]*len(df))).fillna(120).astype(int)
        df['presion_diastolica'] = df.get('presion_diastolica', pd.Series([80]*len(df))).fillna(80).astype(int)
        df['frecuencia_cardiaca'] = df.get('frecuencia_cardiaca', pd.Series([70]*len(df))).fillna(70).astype(int)
        
        mediana_edad = df['edad'].median() if 'edad' in df.columns and not pd.isna(df['edad'].median()) else 30
        df['edad'] = df.get('edad', pd.Series([mediana_edad]*len(df))).fillna(mediana_edad).astype(int)

        # Decimales permitidos en Django (DecimalField)
        df['glucosa'] = df.get('glucosa', pd.Series([90.0]*len(df))).fillna(90.0)
        df['saturacion_oxigeno'] = df.get('saturacion_oxigeno', pd.Series([97.0]*len(df))).fillna(97.0)

        mediana_peso = df['peso'].median() if 'peso' in df.columns and not pd.isna(df['peso'].median()) else 70.0
        df['peso'] = df.get('peso', pd.Series([mediana_peso]*len(df))).fillna(mediana_peso)

        mediana_altura = df['altura'].median() if 'altura' in df.columns and not pd.isna(df['altura'].median()) else 1.70
        df['altura'] = df.get('altura', pd.Series([mediana_altura]*len(df))).fillna(mediana_altura)

        media_col = df['colesterol'].mean() if 'colesterol' in df.columns and not pd.isna(df['colesterol'].mean()) else 180.0
        df['colesterol'] = df.get('colesterol', pd.Series([media_col]*len(df))).fillna(media_col)

        media_temp = df['temperatura'].mean() if 'temperatura' in df.columns and not pd.isna(df['temperatura'].mean()) else 36.6
        df['temperatura'] = df.get('temperatura', pd.Series([media_temp]*len(df))).fillna(media_temp)

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

        return df, duplicados, invalidos, reporte_columnas

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