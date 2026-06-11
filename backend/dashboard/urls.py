from django.urls import path
from dashboard.views import AnalyticsView, CriticosView, SegmentacionView

urlpatterns = [
    path('analytics/',    AnalyticsView.as_view(),    name='analytics'),
    path('criticos/',     CriticosView.as_view(),     name='pacientes-criticos'),
    path('segmentacion/', SegmentacionView.as_view(), name='segmentacion'),
]