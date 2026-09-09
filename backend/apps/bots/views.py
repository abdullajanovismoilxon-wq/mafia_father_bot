from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.common.permissions import IsOwnerPermission
from .models import Bot, BotConfiguration, RuntimeStatus, BotStatus
from .serializers import BotSerializer, BotConfigurationSerializer


class BotViewSet(viewsets.ModelViewSet):
    """
    Bot Management ViewSet with strict multi-tenant isolation.
    Users can only list, view, edit, or delete their OWN bots.
    """
    serializer_class = BotSerializer
    permission_classes = [IsAuthenticated, IsOwnerPermission]

    def get_queryset(self):
        # Strict Multi-Tenancy Enforcement
        return Bot.objects.filter(owner=self.request.user).select_related('configuration', 'credential')

    def perform_create(self, serializer):
        from apps.subscriptions.services import EntitlementService, EntitlementLimitExceededError
        from rest_framework.exceptions import APIException

        try:
            EntitlementService.can_create_bot(self.request.user)
        except EntitlementLimitExceededError as e:
            class PlanLimitReached(APIException):
                status_code = 403
                default_detail = 'Plan limit reached.'
            err = PlanLimitReached()
            err.detail = {
                'code': 'PLAN_LIMIT_REACHED',
                'feature': e.feature_code,
                'limit': e.limit,
                'current_usage': e.current_usage,
                'detail': str(e),
            }
            raise err

        serializer.save(owner=self.request.user)

    @action(detail=True, methods=['get', 'put', 'patch'], permission_classes=[IsAuthenticated, IsOwnerPermission])
    def configuration(self, request, pk=None):
        """Manage specific bot configuration settings."""
        bot = self.get_object()
        config, _ = BotConfiguration.objects.get_or_create(bot=bot)

        if request.method in ['PUT', 'PATCH']:
            serializer = BotConfigurationSerializer(config, data=request.data, partial=(request.method == 'PATCH'))
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)

        serializer = BotConfigurationSerializer(config)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsOwnerPermission])
    def start_bot(self, request, pk=None):
        """Runtime state change endpoint: Start bot."""
        bot = self.get_object()
        bot.status = BotStatus.ACTIVE
        bot.runtime_status = RuntimeStatus.RUNNING
        bot.save(update_fields=['status', 'runtime_status'])
        return Response({'status': 'Bot started successfully', 'runtime_status': bot.runtime_status})

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsOwnerPermission])
    def stop_bot(self, request, pk=None):
        """Runtime state change endpoint: Stop bot."""
        bot = self.get_object()
        bot.status = BotStatus.PAUSED
        bot.runtime_status = RuntimeStatus.OFFLINE
        bot.save(update_fields=['status', 'runtime_status'])
        return Response({'status': 'Bot stopped successfully', 'runtime_status': bot.runtime_status})
