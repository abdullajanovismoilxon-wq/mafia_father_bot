from django.db import transaction
from apps.games.models import Game, Player, Vote, GamePhase


class VoteValidationError(Exception):
    """Raised when a vote submission fails domain validation."""
    pass


class VotingService:
    """Service handling validation and persistence of Voting records."""

    @classmethod
    def submit_vote(cls, game: Game, voter: Player, target: Player) -> Vote:
        """
        Validates and records a vote under atomic transaction.
        Checks:
        1. Game is in VOTING phase.
        2. Voter belongs to game and is alive.
        3. Target belongs to game and is alive.
        4. Voter cannot vote for themselves.
        """
        with transaction.atomic():
            if game.phase != GamePhase.VOTING:
                raise VoteValidationError("Votes can only be cast during the VOTING phase.")

            if voter.game_id != game.id or not voter.is_alive:
                raise VoteValidationError("Only living players in this game can vote.")

            if target.game_id != game.id or not target.is_alive:
                raise VoteValidationError("Target player must be a living participant in this game.")

            if voter.id == target.id:
                raise VoteValidationError("Players cannot vote for themselves.")

            # Create or update existing vote for this round
            vote, _ = Vote.objects.update_or_create(
                game=game,
                round=game.round_number,
                voter=voter,
                defaults={'target': target}
            )
            return vote
