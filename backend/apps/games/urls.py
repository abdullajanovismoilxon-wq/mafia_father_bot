from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import GameViewSet, GameConfigurationViewSet, RoleViewSet

router = DefaultRouter()
router.register(r'', GameViewSet, basename='game')

# Separate routers for configurations and roles
config_router = DefaultRouter()
config_router.register(r'', GameConfigurationViewSet, basename='game-configuration')

role_router = DefaultRouter()
role_router.register(r'', RoleViewSet, basename='role')

urlpatterns = router.urls
