from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import GameConfigurationViewSet

router = DefaultRouter()
router.register(r'', GameConfigurationViewSet, basename='game-configuration')

urlpatterns = [
    path('', include(router.urls)),
]
