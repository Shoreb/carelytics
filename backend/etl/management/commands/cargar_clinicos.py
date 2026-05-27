from django.core.management.base import BaseCommand
from etl import exploracion as ex
from clinical_records.models import Patient
import pandas as pd
import os

class Command(BaseCommand):
    help = 'Carga datos clínicos desde un Excel a la base de datos'

    def handle(self, *args, **options):
        archivo_nombre = 'dataset_clinico_etl_1800_registros.xlsx' 
        ruta = os.path.join(os.getcwd(), '..', 'datasets', archivo_nombre)
        
        if not os.path.exists(ruta):
            self.stdout.write(self.style.ERROR(f'No se encontró el archivo en: {ruta}'))
            return

        self.stdout.write(self.style.SUCCESS('Leyendo Excel y eliminando duplicados...'))
        df = pd.read_excel(ruta)
        df.drop_duplicates(subset=['id_paciente'], keep='first', inplace=True)

        # Mapeo de columnas del Excel a nombres internos
        mapeo_columnas = {
            'id_paciente': 'identificacion',
            'presión_sistólica': 'presion_sistolica',
            'presión_diastólica': 'presion_diastolica',
            'frecuencia_cardiaca': 'frecuencia_cardiaca',
            'actividad_física': 'actividad_fisica',
            'diagnóstico_preliminar': 'diagnostico_preliminar',
            'saturación_oxígeno': 'saturacion_oxigeno'
        }
        df.rename(columns=mapeo_columnas, inplace=True)

        pacientes_nuevos = []
        for _, row in df.iterrows():
            # Creamos el objeto aplicando TODAS las limpiezas
            p = Patient(
                identificacion = row['identificacion'],
                nombre = f"{row['nombres']} {row['apellidos']}",
                edad = ex.limpiar_entero(row['edad']),
                sexo = ex.limpiar_sexo(row['sexo']),
                peso = ex.limpiar_outliers(row.get('peso'), 'peso'),
                altura = row.get('altura') if not pd.isna(row.get('altura')) else 1.70,
                glucosa = row.get('glucosa') if not pd.isna(row.get('glucosa')) else 90,
                colesterol = row.get('colesterol') if not pd.isna(row.get('colesterol')) else 180,
                presion_sistolica = ex.limpiar_presion(row.get('presion_sistolica')),
                presion_diastolica = ex.limpiar_entero(row.get('presion_diastolica'), 80),
                frecuencia_cardiaca = ex.limpiar_entero(row.get('frecuencia_cardiaca'), 70),
                saturacion_oxigeno = row.get('saturacion_oxigeno', 95),
                temperatura = ex.limpiar_outliers(row.get('temperatura'), 'temperatura'),
                actividad_fisica = ex.limpiar_actividad(row.get('actividad_fisica')),
                diagnostico_preliminar = ex.limpiar_diagnostico(row.get('diagnostico_preliminar')),
                fumador = bool(row.get('fumador', False)),
                consumo_alcohol = bool(row.get('consumo_alcohol', False)),
                antecedentes_familiares = bool(row.get('antecedentes_familiares', False)),
                riesgo_enfermedad = row.get('riesgo_enfermedad', 'Bajo')
            )
            pacientes_nuevos.append(p)

        Patient.objects.bulk_create(pacientes_nuevos, ignore_conflicts=True)
        self.stdout.write(self.style.SUCCESS(f'¡Éxito! Procesados {len(pacientes_nuevos)} registros.'))