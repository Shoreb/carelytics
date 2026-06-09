"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from clinical_records.views import PatientViewSet, DashboardKPIView, HealthReportView, PredictionView
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from etl.views import ETLRunView
from django.views.generic import TemplateView

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView
)

# Creamos el router y registramos nuestro ViewSet
router = DefaultRouter()
router.register(r'pacientes', PatientViewSet, basename='paciente')

urlpatterns = [
    path('admin/', admin.site.urls),
    # Endpoint de Login (Obtener el token)
    path('api/auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    # Endpoint para refrescar el token (cuando caduque)
    path('api/auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    # Ruta específica para los KPIs
    path('api/dashboard/kpis/', DashboardKPIView.as_view(), name='dashboard-kpis'),
    # Endpoint de ejecución ETL
    path('api/etl/run/', ETLRunView.as_view(), name='etl-run'),
    # Endpoint de Reportes
    path('api/reportes/', HealthReportView.as_view(), name='health-reports'),
    # Endpoint de Predicciones
    path('api/predicciones/', PredictionView.as_view(), name='paciente-prediccion'),
    # Todas las URLs generadas por el router irán bajo /api/
    path('api/', include(router.urls)),
    # Endpoints Automáticos del Esquema de Documentación OpenAPI 3.0
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    
    # Interfaces Visuales Interactivas para Pruebas del Equipo de Desarrollo
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

   path('login/', TemplateView.as_view(template_name='login.html'), name='frontend_login'),
    
    # Vista del Dashboard Analítico Interactivo
    path('dashboard/', TemplateView.as_view(template_name='dashboard.html'), name='frontend_dashboard'),
    
    # Redirección global automática al Login
    path('', TemplateView.as_view(template_name='login.html'), name='frontend_home'),
]
