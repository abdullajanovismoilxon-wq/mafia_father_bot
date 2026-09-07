from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import GameTemplateViewSet, BotTemplateViewSet

router = DefaultRouter()
router.register(r'game-templates', GameTemplateViewSet, basename='game-templates')
router.register(r'bot-templates', BotTemplateViewSet, basename='bot-templates')

urlpatterns = [
    path('', include(router.urls)),
]
