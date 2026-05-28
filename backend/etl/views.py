from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from clinical_records.models import Patient
from etl import exploracion as ex
import pandas as pd
import os

class ETLRunView(APIView):
    """
    Endpoint para disparar el proceso de extracción, 
    transformación y carga de forma manual.
    """
    def post(self, request):
        archivo_nombre = 'dataset_clinico_etl_1800_registros.xlsx'
        ruta = os.path.join(os.getcwd(), '..', 'datasets', archivo_nombre)

        if not os.path.exists(ruta):
            return Response(
                {"error": "Archivo no encontrado"}, 
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            # 1. Leer y Deduplicar
            df = pd.read_excel(ruta)
            df.drop_duplicates(subset=['id_paciente'], keep='first', inplace=True)

            # 2. Renombrar columnas
            mapeo = {
                'id_paciente': 'identificacion',
                'presión_sistólica': 'presion_sistolica',
                'presión_diastólica': 'presion_diastolica',
                'actividad_física': 'actividad_fisica',
                'diagnóstico_preliminar': 'diagnostico_preliminar'
            }
            df.rename(columns=mapeo, inplace=True)

            # 3. Preparar objetos
            pacientes_nuevos = []
            for _, row in df.iterrows():
                p = Patient(
                    identificacion=row['identificacion'],
                    nombre=f"{row['nombres']} {row['apellidos']}",
                    edad=ex.limpiar_entero(row['edad']),
                    sexo=ex.limpiar_sexo(row['sexo']),
                    peso=ex.limpiar_outliers(row.get('peso'), 'peso'),
                    altura=row.get('altura') if not pd.isna(row.get('altura')) else 1.70,
                    presion_sistolica=ex.limpiar_presion(row.get('presion_sistolica')),
                    actividad_fisica=ex.limpiar_actividad(row.get('actividad_fisica')),
                    diagnostico_preliminar=ex.limpiar_diagnostico(row.get('diagnostico_preliminar')),
                    # ... puedes agregar el resto de campos que ya configuramos
                )
                pacientes_nuevos.append(p)

            # 4. Carga Masiva
            # Usamos ignore_conflicts para no duplicar si el botón se presiona dos veces
            Patient.objects.bulk_create(pacientes_nuevos, ignore_conflicts=True)

            return Response({
                "mensaje": "Proceso ETL ejecutado con éxito",
                "registros_procesados": len(pacientes_nuevos)
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )