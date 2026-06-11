"""
Autenticación personalizada.

Extiende TokenObtainPairView para inyectar el 'role' del usuario en el JWT.
El 'role' se lee del primer grupo de Django al que pertenece el usuario.

Grupos esperados en BD: 'Administrador', 'Medico', 'Analista'
Si el usuario no tiene grupo → role = 'Medico' por defecto.

¿Por qué grupos de Django y no un campo custom?
  - Usa el sistema de permisos nativo de Django (sin migraciones extra).
  - Fácil de asignar desde el panel admin.
  - Se puede combinar con permisos granulares por vista.
"""

from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # Claims adicionales en el payload del JWT
        token['username'] = user.username
        token['email']    = user.email
        token['nombre']   = user.get_full_name() or user.username

        # Rol: primer grupo del usuario, o 'Medico' como fallback
        grupos = list(user.groups.values_list('name', flat=True))
        token['role'] = grupos[0] if grupos else 'Medico'

        return token


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
