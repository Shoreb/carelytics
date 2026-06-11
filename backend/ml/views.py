"""
Vistas del módulo ML.

POST /api/ml/entrenar/   → entrena el modelo y devuelve métricas.
POST /api/predicciones/  → predice riesgo para un paciente.
GET  /api/ml/metricas/   → devuelve métricas del último entrenamiento (desde disco).
"""

import os
import json
import joblib

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from ml.trainer import entrenar_modelo, predecir, MODEL_PATH, ALL_FEATURES, NUMERIC_FEATURES, BOOL_FEATURES


class MLEntrenarView(APIView):
    """
    POST /api/ml/entrenar/
    Entrena el modelo RandomForest con los datos en BD y devuelve métricas.
    Requiere que el ETL ya haya cargado datos.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            metricas = entrenar_modelo()
            return Response({
                'estado': 'modelo entrenado exitosamente',
                'metricas': metricas,
            }, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {'error': 'Error durante el entrenamiento', 'detalle': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class MLMetricasView(APIView):
    """
    GET /api/ml/metricas/
    Devuelve las métricas del modelo actualmente entrenado.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        metricas_path = MODEL_PATH.replace('.pkl', '_metricas.json')
        if not os.path.exists(MODEL_PATH):
            return Response(
                {'error': 'El modelo no ha sido entrenado aún.'},
                status=status.HTTP_404_NOT_FOUND
            )
        # Re-ejecutar métricas leyendo el pipeline serializado
        try:
            metricas = entrenar_modelo()
            # Guardar para caché
            with open(metricas_path, 'w') as f:
                json.dump(metricas, f, indent=2)
            return Response(metricas)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PrediccionView(APIView):
    """
    POST /api/predicciones/
    Predice el nivel de riesgo para un paciente dado.

    Body esperado (JSON):
    {
        "edad": 55,
        "imc": 29.5,
        "glucosa": 145.0,
        "colesterol": 220.0,
        "presion_sistolica": 150,
        "presion_diastolica": 95,
        "frecuencia_cardiaca": 88,
        "saturacion_oxigeno": 96.0,
        "temperatura": 37.0,
        "sexo": "M",
        "actividad_fisica": "Baja",
        "fumador": true,
        "consumo_alcohol": false,
        "antecedentes_familiares": true
    }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        datos = request.data

        # Validar que los campos numéricos clave estén presentes
        campos_requeridos = ['edad', 'glucosa', 'presion_sistolica']
        faltantes = [c for c in campos_requeridos if c not in datos]
        if faltantes:
            return Response(
                {'error': f"Campos requeridos faltantes: {faltantes}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            resultado = predecir(datos)
            return Response(resultado, status=status.HTTP_200_OK)
        except FileNotFoundError as e:
            return Response({'error': str(e)}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(
                {'error': 'Error en la predicción', 'detalle': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
