import logging
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Tournament, TournamentStatus, ParticipantStatus
from .serializers import (
    TournamentSerializer, TournamentDetailSerializer, TournamentCreateSerializer,
    TournamentParticipantSerializer, TournamentRoundSerializer,
)
from .services import TournamentService, TournamentValidationError

logger = logging.getLogger(__name__)


class TournamentViewSet(viewsets.ModelViewSet):
    """
    Full Tournament management.
    Multi-tenancy: owners manage; others can join/view.
    """
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Owners see their own. Others see tournaments they participate in.
        from django.db.models import Q
        return Tournament.objects.filter(
            Q(owner=user) | Q(participants__telegram_user_id__isnull=False)
        ).filter(owner=user).distinct().order_by('-created_at')

    def get_serializer_class(self):
        if self.action == 'create':
            return TournamentCreateSerializer
        if self.action in ('retrieve', 'update', 'partial_update'):
            return TournamentDetailSerializer
        return TournamentSerializer

    def perform_create(self, serializer):
        game_template = serializer.validated_data.get('game_template')
        try:
            tournament = TournamentService.create_tournament(
                owner=self.request.user,
                name=serializer.validated_data['name'],
                description=serializer.validated_data.get('description', ''),
                max_players=serializer.validated_data.get('max_players', 24),
                players_per_game=serializer.validated_data.get('players_per_game', 6),
                total_rounds=serializer.validated_data.get('total_rounds', 3),
                game_template=game_template,
                scoring_config=serializer.validated_data.get('scoring_config', {}),
            )
            # Store the created tournament for response
            serializer.instance = tournament
        except TournamentValidationError as e:
            from rest_framework.exceptions import ValidationError
            raise ValidationError(str(e))

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        output = TournamentDetailSerializer(serializer.instance, context={'request': request})
        return Response(output.data, status=status.HTTP_201_CREATED)

    def _require_owner(self, tournament):
        if tournament.owner != self.request.user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only the tournament owner can perform this action.")

    @action(detail=True, methods=['post'], url_path='open-registration')
    def open_registration(self, request, pk=None):
        """Open registration for a DRAFT tournament."""
        tournament = self.get_object()
        self._require_owner(tournament)
        try:
            TournamentService.open_registration(tournament)
        except TournamentValidationError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(TournamentDetailSerializer(tournament, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='start')
    def start(self, request, pk=None):
        """Start tournament (REGISTRATION -> ACTIVE)."""
        tournament = self.get_object()
        self._require_owner(tournament)
        try:
            TournamentService.start_tournament(tournament)
        except TournamentValidationError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(TournamentDetailSerializer(tournament, context={'request': request}).data)

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        """Cancel a tournament."""
        tournament = self.get_object()
        self._require_owner(tournament)
        try:
            TournamentService.cancel_tournament(tournament)
        except TournamentValidationError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': 'Tournament cancelled.'})

    @action(detail=True, methods=['post'], url_path='join')
    def join(self, request, pk=None):
        """Join a tournament as a participant."""
        tournament = Tournament.objects.get(id=pk)  # Anyone can join, not just owner's queryset
        telegram_user_id = request.data.get('telegram_user_id')
        display_name = request.data.get('display_name', request.user.username or request.user.email)
        username = request.data.get('username', '')

        if not telegram_user_id:
            return Response(
                {'detail': 'telegram_user_id is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            participant = TournamentService.register_participant(
                tournament, int(telegram_user_id), display_name, username
            )
        except TournamentValidationError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Tournament.DoesNotExist:
            return Response({'detail': 'Tournament not found.'}, status=status.HTTP_404_NOT_FOUND)

        return Response(
            TournamentParticipantSerializer(participant).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['post'], url_path='leave')
    def leave(self, request, pk=None):
        """Withdraw from a tournament."""
        tournament = Tournament.objects.get(id=pk)
        telegram_user_id = request.data.get('telegram_user_id')
        if not telegram_user_id:
            return Response({'detail': 'telegram_user_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            TournamentService.withdraw_participant(tournament, int(telegram_user_id))
        except TournamentValidationError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': 'Withdrawn from tournament.'})

    @action(detail=True, methods=['get'], url_path='participants')
    def participants(self, request, pk=None):
        """List all active participants."""
        tournament = self.get_object()
        qs = tournament.participants.filter(status=ParticipantStatus.ACTIVE)
        return Response(TournamentParticipantSerializer(qs, many=True).data)

    @action(detail=True, methods=['get'], url_path='leaderboard')
    def leaderboard(self, request, pk=None):
        """Get sorted tournament leaderboard."""
        tournament = self.get_object()
        data = TournamentService.get_leaderboard(tournament)
        return Response(data)

    @action(detail=True, methods=['get'], url_path='rounds')
    def rounds(self, request, pk=None):
        """List tournament rounds."""
        tournament = self.get_object()
        qs = tournament.rounds.all()
        return Response(TournamentRoundSerializer(qs, many=True).data)
