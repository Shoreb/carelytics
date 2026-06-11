from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clinical_records', '0005_alter_patient_altura_alter_patient_colesterol_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='patient',
            name='imc',
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=5, null=True,
                help_text='Calculado automáticamente por el ETL'
            ),
        ),
        migrations.AddField(
            model_name='patient',
            name='fecha_consulta',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='patient',
            name='riesgo_enfermedad',
            field=models.CharField(
                max_length=10,
                choices=[
                    ('Bajo', 'Bajo'), ('Medio', 'Medio'),
                    ('Alto', 'Alto'), ('Crítico', 'Crítico')
                ],
                default='Bajo',
            ),
        ),
    ]
