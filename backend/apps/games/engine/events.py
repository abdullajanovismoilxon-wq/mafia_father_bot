import logging
from typing import Optional, Dict, Any
from django.db import transaction
from apps.games.models import Game, Player, GameEvent, GameEventType

logger = logging.getLogger(__name__)


class GameEventService:
    """Service logging and querying persistent game events."""

    @classmethod
    def log_event(
        cls,
        game: Game,
        event_type: str,
        actor: Optional[Player] = None,
        target: Optional[Player] = None,
        message: str = '',
        metadata: Optional[Dict[str, Any]] = None,
        round_number: Optional[int] = None,
        phase: Optional[str] = None
    ) -> GameEvent:
        """
        Creates an immutable GameEvent entry for analytics, audit, and replay.
        """
        try:
            cur_round = round_number if round_number is not None else game.round_number
            cur_phase = phase if phase is not None else game.phase

            event = GameEvent.objects.create(
                game=game,
                event_type=event_type,
                round=cur_round,
                phase=cur_phase,
                actor=actor,
                target=target,
                message=message,
                metadata=metadata or {}
            )
            logger.debug(f"[Game #{game.id}] Event {event_type}: {message}")
            return event
        except Exception as e:
            logger.warning(f"Failed to log GameEvent {event_type} for Game #{game.id}: {e}")
            # Do not block gameplay flow if logging fails
            return None
