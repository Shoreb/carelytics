from django.db import models
from django.contrib.auth.models import User


class ETLLog(models.Model):
    """
    Registra cada ejecución del pipeline ETL para trazabilidad y auditoría.

    Patrón: Event Log / Audit Trail.
    Cada fila es inmutable una vez creada; nunca se edita, solo se consulta.
    """

    class EstadoChoices(models.TextChoices):
        EXITOSO = 'exitoso', 'Exitoso'
        FALLIDO = 'fallido', 'Fallido'
        PARCIAL = 'parcial', 'Parcial'

    # ── Metadatos de ejecución ───────────────────────────────────────────────
    fecha_ejecucion = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='etl_logs',
        help_text='Usuario que disparó el proceso ETL'
    )
    fuente_datos = models.CharField(
        max_length=255,
        default='dataset_clinico_etl_1800_registros.xlsx',
        help_text='Nombre del archivo o URL de origen'
    )

    # ── Métricas de procesamiento ────────────────────────────────────────────
    registros_leidos = models.PositiveIntegerField(default=0)
    registros_duplicados = models.PositiveIntegerField(default=0)
    registros_invalidos = models.PositiveIntegerField(default=0)
    registros_cargados = models.PositiveIntegerField(default=0)
    tiempo_ejecucion_seg = models.DecimalField(
        max_digits=8, decimal_places=3, default=0,
        help_text='Tiempo total de ejecución en segundos'
    )

    # ── Resultado ────────────────────────────────────────────────────────────
    estado = models.CharField(
        max_length=10,
        choices=EstadoChoices.choices,
        default=EstadoChoices.EXITOSO
    )
    mensaje_error = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-fecha_ejecucion']
        verbose_name = 'Log ETL'
        verbose_name_plural = 'Logs ETL'

    def __str__(self):
        return (
            f"ETL {self.fecha_ejecucion.strftime('%Y-%m-%d %H:%M')} "
            f"— {self.registros_cargados} registros — {self.estado}"
        )
