"""
URL configuration — Carelytics Backend.
"""

from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView

from rest_framework.routers import DefaultRouter

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

from clinical_records.views import PatientViewSet, DashboardKPIView, HealthReportView, PredictionView
from etl.views import ETLRunView, ETLHistorialView
from ml.views import MLEntrenarView, MLMetricasView
from authentication.views import CustomTokenObtainPairView
from rest_framework_simplejwt.views import TokenRefreshView

router = DefaultRouter()
router.register(r'pacientes', PatientViewSet, basename='paciente')

urlpatterns = [
    # ── Admin ──────────────────────────────────────────────────────────────
    path('admin/', admin.site.urls),

    # ── Auth ───────────────────────────────────────────────────────────────
    path('api/auth/login/',          CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/token/refresh/',  TokenRefreshView.as_view(),          name='token_refresh'),

    # ── Dashboard ──────────────────────────────────────────────────────────
    path('api/dashboard/', include('dashboard.urls')),
    path('api/dashboard/kpis/',      DashboardKPIView.as_view(),          name='dashboard-kpis'),

    # ── ETL ────────────────────────────────────────────────────────────────
    path('api/etl/run/',             ETLRunView.as_view(),                 name='etl-run'),
    path('api/etl/historial/',       ETLHistorialView.as_view(),           name='etl-historial'),

    # ── ML ─────────────────────────────────────────────────────────────────
    path('api/ml/entrenar/',         MLEntrenarView.as_view(),             name='ml-entrenar'),
    path('api/ml/metricas/',         MLMetricasView.as_view(),             name='ml-metricas'),

    # ── Reportes y predicciones ────────────────────────────────────────────
    path('api/reportes/',            HealthReportView.as_view(),           name='health-reports'),
    path('api/predicciones/',        PredictionView.as_view(),             name='prediccion'),

    # ── Pacientes (CRUD + filtros) ─────────────────────────────────────────
    path('api/', include(router.urls)),

    # ── Documentación OpenAPI ──────────────────────────────────────────────
    path('api/schema/',              SpectacularAPIView.as_view(),         name='schema'),
    path('api/schema/swagger-ui/',   SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/',        SpectacularRedocView.as_view(url_name='schema'),   name='redoc'),

    # ── Frontend (templates Django) ────────────────────────────────────────
    path('login/',     TemplateView.as_view(template_name='login.html'),     name='frontend_login'),
    path('dashboard/', TemplateView.as_view(template_name='dashboard.html'), name='frontend_dashboard'),
    path('',           TemplateView.as_view(template_name='login.html'),     name='frontend_home'),
]
