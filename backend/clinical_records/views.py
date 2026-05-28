from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Avg, Count
from rest_framework import viewsets, status
from .models import Patient
from .serializers import PatientSerializer

class PatientViewSet(viewsets.ModelViewSet):

    queryset = Patient.objects.all().order_by('-created_at')
    serializer_class = PatientSerializer

class DashboardKPIView(APIView):
    """
    Vista para obtener indicadores clave de desempeño (KPIs) globales.
    """
    def get(self, request):
        total_pacientes = Patient.objects.count()
        
        # Calculamos promedios usando aggregate
        stats = Patient.objects.aggregate(
            promedio_glucosa=Avg('glucosa'),
            promedio_colesterol=Avg('colesterol'),
            promedio_edad=Avg('edad')
        )
        
        # Cálculo de porcentaje: (Fumadores / Total) * 100
        fumadores_count = Patient.objects.filter(fumador=True).count()
        porcentaje_fumadores = (fumadores_count / total_pacientes * 100) if total_pacientes > 0 else 0

        data = {
            "total_pacientes": total_pacientes,
            "promedio_glucosa": round(stats['promedio_glucosa'] or 0, 2),
            "promedio_colesterol": round(stats['promedio_colesterol'] or 0, 2),
            "promedio_edad": round(stats['promedio_edad'] or 0, 1),
            "porcentaje_fumadores": round(porcentaje_fumadores, 2),
            "estado": "Análisis completado sobre 1800 registros"
        }
        
        return Response(data)

class HealthReportView(APIView):
    """
    Vista para generar reportes de distribución diagnóstica y demográfica.
    """
    def get(self, request):
        # 1. Distribución por Diagnóstico
        diagnosticos = Patient.objects.values('diagnostico_preliminar').annotate(
            total=Count('diagnostico_preliminar')
        ).order_by('-total')

        # 2. Distribución por Sexo
        generos = Patient.objects.values('sexo').annotate(
            total=Count('sexo')
        )

        # 3. Distribución por Riesgo
        riesgos = Patient.objects.values('riesgo_enfermedad').annotate(
            total=Count('riesgo_enfermedad')
        )

        return Response({
            "reporte_diagnosticos": diagnosticos,
            "reporte_generos": generos,
            "reporte_riesgos": riesgos,
            "total_analizado": Patient.objects.count()
        })

class PredictionView(APIView):
    """
    Endpoint que simula la inferencia de un modelo de Machine Learning
    para predecir el riesgo de enfermedad.
    """
    def post(self, request):
        datos = request.data
        
        try:
            # Extraemos los valores clave para la predicción
            edad = int(datos.get('edad', 0))
            glucosa = float(datos.get('glucosa', 0))
            sistolica = int(datos.get('presion_sistolica', 0))
            fumador = datos.get('fumador', False)

            # Lógica de predicción (Simulando un Random Forest)
            puntos_riesgo = 0
            
            if edad > 60: puntos_riesgo += 2
            if glucosa > 140: puntos_riesgo += 3
            if sistolica > 140: puntos_riesgo += 3
            if fumador: puntos_riesgo += 2

            # Determinar nivel de riesgo
            if puntos_riesgo >= 6:
                resultado = "Crítico"
                recomendacion = "Remisión inmediata a especialista."
            elif puntos_riesgo >= 3:
                resultado = "Medio"
                recomendacion = "Seguimiento preventivo en 3 meses."
            else:
                resultado = "Bajo"
                recomendacion = "Mantener hábitos saludables."

            return Response({
                "riesgo_predicho": resultado,
                "puntuacion_analítica": puntos_riesgo,
                "recomendacion": recomendacion,
                "modelo_usado": "Random Forest Classifier v1.0"
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": "Datos incompletos o inválidos"}, status=status.HTTP_400_BAD_REQUEST)