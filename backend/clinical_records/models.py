from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class Patient(models.Model):
    """
    Modelo principal de paciente clínico.

    Decisión de diseño: imc se guarda como campo calculado (no solo @property)
    para permitir consultas analíticas eficientes sin cálculo en runtime.
    La property se mantiene como fallback si el campo es None.
    """

    class SexChoices(models.TextChoices):
        MASCULINO = 'M', 'Masculino'
        FEMENINO  = 'F', 'Femenino'
        OTRO      = 'O', 'Otro'

    class ActivityChoices(models.TextChoices):
        BAJA  = 'Baja',  'Baja'
        MEDIA = 'Media', 'Media'
        ALTA  = 'Alta',  'Alta'

    class RiesgoChoices(models.TextChoices):
        BAJO     = 'Bajo',     'Bajo'
        MEDIO    = 'Medio',    'Medio'
        ALTO     = 'Alto',     'Alto'
        CRITICO  = 'Crítico',  'Crítico'

    # ── Identificación ────────────────────────────────────────────────────────
    identificacion = models.CharField(max_length=50, unique=True)
    nombre         = models.CharField(max_length=150)
    edad           = models.PositiveSmallIntegerField(default=0)
    sexo           = models.CharField(
                        max_length=1, choices=SexChoices.choices,
                        default=SexChoices.OTRO)

    # ── Antropometría ─────────────────────────────────────────────────────────
    peso    = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    altura  = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    imc     = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                  help_text='Calculado automáticamente por el ETL')

    # ── Signos vitales ────────────────────────────────────────────────────────
    glucosa             = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    colesterol          = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    presion_sistolica   = models.PositiveSmallIntegerField(null=True, blank=True)
    presion_diastolica  = models.PositiveSmallIntegerField(null=True, blank=True)
    frecuencia_cardiaca = models.PositiveSmallIntegerField(null=True, blank=True)
    saturacion_oxigeno  = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    temperatura         = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)

    # ── Hábitos y antecedentes ────────────────────────────────────────────────
    fumador               = models.BooleanField(default=False)
    consumo_alcohol       = models.BooleanField(default=False)
    antecedentes_familiares = models.BooleanField(default=False)
    actividad_fisica      = models.CharField(
                                max_length=10, choices=ActivityChoices.choices,
                                default=ActivityChoices.BAJA)

    # ── Clínico ───────────────────────────────────────────────────────────────
    diagnostico_preliminar = models.CharField(max_length=100, default='Sin Diagnóstico')
    riesgo_enfermedad      = models.CharField(
                                max_length=10, choices=RiesgoChoices.choices,
                                default=RiesgoChoices.BAJO)

    # ── Temporal ──────────────────────────────────────────────────────────────
    fecha_consulta = models.DateField(null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Paciente'
        verbose_name_plural = 'Pacientes'
        indexes = [
            models.Index(fields=['riesgo_enfermedad']),
            models.Index(fields=['diagnostico_preliminar']),
            models.Index(fields=['fecha_consulta']),
        ]

    def __str__(self):
        return f"{self.nombre} ({self.identificacion})"

    @property
    def imc_calculado(self):
        """Fallback si el campo imc no fue calculado por el ETL."""
        if self.imc:
            return float(self.imc)
        if self.altura and float(self.altura) > 0 and self.peso:
            return round(float(self.peso) / (float(self.altura) ** 2), 2)
        return None

    @property
    def clasificacion_imc(self):
        val = self.imc_calculado
        if val is None:
            return 'Sin datos'
        if val < 18.5:
            return 'Bajo peso'
        if val < 25:
            return 'Normal'
        if val < 30:
            return 'Sobrepeso'
        return 'Obesidad'

    @property
    def es_critico(self):
        return (
            (self.presion_sistolica and self.presion_sistolica > 180) or
            (self.glucosa and float(self.glucosa) > 300) or
            (self.saturacion_oxigeno and float(self.saturacion_oxigeno) < 85)
        )
