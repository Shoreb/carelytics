from django.db.models import Avg, Count, Max, Min, StdDev, Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from clinical_records.models import Patient


class AnalyticsView(APIView):
    """GET /api/dashboard/analytics/ — descriptive stats for all clinical variables."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Patient.objects.all()
        total = qs.count()
        if total == 0:
            return Response({'error': 'No data. Run the ETL first.'})

        def stats(field):
            agg = qs.aggregate(
                promedio=Avg(field), std=StdDev(field),
                minimo=Min(field),   maximo=Max(field),
            )
            return {k: round(float(v), 2) if v is not None else None
                    for k, v in agg.items()}

        moda_diag = (
            qs.values('diagnostico_preliminar')
              .annotate(n=Count('id')).order_by('-n').first()
        )
        moda_riesgo = (
            qs.values('riesgo_enfermedad')
              .annotate(n=Count('id')).order_by('-n').first()
        )

        return Response({
            'total_registros': total,
            'variables': {
                'edad':                stats('edad'),
                'imc':                 stats('imc'),
                'glucosa':             stats('glucosa'),
                'colesterol':          stats('colesterol'),
                'presion_sistolica':   stats('presion_sistolica'),
                'presion_diastolica':  stats('presion_diastolica'),
                'frecuencia_cardiaca': stats('frecuencia_cardiaca'),
                'saturacion_oxigeno':  stats('saturacion_oxigeno'),
                'temperatura':         stats('temperatura'),
            },
            'modas': {
                'diagnostico': moda_diag['diagnostico_preliminar'] if moda_diag else None,
                'riesgo':      moda_riesgo['riesgo_enfermedad'] if moda_riesgo else None,
            },
        })


class CriticosView(APIView):
    """GET /api/dashboard/criticos/ — patients meeting clinical criticality criteria."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Patient.objects.filter(
            Q(presion_sistolica__gt=180) |
            Q(glucosa__gt=300) |
            Q(saturacion_oxigeno__lt=85)
        ).values(
            'id', 'identificacion', 'nombre', 'edad', 'sexo',
            'presion_sistolica', 'glucosa', 'saturacion_oxigeno',
            'riesgo_enfermedad', 'diagnostico_preliminar',
        ).order_by('-presion_sistolica')[:100]

        data = list(qs)
        return Response({
            'total_criticos': len(data),
            'pacientes': data,
        })


class SegmentacionView(APIView):
    """GET /api/dashboard/segmentacion/ — cross-segmentation by age, sex, risk and IMC."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Patient.objects.all()

        riesgo_por_sexo = list(
            qs.values('riesgo_enfermedad', 'sexo')
              .annotate(n=Count('id'))
              .order_by('riesgo_enfermedad', 'sexo')
        )

        grupos = {
            '0-17':  qs.filter(edad__lt=18),
            '18-35': qs.filter(edad__gte=18, edad__lte=35),
            '36-50': qs.filter(edad__gte=36, edad__lte=50),
            '51-65': qs.filter(edad__gte=51, edad__lte=65),
            '65+':   qs.filter(edad__gt=65),
        }
        riesgo_por_edad = {
            grupo: dict(
                subqs.values('riesgo_enfermedad')
                     .annotate(n=Count('id'))
                     .values_list('riesgo_enfermedad', 'n')
            )
            for grupo, subqs in grupos.items()
        }

        top_diag = list(
            qs.values('diagnostico_preliminar')
              .annotate(n=Count('id')).order_by('-n')
              .values_list('diagnostico_preliminar', flat=True)[:5]
        )
        imc_por_diagnostico = [
            {
                'diagnostico': d,
                'imc_promedio': round(float(
                    qs.filter(diagnostico_preliminar=d).aggregate(v=Avg('imc'))['v'] or 0
                ), 2),
            }
            for d in top_diag
        ]

        fumadores_riesgo = list(
            qs.values('fumador', 'riesgo_enfermedad')
              .annotate(n=Count('id'))
              .order_by('fumador', 'riesgo_enfermedad')
        )

        return Response({
            'riesgo_por_sexo':       riesgo_por_sexo,
            'riesgo_por_grupo_edad': riesgo_por_edad,
            'imc_por_diagnostico':   imc_por_diagnostico,
            'fumadores_por_riesgo':  fumadores_riesgo,
        })