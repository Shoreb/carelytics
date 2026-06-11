from rest_framework import serializers
from .models import Patient


class PatientSerializer(serializers.ModelSerializer):
    """
    Serializer completo del modelo Patient.
    Agrega campos calculados de solo lectura (imc_calculado, clasificacion_imc,
    es_critico) para que el frontend los consuma directamente sin cálculos extra.
    """
    imc_calculado    = serializers.ReadOnlyField()
    clasificacion_imc = serializers.ReadOnlyField()
    es_critico       = serializers.ReadOnlyField()

    class Meta:
        model = Patient
        fields = [
            # Identificación
            'id', 'identificacion', 'nombre', 'edad', 'sexo',
            # Antropometría
            'peso', 'altura', 'imc', 'imc_calculado', 'clasificacion_imc',
            # Signos vitales
            'glucosa', 'colesterol',
            'presion_sistolica', 'presion_diastolica',
            'frecuencia_cardiaca', 'saturacion_oxigeno', 'temperatura',
            # Hábitos
            'fumador', 'consumo_alcohol', 'antecedentes_familiares', 'actividad_fisica',
            # Clínico
            'diagnostico_preliminar', 'riesgo_enfermedad', 'es_critico',
            # Temporal
            'fecha_consulta', 'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'imc_calculado', 'clasificacion_imc', 'es_critico']
