from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

class Patient(models.Model):
    class SexChoices(models.TextChoices):
        MASCULINO = 'M', 'Masculino'
        FEMENINO = 'F', 'Femenino'
        OTRO = 'O', 'Otro'

    identificacion = models.CharField(max_length=50, unique=True)
    nombre = models.CharField(max_length=150)
    edad = models.PositiveSmallIntegerField()
    sexo = models.CharField(max_length=1, choices=SexChoices.choices, default=SexChoices.OTRO)
    
    peso = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    altura = models.DecimalField(max_digits=3, decimal_places=2, null=True)
    glucosa = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    colesterol = models.DecimalField(max_digits=5, decimal_places=2, null=True)

    presion_sistolica = models.PositiveSmallIntegerField(null=True)
    presion_diastolica = models.PositiveSmallIntegerField(null=True)
    frecuencia_cardiaca = models.PositiveSmallIntegerField(null=True)
    saturacion_oxigeno = models.DecimalField(max_digits=5, decimal_places=2, null=True)
    temperatura = models.DecimalField(max_digits=4, decimal_places=2, null=True)

    fumador = models.BooleanField(default=False)
    consumo_alcohol = models.BooleanField(default=False)

    class ActivityChoices(models.TextChoices):
        BAJA = 'Baja', 'Baja'
        MEDIA = 'Media', 'Media'
        ALTA = 'Alta', 'Alta'

    actividad_fisica = models.CharField(max_length=10, choices=ActivityChoices.choices, default=ActivityChoices.BAJA)
    antecedentes_familiares = models.BooleanField(default=False)
    diagnostico_preliminar = models.CharField(max_length=100, default='Sin Diagnóstico')
    riesgo_enfermedad = models.CharField(max_length=20, default='Bajo')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self): return f"{self.nombre} ({self.identificacion})"

    @property
    def imc(self):
        if self.altura and self.altura > 0 and self.peso:
            return round(float(self.peso) / (float(self.altura) ** 2), 2)
        return 0