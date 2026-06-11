from django.urls import path
from ml.views import MLEntrenarView, MLMetricasView, PrediccionView

urlpatterns = [
    path('entrenar/', MLEntrenarView.as_view(), name='ml-entrenar'),
    path('metricas/', MLMetricasView.as_view(), name='ml-metricas'),
]
