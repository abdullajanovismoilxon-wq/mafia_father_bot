from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from apps.common.views.health import health_check, readiness_check, liveness_check

urlpatterns = [
    path('', RedirectView.as_view(url='/superadmin/', permanent=False)),
    path('superadmin/', include('apps.superadmin.urls')),
    path('webapp/', include('apps.webapp.urls')),
    path('admin/', admin.site.urls),

    # Observability / Health Endpoints
    path('health/', health_check, name='health_check'),
    path('health/live/', liveness_check, name='liveness_check'),
    path('health/ready/', readiness_check, name='readiness_check'),

    # OpenAPI Schema & Docs
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/v1/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/v1/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # API V1 Endpoints
    path('api/v1/auth/', include('apps.users.urls')),
    path('api/v1/bots/', include('apps.bots.urls')),
    path('api/v1/subscriptions/', include('apps.subscriptions.urls')),
    path('api/v1/payments/', include('apps.payments.urls')),
    path('api/v1/templates/', include('apps.templates.urls')),
    path('api/v1/games/', include('apps.games.urls')),
    path('api/v1/analytics/', include('apps.analytics.urls')),
    path('api/v1/tournaments/', include('apps.tournaments.urls')),
    path('api/v1/configurations/', include('apps.games.config_urls')),
    path('api/v1/roles/', include('apps.games.role_urls')),
    path('api/v1/billing/', include('apps.subscriptions.billing_urls')),
    path('api/v1/admin/', include('apps.common.admin_urls')),
    path('api/v1/economy/', include('apps.economy.urls')),
    path('api/v1/stats/', include('apps.stats.urls')),
]

from django.conf import settings
from django.conf.urls.static import static
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
