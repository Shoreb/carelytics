from rest_framework import serializers
from etl.models import ETLLog


class ETLLogSerializer(serializers.ModelSerializer):
    usuario_nombre = serializers.SerializerMethodField()

    class Meta:
        model = ETLLog
        fields = [
            'id',
            'fecha_ejecucion',
            'usuario_nombre',
            'fuente_datos',
            'registros_leidos',
            'registros_duplicados',
            'registros_invalidos',
            'registros_cargados',
            'tiempo_ejecucion_seg',
            'estado',
            'mensaje_error',
        ]

    def get_usuario_nombre(self, obj):
        if obj.usuario:
            return obj.usuario.get_full_name() or obj.usuario.username
        return 'Sistema'