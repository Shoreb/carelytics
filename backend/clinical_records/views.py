from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Avg, Count
from rest_framework import viewsets
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