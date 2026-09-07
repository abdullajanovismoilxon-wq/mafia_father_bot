"""
Tournament Service Layer.

TournamentService — lifecycle management (create, start, rounds, cancel).
TournamentGroupingService — isolated, testable participant grouping algorithm.
TournamentScoringService — deterministic score calculation from game results.

NO Telegram handler logic lives here.
NO arbitrary code execution from user input.
"""
import logging
import random
from typing import List, Dict, Any, Optional
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


class TournamentValidationError(Exception):
    """Raised when a tournament operation fails domain validation."""
    pass


class TournamentGroupingService:
    """
    Isolated, testable algorithm for grouping tournament participants into game groups.
    Accepts a list of participant IDs and desired group size; returns groups.
    No DB access — pure function for easy testing.
    """

    @staticmethod
    def group_participants(
        participant_ids: List[int],
        players_per_game: int,
        seed: Optional[int] = None,
    ) -> List[List[int]]:
        """
        Divide participant_ids into groups of players_per_game size.
        Shuffles randomly (optionally seeded for deterministic tests).
        If participants don't divide evenly, the last group may be smaller.
        Groups smaller than 4 are merged with the previous group.

        Args:
            participant_ids: List of telegram_user_ids (or any int IDs).
            players_per_game: Target group size.
            seed: Optional RNG seed for deterministic results.

        Returns:
            List of groups, each group is a list of IDs.
        """
        if players_per_game < 4:
            raise TournamentValidationError("players_per_game must be at least 4.")
        if not participant_ids:
            return []

        ids = list(participant_ids)
        rng = random.Random(seed)
        rng.shuffle(ids)

        groups = []
        i = 0
        while i < len(ids):
            group = ids[i:i + players_per_game]
            groups.append(group)
            i += players_per_game

        # Merge undersized last group (< 4) into the previous group
        if len(groups) >= 2 and len(groups[-1]) < 4:
            groups[-2].extend(groups.pop())

        return groups


class TournamentScoringService:
    """
    Calculates and applies tournament scores based on game results.
    Scoring config is read from Tournament.scoring_config.
    """

    @classmethod
    def calculate_scores(
        cls,
        tournament,  # Tournament instance
        game,        # Game instance
        player_results: List[Dict[str, Any]],
    ) -> Dict[int, int]:
        """
        Calculate score deltas for each participant based on game results.

        player_results: list of {
            telegram_user_id: int,
            survived: bool,
            won: bool,        # was on winning faction
            kills: int,       # night kills performed (Mafia only)
            is_final_survivor: bool,  # last alive player on winning team
        }

        Returns: {telegram_user_id: score_delta}
        """
        scoring = tournament.get_default_scoring()
        score_deltas: Dict[int, int] = {}

        for pr in player_results:
            uid = pr['telegram_user_id']
            delta = 0

            delta += scoring.get('participation', 1)

            if pr.get('survived'):
                delta += scoring.get('survival', 1)

            if pr.get('won'):
                delta += scoring.get('winning_faction', 3)

            kills = pr.get('kills', 0)
            delta += kills * scoring.get('mafia_elimination', 1)

            if pr.get('is_final_survivor'):
                delta += scoring.get('final_survivor', 2)

            score_deltas[uid] = delta

        return score_deltas

    @classmethod
    def apply_scores(
        cls,
        tournament,
        tournament_game,  # TournamentGame instance
        player_results: List[Dict[str, Any]],
    ) -> None:
        """
        Apply calculated score deltas to TournamentParticipant records.
        Marks the TournamentGame as score_applied.
        Must be called within a transaction.
        """
        from apps.tournaments.models import TournamentParticipant

        if tournament_game.score_applied:
            logger.warning(f"Scores already applied for TournamentGame #{tournament_game.id}")
            return

        score_deltas = cls.calculate_scores(tournament, tournament_game.game, player_results)

        with transaction.atomic():
            for uid, delta in score_deltas.items():
                try:
                    participant = TournamentParticipant.objects.select_for_update().get(
                        tournament=tournament,
                        telegram_user_id=uid,
                    )
                    participant.score += delta
                    participant.games_played += 1

                    # Update wins/losses
                    pr = next((p for p in player_results if p['telegram_user_id'] == uid), {})
                    if pr.get('won'):
                        participant.games_won += 1
                    else:
                        participant.games_lost += 1
                    if pr.get('survived'):
                        participant.survival_count += 1
                    participant.kills += pr.get('kills', 0)

                    participant.save(update_fields=[
                        'score', 'games_played', 'games_won', 'games_lost',
                        'survival_count', 'kills',
                    ])
                except TournamentParticipant.DoesNotExist:
                    logger.warning(f"Participant {uid} not found in tournament #{tournament.id}")

            tournament_game.score_applied = True
            tournament_game.save(update_fields=['score_applied'])

        logger.info(f"Scores applied for TournamentGame #{tournament_game.id}")


class TournamentService:
    """High-level service for Tournament lifecycle management."""

    @classmethod
    def create_tournament(
        cls,
        owner,
        name: str,
        description: str = '',
        max_players: int = 24,
        players_per_game: int = 6,
        total_rounds: int = 3,
        game_template=None,
        scoring_config: Optional[Dict] = None,
    ):
        """Creates a new Tournament in DRAFT status."""
        from apps.tournaments.models import Tournament, TournamentStatus
        from apps.subscriptions.services import EntitlementService, EntitlementLimitExceededError

        try:
            EntitlementService.can_create_tournament(owner)
        except EntitlementLimitExceededError as e:
            raise TournamentValidationError(str(e))

        if max_players < players_per_game:
            raise TournamentValidationError("max_players must be >= players_per_game.")
        if players_per_game < 4:
            raise TournamentValidationError("players_per_game must be at least 4.")
        if total_rounds < 1:
            raise TournamentValidationError("total_rounds must be at least 1.")

        config_data = {}
        if game_template:
            config_data = dict(game_template.get_default_configuration())

        with transaction.atomic():
            tournament = Tournament.objects.create(
                owner=owner,
                name=name,
                description=description,
                status=TournamentStatus.DRAFT,
                max_players=max_players,
                players_per_game=players_per_game,
                total_rounds=total_rounds,
                game_template=game_template,
                configuration_data=config_data,
                scoring_config=scoring_config or {},
            )
            logger.info(f"Tournament '{name}' created by {owner.email}")
            return tournament

    @classmethod
    def open_registration(cls, tournament):
        """Transition tournament from DRAFT to REGISTRATION."""
        from apps.tournaments.models import TournamentStatus
        if tournament.status != TournamentStatus.DRAFT:
            raise TournamentValidationError("Only DRAFT tournaments can be opened for registration.")
        tournament.status = TournamentStatus.REGISTRATION
        tournament.save(update_fields=['status'])
        return tournament

    @classmethod
    def register_participant(
        cls,
        tournament,
        telegram_user_id: int,
        display_name: str,
        username: str = '',
    ):
        """Register a participant in REGISTRATION phase tournament."""
        from apps.tournaments.models import TournamentStatus, TournamentParticipant, ParticipantStatus

        if tournament.status != TournamentStatus.REGISTRATION:
            raise TournamentValidationError("Tournament is not open for registration.")

        active_count = tournament.participants.filter(status=ParticipantStatus.ACTIVE).count()
        if active_count >= tournament.max_players:
            raise TournamentValidationError("Tournament is full. Maximum participant capacity reached.")

        participant, created = TournamentParticipant.objects.get_or_create(
            tournament=tournament,
            telegram_user_id=telegram_user_id,
            defaults={
                'display_name': display_name,
                'username': username or '',
                'status': ParticipantStatus.ACTIVE,
            }
        )
        if not created:
            if participant.status == ParticipantStatus.ACTIVE:
                raise TournamentValidationError("You are already registered in this tournament.")
            # Re-activate if previously withdrawn
            participant.status = ParticipantStatus.ACTIVE
            participant.display_name = display_name
            participant.save(update_fields=['status', 'display_name'])

        logger.info(f"Participant {telegram_user_id} registered in tournament #{tournament.id}")
        return participant

    @classmethod
    def withdraw_participant(cls, tournament, telegram_user_id: int):
        """Withdraw a participant from tournament."""
        from apps.tournaments.models import TournamentStatus, TournamentParticipant, ParticipantStatus

        if tournament.status not in (TournamentStatus.REGISTRATION,):
            raise TournamentValidationError(
                "Participants can only withdraw before the tournament starts."
            )

        try:
            participant = TournamentParticipant.objects.get(
                tournament=tournament,
                telegram_user_id=telegram_user_id,
            )
        except TournamentParticipant.DoesNotExist:
            raise TournamentValidationError("You are not registered in this tournament.")

        participant.status = ParticipantStatus.WITHDRAWN
        participant.save(update_fields=['status'])
        return participant

    @classmethod
    def start_tournament(cls, tournament, bot=None):
        """
        Transition tournament to ACTIVE and create the first round.
        Validates minimum participant count.
        """
        from apps.tournaments.models import TournamentStatus, ParticipantStatus

        if tournament.status != TournamentStatus.REGISTRATION:
            raise TournamentValidationError("Only REGISTRATION tournaments can be started.")

        active_count = tournament.participants.filter(status=ParticipantStatus.ACTIVE).count()
        if active_count < tournament.players_per_game:
            raise TournamentValidationError(
                f"Need at least {tournament.players_per_game} participants to start. "
                f"Current: {active_count}"
            )

        with transaction.atomic():
            tournament.status = TournamentStatus.ACTIVE
            tournament.started_at = timezone.now()
            tournament.current_round = 1
            if bot:
                tournament.bot = bot
            tournament.save(update_fields=['status', 'started_at', 'current_round', 'bot'])

            # Create first round
            cls._create_round(tournament, round_number=1)

        logger.info(f"Tournament '{tournament.name}' started.")
        return tournament

    @classmethod
    def _create_round(cls, tournament, round_number: int):
        """Creates a TournamentRound record."""
        from apps.tournaments.models import TournamentRound, TournamentRoundStatus
        return TournamentRound.objects.create(
            tournament=tournament,
            number=round_number,
            status=TournamentRoundStatus.PENDING,
        )

    @classmethod
    def start_round(cls, tournament, bot):
        """
        Start the current round: group participants, create Game instances,
        link them via TournamentGame.
        """
        from apps.tournaments.models import TournamentRound, TournamentRoundStatus, TournamentGame, ParticipantStatus
        from apps.games.engine.game_service import GameService

        if not tournament.bot and not bot:
            raise TournamentValidationError("A bot must be linked to the tournament to start rounds.")

        current_bot = tournament.bot or bot

        round_obj = TournamentRound.objects.get(
            tournament=tournament,
            number=tournament.current_round,
        )
        if round_obj.status != TournamentRoundStatus.PENDING:
            raise TournamentValidationError("Current round is not in PENDING status.")

        # Get active participants
        active_participants = list(
            tournament.participants.filter(status=ParticipantStatus.ACTIVE)
            .values_list('telegram_user_id', flat=True)
        )

        groups = TournamentGroupingService.group_participants(
            active_participants, tournament.players_per_game
        )

        with transaction.atomic():
            round_obj.status = TournamentRoundStatus.ACTIVE
            round_obj.started_at = timezone.now()
            round_obj.save(update_fields=['status', 'started_at'])

            for i, group in enumerate(groups, start=1):
                # Create a Game for this group
                game = GameService.create_game(current_bot, chat_id=-(tournament.id.int % 10**12))
                # Add participants as players
                for uid in group:
                    participant = tournament.participants.get(telegram_user_id=uid)
                    GameService.join_game(
                        game, uid,
                        username=participant.username,
                        display_name=participant.display_name,
                    )

                TournamentGame.objects.create(
                    round=round_obj,
                    game=game,
                    group_number=i,
                )

        return round_obj

    @classmethod
    def finish_round(cls, tournament):
        """Mark current round as FINISHED. Advance to next round or finish tournament."""
        from apps.tournaments.models import TournamentRound, TournamentRoundStatus, TournamentStatus

        round_obj = TournamentRound.objects.get(
            tournament=tournament,
            number=tournament.current_round,
        )
        round_obj.status = TournamentRoundStatus.FINISHED
        round_obj.finished_at = timezone.now()
        round_obj.save(update_fields=['status', 'finished_at'])

        with transaction.atomic():
            if tournament.current_round >= tournament.total_rounds:
                # All rounds done — finish tournament
                tournament.status = TournamentStatus.FINISHED
                tournament.finished_at = timezone.now()
                tournament.save(update_fields=['status', 'finished_at'])
                logger.info(f"Tournament '{tournament.name}' finished.")
            else:
                # Create next round
                tournament.current_round += 1
                tournament.save(update_fields=['current_round'])
                cls._create_round(tournament, tournament.current_round)

        return tournament

    @classmethod
    def cancel_tournament(cls, tournament):
        """Cancel a tournament at any stage."""
        from apps.tournaments.models import TournamentStatus
        terminal = (TournamentStatus.FINISHED, TournamentStatus.CANCELLED)
        if tournament.status in terminal:
            raise TournamentValidationError("Cannot cancel a finished or already cancelled tournament.")
        tournament.status = TournamentStatus.CANCELLED
        tournament.save(update_fields=['status'])
        return tournament

    @classmethod
    def get_leaderboard(cls, tournament) -> List[Dict]:
        """
        Returns sorted leaderboard.
        Deterministic ordering: score DESC, games_won DESC, survival_count DESC, telegram_user_id ASC.
        """
        from apps.tournaments.models import ParticipantStatus
        participants = tournament.participants.filter(
            status=ParticipantStatus.ACTIVE
        ).order_by('-score', '-games_won', '-survival_count', 'telegram_user_id')

        leaderboard = []
        for rank, p in enumerate(participants, start=1):
            leaderboard.append({
                'rank': rank,
                'telegram_user_id': p.telegram_user_id,
                'display_name': p.display_name or p.username,
                'score': p.score,
                'games_played': p.games_played,
                'games_won': p.games_won,
                'kills': p.kills,
                'survival_count': p.survival_count,
            })
        return leaderboard
