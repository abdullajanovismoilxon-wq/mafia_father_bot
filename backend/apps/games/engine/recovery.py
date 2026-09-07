import logging
from typing import List, Dict, Any
from django.utils import timezone
from apps.games.models import Game, GamePhase
from apps.games.engine.game_service import GameService

logger = logging.getLogger(__name__)


class GameRecoveryService:
    """
    Recovers and reconciles active games following server, bot runtime, or worker restart.
    Authoritative state is restored directly from PostgreSQL.
    """

    @classmethod
    def get_unresolved_active_games(cls) -> List[Game]:
        """Returns list of active in-flight games requiring runtime restoration."""
        return list(
            Game.objects.filter(
                phase__in=[
                    GamePhase.STARTING,
                    GamePhase.NIGHT,
                    GamePhase.DAY,
                    GamePhase.DISCUSSION,
                    GamePhase.VOTING,
                    GamePhase.ELIMINATION
                ]
            ).select_related('bot', 'game_configuration', 'configuration_snapshot').prefetch_related('players')
        )

    @classmethod
    def recover_active_games(cls) -> Dict[str, Any]:
        """
        Scans all active games and checks if their phase has timed out or needs phase advancement.
        """
        active_games = cls.get_unresolved_active_games()
        recovered_count = 0
        now = timezone.now()

        for game in active_games:
            try:
                # If phase_ends_at is in the past, advance phase
                if game.phase_ends_at and game.phase_ends_at <= now:
                    logger.info(f"Recovering expired phase for Game #{game.id} [{game.phase}]")
                    GameService.advance_phase(game)
                    recovered_count += 1
                else:
                    logger.info(f"Restored active Game #{game.id} [{game.phase}] in Chat {game.chat_id}")
                    recovered_count += 1
            except Exception as e:
                logger.error(f"Error recovering Game #{game.id}: {e}")

        return {
            'total_active': len(active_games),
            'recovered_count': recovered_count
        }
