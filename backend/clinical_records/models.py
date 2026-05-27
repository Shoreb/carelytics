from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

class Patient(models.Model):
    # Opciones para campos categóricos
    class SexChoices(models.TextChoices):
        MASCULINO = 'M', 'Masculino'
        FEMENINO = 'F', 'Femenino'
        OTRO = 'O', 'Otro'

    # Identificación y Demografía
    identificacion = models.CharField(max_length=50, unique=True)
    nombre = models.CharField(max_length=150)
    edad = models.PositiveSmallIntegerField(validators=[MaxValueValidator(120)])
    sexo = models.CharField(max_length=1, choices=SexChoices.choices, default=SexChoices.OTRO)
    
    # Datos Clínicos (Importantes para el modelo de ML futuro)
    peso = models.DecimalField(max_digits=5, decimal_places=2, help_text="Peso en kg")
    altura = models.DecimalField(max_digits=3, decimal_places=2, help_text="Altura en metros")
    glucosa = models.DecimalField(max_digits=5, decimal_places=2)
    colesterol = models.DecimalField(max_digits=5, decimal_places=2)
    presion_sistolica = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(40), MaxValueValidator(250)]
    )
    
    antecedentes_familiares = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre} ({self.identificacion})"

    @property
    def imc(self):
        """Calcula el Índice de Masa Corporal dinámicamente."""
        if self.altura > 0:
            return round(float(self.peso) / (float(self.altura) ** 2), 2)
        return 0
