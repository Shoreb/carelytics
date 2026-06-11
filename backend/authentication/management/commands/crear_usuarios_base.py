"""
Management command: python manage.py crear_usuarios_base

Crea los grupos y usuarios iniciales del sistema.
Ejecutar UNA VEZ tras las migraciones iniciales.

Usuarios creados:
  admin → grupo Administrador
  medico → grupo Medico
  analista → grupo Analista
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group


GRUPOS = ['Administrador', 'Medico', 'Analista']

USUARIOS = [
    {'username': 'admin',    'password': 'admin123',    'email': 'admin@carelytics.com',
     'first_name': 'Admin',  'last_name': 'Sistema', 'grupo': 'Administrador', 'is_staff': True},
    {'username': 'medico',   'password': 'medico123',   'email': 'medico@carelytics.com',
     'first_name': 'Dr.',    'last_name': 'García',  'grupo': 'Medico',         'is_staff': False},
    {'username': 'analista', 'password': 'analista123', 'email': 'analista@carelytics.com',
     'first_name': 'Ana',    'last_name': 'López',   'grupo': 'Analista',       'is_staff': False},
]


class Command(BaseCommand):
    help = 'Crea grupos y usuarios base para Carelytics'

    def handle(self, *args, **options):
        # Crear grupos
        for nombre_grupo in GRUPOS:
            grupo, creado = Group.objects.get_or_create(name=nombre_grupo)
            if creado:
                self.stdout.write(self.style.SUCCESS(f'  Grupo creado: {nombre_grupo}'))
            else:
                self.stdout.write(f'  Grupo ya existe: {nombre_grupo}')

        # Crear usuarios
        for datos in USUARIOS:
            if User.objects.filter(username=datos['username']).exists():
                self.stdout.write(f"  Usuario ya existe: {datos['username']}")
                continue

            user = User.objects.create_user(
                username=datos['username'],
                password=datos['password'],
                email=datos['email'],
                first_name=datos['first_name'],
                last_name=datos['last_name'],
                is_staff=datos['is_staff'],
            )
            grupo = Group.objects.get(name=datos['grupo'])
            user.groups.add(grupo)
            self.stdout.write(
                self.style.SUCCESS(f"  Usuario creado: {datos['username']} → {datos['grupo']}")
            )

        self.stdout.write(self.style.SUCCESS('\n✅ Usuarios base creados exitosamente.'))
        self.stdout.write('   Credenciales: admin/admin123 · medico/medico123 · analista/analista123')
