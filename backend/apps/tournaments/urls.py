from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TournamentViewSet

router = DefaultRouter()
router.register(r'', TournamentViewSet, basename='tournaments')

urlpatterns = [
    path('', include(router.urls)),
]
