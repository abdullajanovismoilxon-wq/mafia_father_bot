from apps.games.models import Game, GamePhase


class InvalidStateTransitionError(Exception):
    """Raised when an illegal phase transition is attempted."""
    pass


class GameStateMachine:
    """
    Enforces valid phase transitions for Mafia games.
    """

    ALLOWED_TRANSITIONS = {
        GamePhase.WAITING: [GamePhase.STARTING, GamePhase.CANCELED],
        GamePhase.STARTING: [GamePhase.NIGHT, GamePhase.CANCELED],
        GamePhase.NIGHT: [GamePhase.DAY, GamePhase.FINISHED, GamePhase.CANCELED],
        GamePhase.DAY: [GamePhase.DISCUSSION, GamePhase.VOTING, GamePhase.FINISHED, GamePhase.CANCELED],
        GamePhase.DISCUSSION: [GamePhase.VOTING, GamePhase.FINISHED, GamePhase.CANCELED],
        GamePhase.VOTING: [GamePhase.ELIMINATION, GamePhase.NIGHT, GamePhase.FINISHED, GamePhase.CANCELED],
        GamePhase.ELIMINATION: [GamePhase.NIGHT, GamePhase.FINISHED, GamePhase.CANCELED],
        GamePhase.FINISHED: [],
        GamePhase.CANCELED: [],
    }

    @classmethod
    def transition(cls, game: Game, target_phase: str) -> str:
        """
        Validates and transitions game to target_phase.
        Updates phase and status fields cleanly.
        """
        current_phase = game.phase
        allowed = cls.ALLOWED_TRANSITIONS.get(current_phase, [])

        if target_phase not in allowed:
            raise InvalidStateTransitionError(
                f"Cannot transition Game #{game.id} from state '{current_phase}' to '{target_phase}'. Allowed: {allowed}"
            )

        game.phase = target_phase
        game.status = target_phase
        game.save(update_fields=['phase', 'status', 'updated_at'])
        return game.phase
