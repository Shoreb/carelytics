"""
Vistas de clinical_records.
"""

import io
import csv
import pandas as pd
from datetime import date

from django.db.models import Avg, Count, Q, StdDev
from django.http import HttpResponse

from rest_framework.views import APIView
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework import viewsets, status, filters, serializers
from rest_framework.permissions import IsAuthenticated

from .models import Patient
from .serializers import PatientSerializer


# ── Pacientes ─────────────────────────────────────────────────────────────────

class PatientViewSet(viewsets.ModelViewSet):
    queryset = Patient.objects.all().order_by('-created_at')
    serializer_class = PatientSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nombre', 'identificacion', 'diagnostico_preliminar']
    ordering_fields = ['edad', 'created_at', 'riesgo_enfermedad']

    def get_queryset(self):
        qs = super().get_queryset()
        riesgo = self.request.query_params.get('riesgo')
        if riesgo: qs = qs.filter(riesgo_enfermedad=riesgo)
        return qs


# ── Dashboard KPIs ────────────────────────────────────────────────────────────

class DashboardKPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Patient.objects.all()
        total = qs.count()
        if total == 0: return Response({'total_pacientes': 0})
        
        stats = qs.aggregate(imc_promedio=Avg('imc'), glucosa_promedio=Avg('glucosa'), ps_promedio=Avg('presion_sistolica'))
        por_riesgo = dict(qs.values('riesgo_enfermedad').annotate(n=Count('id')).values_list('riesgo_enfermedad', 'n'))
        
        return Response({
            'total_pacientes': total,
            'por_riesgo': por_riesgo,
            'estadisticas': {'imc': round(stats['imc_promedio'] or 0, 2), 'glucosa': round(stats['glucosa_promedio'] or 0, 2)}
        })


# ── Reportes (PDF / Excel / CSV) ──────────────────────────────────────────────

class HealthReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        formato = request.query_params.get('formato', 'json').lower()
        if formato == 'csv': return self._exportar_csv()
        if formato == 'excel': return self._exportar_excel()
        return Response({"mensaje": "Reporte listo"})

    def _exportar_csv(self):
        qs = Patient.objects.all().values('identificacion', 'nombre', 'riesgo_enfermedad')
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="reporte.csv"'
        writer = csv.DictWriter(response, fieldnames=['identificacion', 'nombre', 'riesgo_enfermedad'])
        writer.writeheader()
        writer.writerows(qs)
        return response

    def _exportar_excel(self):
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(['ID', 'Nombre', 'Riesgo'])
        for p in Patient.objects.all():
            ws.append([p.identificacion, p.nombre, p.riesgo_enfermedad])
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        response = HttpResponse(buffer.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="reporte.xlsx"'
        return response


# ── Predicción ML ─────────────────────────────────────────────────────────────

class PrediccionSerializer(serializers.Serializer):
    edad = serializers.IntegerField(default=55)
    glucosa = serializers.FloatField(default=145.0)
    presion_sistolica = serializers.IntegerField(default=150)
    presion_diastolica = serializers.IntegerField(default=95)
    imc = serializers.FloatField(default=29.0)
    colesterol = serializers.FloatField(default=220.0)
    frecuencia_cardiaca = serializers.IntegerField(default=88)
    saturacion_oxigeno = serializers.FloatField(default=96.0)
    temperatura = serializers.FloatField(default=37.0)
    fumador = serializers.BooleanField(default=True)
    consumo_alcohol = serializers.BooleanField(default=False)
    antecedentes_familiares = serializers.BooleanField(default=True)
    sexo = serializers.ChoiceField(choices=['M', 'F', 'O'], default='M')
    actividad_fisica = serializers.ChoiceField(choices=['Baja', 'Media', 'Alta'], default='Baja')

class PredictionView(GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PrediccionSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            d = serializer.validated_data
            
            # Convertimos todo explícitamente a tipos de Python (int, float, bool)
            # para evitar que Pandas intente evaluar una Series como booleano.
            datos_para_ml = {
                "edad": int(d["edad"]),
                "glucosa": float(d["glucosa"]),
                "presion_sistolica": int(d["presion_sistolica"]),
                "presion_diastolica": int(d["presion_diastolica"]),
                "imc": float(d["imc"]),
                "colesterol": float(d["colesterol"]),
                "frecuencia_cardiaca": int(d["frecuencia_cardiaca"]),
                "saturacion_oxigeno": float(d["saturacion_oxigeno"]),
                "temperatura": float(d["temperatura"]),
                "fumador": 1 if d["fumador"] else 0,
                "consumo_alcohol": 1 if d["consumo_alcohol"] else 0,
                "antecedentes_familiares": 1 if d["antecedentes_familiares"] else 0,
                "sexo": {'F': 0, 'M': 1, 'O': 2}.get(d["sexo"], 1),
                "actividad_fisica": {'Alta': 0, 'Baja': 1, 'Media': 2}.get(d["actividad_fisica"], 1),
            }

            try:
                from ml.trainer import predecir
                
                # 1. Creamos el DataFrame inicial
                df_pred = pd.DataFrame([datos_para_ml])
                
                # 2. FORZAMOS la conversión a tipos nativos de Python. 
                # Esto elimina cualquier rastro de 'Series' o tipos de Pandas que causan el error.
                datos_limpios = df_pred.to_dict(orient='records')
                df_final = pd.DataFrame(datos_limpios)
                
                # 3. Enviamos el DataFrame limpio al trainer
                resultado = predecir(df_final)
                
                return Response(resultado, status=status.HTTP_200_OK)
            
            except Exception as e:
                import traceback
                error_msg = str(e)
                trace = traceback.format_exc()
                # Imprimimos el error en consola para que veas qué pasa exactamente
                print(f"Error detectado: {error_msg}")
                return Response({
                    'error': 'Error en la predicción', 
                    'detalle': error_msg, 
                    'trace': trace
                }, status=500)
                
        return Response(serializer.errors, status=400)