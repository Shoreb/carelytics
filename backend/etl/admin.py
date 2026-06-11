from django.contrib import admin
from etl.models import ETLLog


@admin.register(ETLLog)
class ETLLogAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'fecha_ejecucion', 'usuario', 'fuente_datos',
        'registros_leidos', 'registros_cargados', 'tiempo_ejecucion_seg', 'estado'
    ]
    list_filter = ['estado', 'fecha_ejecucion']
    search_fields = ['usuario__username', 'fuente_datos']
    readonly_fields = [f.name for f in ETLLog._meta.fields]

    def has_add_permission(self, request):
        return False  # Los logs solo los crea el sistema

    def has_change_permission(self, request, obj=None):
        return False  # Inmutables
