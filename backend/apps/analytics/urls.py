from django.urls import path
from .views import OverviewAnalyticsView

urlpatterns = [
    path('overview/', OverviewAnalyticsView.as_view(), name='analytics_overview'),
]
