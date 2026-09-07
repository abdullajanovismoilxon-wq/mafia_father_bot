from django.db import connection
from django.db.models import Q
from django.conf import settings
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from apps.bots.models import Bot, BotStatus, RuntimeStatus


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Simple liveness health check endpoint."""
    return Response({
        'status': 'healthy',
        'service': 'MAFIA BOT FATHER Control Plane API',
        'version': '1.0.0',
        'timestamp': timezone.now().isoformat(),
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def liveness_check(request):
    """Kubernetes liveness probe endpoint."""
    return Response({
        'status': 'alive',
        'timestamp': timezone.now().isoformat(),
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def readiness_check(request):
    """Deep readiness check for Application, Database, Redis, and Bot Runtimes."""
    health_status = {
        'application': 'healthy',
        'database': 'unknown',
        'redis': 'unknown',
        'bot_runtimes': 'healthy',
    }
    is_healthy = True

    # 1. Database Check
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        health_status['database'] = 'healthy'
    except Exception as e:
        health_status['database'] = f'unhealthy: {str(e)}'
        is_healthy = False

    # 2. Redis Check
    try:
        import redis
        r = redis.Redis.from_url(settings.REDIS_URL, socket_timeout=2)
        r.ping()
        health_status['redis'] = 'healthy'
    except Exception as e:
        health_status['redis'] = f'unhealthy/degraded: {str(e)}'

    # 3. Bot Runtimes Check
    try:
        running_bots = Bot.objects.filter(runtime_status=RuntimeStatus.RUNNING).count()
        error_bots = Bot.objects.filter(Q(status=BotStatus.ERROR) | Q(runtime_status=RuntimeStatus.ERROR)).count()
        health_status['bot_runtimes'] = {
            'running_bots': running_bots,
            'error_bots': error_bots,
            'status': 'healthy' if error_bots == 0 else 'warning'
        }
    except Exception:
        health_status['bot_runtimes'] = 'unknown'

    response_code = status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    return Response({
        'status': 'ready' if is_healthy else 'degraded',
        'checks': health_status,
        'timestamp': timezone.now().isoformat(),
    }, status=response_code)
