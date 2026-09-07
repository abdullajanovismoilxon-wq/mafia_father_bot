from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from apps.common.permissions import IsOwnerPermission
from .models import Game, Player, GamePhase, GameConfiguration, Role
from .serializers import (
    GameSerializer, GameDetailSerializer, PlayerSerializer,
    GameConfigurationSerializer, RoleSerializer, RoleDetailSerializer,
)
from .engine.game_service import GameService


class GameViewSet(viewsets.ModelViewSet):
    """
    Game Management ViewSet with strict multi-tenant isolation.
    Users can only list, view, or control games associated with THEIR bots.
    """
    permission_classes = [IsAuthenticated, IsOwnerPermission]

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return GameDetailSerializer
        return GameSerializer

    def get_queryset(self):
        # Strict Multi-Tenancy Enforcement
        return Game.objects.filter(bot__owner=self.request.user).select_related('bot').prefetch_related('players')

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsOwnerPermission])
    def start(self, request, pk=None):
        """API action to manually start a game lobby."""
        game = self.get_object()
        try:
            assignments = GameService.start_game(game)
            return Response({
                'detail': 'Game started successfully.',
                'phase': game.phase,
                'players_count': len(assignments)
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsOwnerPermission])
    def cancel(self, request, pk=None):
        """API action to cancel a game."""
        game = self.get_object()
        game.phase = GamePhase.CANCELED
        game.status = GamePhase.CANCELED
        game.save(update_fields=['phase', 'status'])
        return Response({'detail': 'Game canceled successfully.', 'phase': game.phase}, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated, IsOwnerPermission])
    def players(self, request, pk=None):
        """Retrieve list of players in this game."""
        game = self.get_object()
        serializer = PlayerSerializer(game.players.all(), many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated, IsOwnerPermission])
    def state(self, request, pk=None):
        """Retrieve safe game state overview for dashboard monitoring."""
        game = self.get_object()
        alive_count = game.players.filter(is_alive=True).count()
        total_count = game.players.count()

        snapshot_data = None
        try:
            snap = game.configuration_snapshot
            snapshot_data = {
                'name': snap.configuration_name,
                'game_mode': snap.game_mode,
                'night_duration': snap.night_duration,
                'voting_duration': snap.voting_duration,
                'tie_behavior': snap.tie_behavior,
            }
        except Exception:
            pass

        return Response({
            'id': str(game.id),
            'bot_id': str(game.bot_id),
            'bot_name': game.bot.name,
            'chat_id': game.chat_id,
            'phase': game.phase,
            'status': game.status,
            'round_number': game.round_number,
            'total_players': total_count,
            'alive_players': alive_count,
            'winner_team': game.winner_team,
            'started_at': game.started_at,
            'finished_at': game.finished_at,
            'configuration_snapshot': snapshot_data,
        })


class GameConfigurationViewSet(viewsets.ModelViewSet):
    """
    CRUD for GameConfiguration. Strictly multi-tenant.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = GameConfigurationSerializer

    def get_queryset(self):
        return GameConfiguration.objects.filter(owner=self.request.user).prefetch_related('distribution_rules__role')

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def get_object(self):
        obj = super().get_object()
        if obj.owner != self.request.user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("You do not own this configuration.")
        return obj


class RoleViewSet(viewsets.ModelViewSet):
    """
    CRUD for custom Roles. System roles are read-only for all users.
    Users can create/edit/deactivate their own custom roles.
    """
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ('retrieve', 'create', 'update', 'partial_update'):
            return RoleDetailSerializer
        return RoleSerializer

    def get_queryset(self):
        # Return own roles + system roles
        from django.db.models import Q
        return Role.objects.filter(
            Q(owner=self.request.user) | Q(is_system=True)
        ).filter(is_active=True).prefetch_related('abilities')

    def perform_create(self, serializer):
        from apps.subscriptions.services import EntitlementService, EntitlementLimitExceededError
        from rest_framework.exceptions import APIException

        try:
            EntitlementService.can_use_custom_roles(self.request.user)
        except EntitlementLimitExceededError as e:
            class PlanLimitReached(APIException):
                status_code = 403
                default_detail = 'Plan limit reached.'
            err = PlanLimitReached()
            err.detail = {'code': 'PLAN_LIMIT_REACHED', 'feature': e.feature_code, 'detail': str(e)}
            raise err

        serializer.save(owner=self.request.user, is_system=False)

    def get_object(self):
        obj = super().get_object()
        if self.action not in ('retrieve', 'list'):
            if obj.is_system:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("System roles cannot be modified.")
            if obj.owner != self.request.user:
                from rest_framework.exceptions import PermissionDenied
                raise PermissionDenied("You do not own this role.")
        return obj

    def perform_destroy(self, instance):
        """Soft-delete: deactivate instead of hard delete."""
        if instance.is_system:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("System roles cannot be deleted.")
        instance.is_active = False
        instance.save(update_fields=['is_active'])

