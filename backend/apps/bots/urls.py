from rest_framework.routers import DefaultRouter
from .views import BotViewSet

router = DefaultRouter()
router.register('', BotViewSet, basename='bot')

urlpatterns = router.urls
