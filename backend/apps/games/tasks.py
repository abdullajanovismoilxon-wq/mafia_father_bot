import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from apps.games.models import Game, GamePhase
from apps.games.engine.game_service import GameService
from apps.games.engine.recovery import GameRecoveryService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def auto_advance_phase_task(self, game_id: str, expected_phase: str, expected_round: int):
    """
    Celery task handling phase timers.
    Checks if game is still in expected_phase and expected_round, then advances phase cleanly.
    """
    try:
        game = Game.objects.get(id=game_id)
        if game.phase == expected_phase and game.round_number == expected_round:
            logger.info(f"Timer expired for Game #{game.id} in phase '{expected_phase}'. Advancing phase...")
            result = GameService.advance_phase(game)
            return result
        else:
            logger.info(f"Timer ignored for Game #{game.id}: State changed (Current: '{game.phase}', Expected: '{expected_phase}').")
            return None
    except Game.DoesNotExist:
        logger.error(f"Task failed: Game #{game_id} does not exist.")
    except Exception as e:
        logger.exception(f"Error in auto_advance_phase_task for Game #{game_id}: {e}")


@shared_task
def schedule_phase_timer(game_id: str, expected_phase: str, expected_round: int, duration_seconds: int):
    """
    Helper scheduling an asynchronous timer task with countdown.
    Updates game.phase_ends_at for recovery awareness.
    """
    try:
        game = Game.objects.get(id=game_id)
        game.phase_ends_at = timezone.now() + timedelta(seconds=duration_seconds)
        game.save(update_fields=['phase_ends_at'])
        auto_advance_phase_task.apply_async(
            args=[str(game.id), expected_phase, expected_round],
            countdown=duration_seconds
        )
    except Exception as e:
        logger.error(f"Failed to schedule phase timer for Game #{game_id}: {e}")


@shared_task
def reconcile_active_games_task():
    """Periodic Celery Beat task reconciling and recovering stalled games."""
    return GameRecoveryService.recover_active_games()
