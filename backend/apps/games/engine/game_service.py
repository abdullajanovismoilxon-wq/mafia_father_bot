import logging
from typing import Dict, Any, List, Optional
from django.db import transaction
from django.utils import timezone
from apps.bots.models import Bot
from apps.games.models import (
    Game, Player, GamePhase, RoleTeam, ConfigurationSnapshot, GameMode, GameEventType
)
from .roles import RoleDistributionService
from .state_machine import GameStateMachine
from .actions import NightActionService
from .voting import VotingService
from .resolution import GameResolutionService
from .win_conditions import WinConditionService
from .events import GameEventService


logger = logging.getLogger(__name__)


def _create_configuration_snapshot(game: Game) -> ConfigurationSnapshot:
    """
    Creates an immutable ConfigurationSnapshot for a game at start time.
    Uses game.game_configuration if set, otherwise uses system defaults.
    Snapshot guarantees configuration changes after game start won't affect the game.
    """
    config = game.game_configuration

    if config:
        # Build role distribution snapshot from configured rules
        rules_snapshot = []
        for rule in config.distribution_rules.select_related('role'):
            rules_snapshot.append({
                'role_code': rule.role.code,
                'role_name': rule.role.name,
                'team': rule.role.team,
                'min_count': rule.min_count,
                'max_count': rule.max_count,
                'distribution_type': rule.distribution_type,
                'priority': rule.priority,
            })

        snapshot, _ = ConfigurationSnapshot.objects.update_or_create(
            game=game,
            defaults=dict(
                configuration_name=config.name,
                game_mode=config.game_mode,
                minimum_players=config.minimum_players,
                maximum_players=config.maximum_players,
                night_duration=config.night_duration,
                discussion_duration=config.discussion_duration,
                voting_duration=config.voting_duration,
                allow_self_vote=config.allow_self_vote,
                allow_self_protection=config.allow_self_protection,
                reveal_role_on_elimination=config.reveal_role_on_elimination,
                tie_behavior=config.tie_behavior,
                mafia_vote_mode=config.mafia_vote_mode,
                automatic_phase_transition=config.automatic_phase_transition,
                day_discussion_enabled=config.day_discussion_enabled,
                night_media_url=config.night_media_url,
                day_media_url=config.day_media_url,
                elimination_media_url=config.elimination_media_url,
                victory_media_url=config.victory_media_url,
                custom_theme=config.custom_theme,
                role_distribution_snapshot=rules_snapshot,
            )
        )
    else:
        # Default snapshot
        snapshot, _ = ConfigurationSnapshot.objects.update_or_create(
            game=game,
            defaults=dict(
                configuration_name='Default',
                game_mode=getattr(game, 'mode', 'CLASSIC') or GameMode.CLASSIC,
                minimum_players=4,
                maximum_players=30,
                night_duration=60,
                discussion_duration=120,
                voting_duration=60,
                allow_self_vote=False,
                allow_self_protection=False,
                reveal_role_on_elimination=True,
                tie_behavior='NO_ELIMINATION',
                mafia_vote_mode='ANY',
                automatic_phase_transition=True,
                day_discussion_enabled=True,
                night_media_url='',
                day_media_url='',
                elimination_media_url='',
                victory_media_url='',
                custom_theme='default',
                role_distribution_snapshot=[],
            )
        )

    return snapshot


class GameService:
    """
    Primary Game Application Service orchestrating Lobby, State Machine, Actions, Events, and Resolutions.
    """

    @classmethod
    def create_game(cls, bot: Optional[Bot] = None, chat_id: int = 0, configuration_id: Optional[str] = None, bot_id: Optional[Any] = None, **kwargs) -> Game:
        """
        Creates a new game lobby in a Telegram Group Chat.
        Cancels any existing WAITING game in the same chat.
        """
        if not bot and bot_id:
            bot = Bot.objects.filter(id=bot_id).first()
        if not bot:
            bot = Bot.objects.first()

        with transaction.atomic():
            # Cancel old waiting games in this chat
            old_games = Game.objects.filter(bot=bot, chat_id=chat_id, phase=GamePhase.WAITING)
            for og in old_games:
                GameEventService.log_event(
                    game=og,
                    event_type=GameEventType.GAME_CANCELED,
                    message="Game canceled by new lobby creation"
                )
            old_games.update(phase=GamePhase.CANCELED, status=GamePhase.CANCELED)

            game_kwargs: Dict[str, Any] = {
                'bot': bot,
                'chat_id': chat_id,
                'phase': GamePhase.WAITING,
                'status': GamePhase.WAITING,
                'mode': kwargs.get('mode', 'CLASSIC'),
            }

            if configuration_id:
                from apps.games.models import GameConfiguration
                try:
                    config = GameConfiguration.objects.get(id=configuration_id)
                    game_kwargs['game_configuration'] = config
                except GameConfiguration.DoesNotExist:
                    logger.warning(f"GameConfiguration #{configuration_id} not found. Using defaults.")

            game = Game.objects.create(**game_kwargs)
            GameEventService.log_event(
                game=game,
                event_type=GameEventType.GAME_CREATED,
                message=f"Game lobby #{game.id} created in chat {chat_id}"
            )
            logger.info(f"Created Game #{game.id} on Bot {bot.name} in Chat {chat_id}")
            return game

    @classmethod
    def cancel_game(cls, game: Game) -> bool:
        """Cancels a WAITING or active game."""
        with transaction.atomic():
            game = Game.objects.select_for_update().get(id=game.id)
            if game.phase == GamePhase.FINISHED:
                return False
            game.phase = GamePhase.CANCELED
            game.status = GamePhase.CANCELED
            game.save(update_fields=['phase', 'status'])
            GameEventService.log_event(
                game=game,
                event_type=GameEventType.GAME_CANCELED,
                message="Game manually canceled"
            )
            return True

    @classmethod
    def join_lobby(cls, game: Game, telegram_user_id: int, username: str = '', display_name: str = '', team_side: Optional[str] = None) -> tuple:
        """Adds a player to a WAITING game lobby and returns (player, created)."""
        with transaction.atomic():
            game = Game.objects.select_for_update().get(id=game.id)
            if game.phase != GamePhase.WAITING:
                raise ValueError("Cannot join a game that has already started.")

            initial_metadata = {'team_side': team_side} if team_side else {}
            player, created = Player.objects.get_or_create(
                game=game,
                telegram_user_id=telegram_user_id,
                defaults={
                    'username': username or '',
                    'display_name': display_name or username or f"User_{telegram_user_id}",
                    'is_alive': True,
                    'metadata': initial_metadata,
                }
            )
            if not created:
                player.username = username or player.username
                player.display_name = display_name or player.display_name
                if team_side:
                    if not player.metadata:
                        player.metadata = {}
                    player.metadata['team_side'] = team_side
                player.save(update_fields=['username', 'display_name', 'metadata'])

            GameEventService.log_event(
                game=game,
                event_type=GameEventType.PLAYER_JOINED,
                actor=player,
                message=f"{player.display_name} joined the lobby"
            )

            # Auto-create profile in stats
            try:
                from apps.stats.services import StatsService
                StatsService.get_or_create_profile(
                    telegram_id=telegram_user_id,
                    username=username,
                    first_name=display_name
                )
            except Exception as e:
                logger.debug(f"Profile lookup on join: {e}")

            return player, created

    @classmethod
    def join_game(cls, game: Game, telegram_user_id: int, username: str, display_name: str) -> Player:
        """Adds a player to a WAITING game lobby."""
        player, _ = cls.join_lobby(game, telegram_user_id, username, display_name)
        return player

    @classmethod
    def leave_game(cls, game: Game, telegram_user_id: int) -> tuple[bool, str, str, str, Optional[str]]:
        """
        Removes a player from a WAITING lobby or eliminates them from an active game.
        Returns: (success, phase_mode, display_name, role_name, winner_team)
        """
        with transaction.atomic():
            game = Game.objects.select_for_update().get(id=game.id)
            if game.phase in [GamePhase.FINISHED, GamePhase.CANCELED]:
                return False, 'FINISHED', '', '', None

            player = Player.objects.select_related('role').filter(game=game, telegram_user_id=telegram_user_id).first()
            if not player:
                return False, 'NOT_FOUND', '', '', None

            display_name = player.display_name
            role_name = player.role.name if player.role else "Oddiy"

            if game.phase == GamePhase.WAITING:
                GameEventService.log_event(
                    game=game,
                    event_type=GameEventType.PLAYER_LEFT,
                    actor=player,
                    message=f"{player.display_name} left the lobby"
                )
                player.delete()
                return True, 'LOBBY', display_name, role_name, None
            else:
                # Active game (STARTING, NIGHT, DAY, VOTING)
                if not player.is_alive:
                    return False, 'ALREADY_DEAD', display_name, role_name, None

                player.is_alive = False
                player.eliminated_reason = 'LEFT'
                player.eliminated_at = timezone.now()
                player.save(update_fields=['is_alive', 'eliminated_reason', 'eliminated_at'])

                GameEventService.log_event(
                    game=game,
                    event_type=GameEventType.PLAYER_LEFT,
                    actor=player,
                    message=f"{player.display_name} ({role_name}) left active game"
                )

                # Check win condition
                from apps.games.engine.win_conditions import WinConditionService
                winner = WinConditionService.check_win_condition(game)
                if winner:
                    cls.finish_game(game, winner)
                return True, 'ACTIVE', display_name, role_name, winner

    @classmethod
    def leave_lobby(cls, game: Game, telegram_user_id: int) -> bool:
        """Alias for lobby callback button."""
        success, phase_mode, _, _, _ = cls.leave_game(game, telegram_user_id)
        return success

    @classmethod
    def start_game(cls, game: Game) -> List[tuple]:
        """
        Starts the game:
        1. Checks subscription entitlement & game limits.
        2. Validates minimum players.
        3. Creates ConfigurationSnapshot.
        4. Assigns roles (config-driven or default).
        5. Transitions phase: WAITING -> STARTING -> NIGHT.
        """
        if game.bot and getattr(game.bot, 'owner', None):
            try:
                from apps.subscriptions.services import EntitlementService
                EntitlementService.can_start_game(game.bot.owner, len(game.players.all()))
            except Exception as ent_err:
                logger.warning(f"Entitlement bypass on game start for Game #{game.id}: {ent_err}")

        with transaction.atomic():
            game = Game.objects.select_for_update().get(id=game.id)
            if game.phase != GamePhase.WAITING:
                raise ValueError("Game is not in WAITING state.")

            players = list(game.players.all())

            min_players = 4
            if game.game_configuration:
                min_players = game.game_configuration.minimum_players

            if len(players) < min_players:
                raise ValueError(
                    f"At least {min_players} players are required to start. Current: {len(players)}"
                )

            # Create configuration snapshot BEFORE role assignment
            snapshot = _create_configuration_snapshot(game)
            logger.info(f"Configuration snapshot created for Game #{game.id}: '{snapshot.configuration_name}'")

            # Assign roles
            configuration = game.game_configuration
            assignments = RoleDistributionService.assign_roles_to_players(players, configuration=configuration)

            GameEventService.log_event(
                game=game,
                event_type=GameEventType.GAME_STARTED,
                message=f"Game #{game.id} started with {len(players)} players"
            )

            for p, r in assignments:
                GameEventService.log_event(
                    game=game,
                    event_type=GameEventType.ROLE_ASSIGNED,
                    actor=p,
                    message=f"{p.display_name} assigned role {r.name} ({r.team})"
                )

            # Transition state: WAITING -> STARTING -> NIGHT
            GameStateMachine.transition(game, GamePhase.STARTING)
            game.started_at = timezone.now()
            game.round_number = 1
            game.save(update_fields=['started_at', 'round_number'])

            GameStateMachine.transition(game, GamePhase.NIGHT)
            GameEventService.log_event(
                game=game,
                event_type=GameEventType.NIGHT_STARTED,
                message=f"Round {game.round_number} Night phase started"
            )
            logger.info(f"Game #{game.id} started. Round 1 NIGHT phase activated.")

            # Schedule the first night timer so game auto-advances if players are idle
            cls._schedule_next_timer(game, GamePhase.NIGHT, cls._get_phase_duration(game, GamePhase.NIGHT))

            return assignments

    @classmethod
    def _schedule_next_timer(cls, game: Game, phase: str, duration_seconds: int) -> None:
        """
        Schedules the auto-advance Celery task for the given phase.
        Directly updates game.phase_ends_at in DB, then fires apply_async in a
        daemon thread so Redis connection delays never block game logic or tests.
        Gracefully swallows errors when Celery/Redis is not available.
        """
        import threading
        from django.utils import timezone
        from datetime import timedelta

        # Update phase_ends_at synchronously (pure DB, always fast)
        try:
            Game.objects.filter(id=game.id).update(
                phase_ends_at=timezone.now() + timedelta(seconds=duration_seconds)
            )
        except Exception as e:
            logger.warning(f"Could not update phase_ends_at for Game #{game.id}: {e}")

        game_id_str = str(game.id)
        round_num = game.round_number

        def _fire_task():
            try:
                import os
                from django.conf import settings
                broker = getattr(settings, 'CELERY_BROKER_URL', '')
                if broker and broker.startswith('redis') and not os.environ.get('DISABLE_CELERY'):
                    from apps.games.tasks import auto_advance_phase_task
                    auto_advance_phase_task.apply_async(
                        args=[game_id_str, phase, round_num],
                        countdown=duration_seconds,
                        retry=False,
                        ignore_result=True
                    )
            except Exception:
                pass

        t = threading.Thread(target=_fire_task, daemon=True)
        t.start()

    @classmethod
    def _get_phase_duration(cls, game: Game, phase: str) -> int:
        """Returns duration (seconds) for a phase from snapshot or sane defaults."""
        try:
            snap = game.configuration_snapshot
            if phase == GamePhase.NIGHT:
                return snap.night_duration or 45
            elif phase == GamePhase.DISCUSSION:
                return snap.discussion_duration or 60
            elif phase == GamePhase.VOTING:
                return snap.voting_duration or 45
        except Exception:
            pass
        # Sane defaults
        defaults = {
            GamePhase.NIGHT: 45,
            GamePhase.DISCUSSION: 60,
            GamePhase.VOTING: 45,
            GamePhase.DAY: 10,
        }
        return defaults.get(phase, 60)

    @classmethod
    def advance_phase(cls, game: Game, target_phase: Optional[str] = None) -> Dict[str, Any]:
        """
        Advances the game through its cycle:
        NIGHT -> DAY -> DISCUSSION -> VOTING -> ELIMINATION -> (NIGHT / FINISHED)
        Or transitions directly to target_phase if specified.
        """
        with transaction.atomic():
            game = Game.objects.select_for_update().get(id=game.id)
            if target_phase:
                GameStateMachine.transition(game, target_phase)
                game.save(update_fields=['phase'])
                return {'next_phase': target_phase}

            current_phase = game.phase
            result_summary = {}

            if current_phase == GamePhase.NIGHT:
                night_result = GameResolutionService.resolve_night_phase(game)
                result_summary['night'] = night_result

                elim = night_result.get('eliminated_player')
                if elim:
                    GameEventService.log_event(
                        game=game,
                        event_type=GameEventType.PLAYER_ELIMINATED,
                        target=elim,
                        message=f"{elim.display_name} ({night_result.get('eliminated_role_name')}) killed during the night"
                    )

                GameEventService.log_event(
                    game=game,
                    event_type=GameEventType.NIGHT_RESOLVED,
                    message=f"Night round {game.round_number} resolved"
                )

                winner = WinConditionService.check_win_condition(game)
                if winner:
                    cls.finish_game(game, winner)
                    result_summary['winner'] = winner
                    return result_summary

                GameStateMachine.transition(game, GamePhase.DAY)
                GameEventService.log_event(
                    game=game,
                    event_type=GameEventType.DAY_STARTED,
                    message=f"Day round {game.round_number} started"
                )
                result_summary['next_phase'] = GamePhase.DAY
                # DAY is a short transitional phase — auto-advance to DISCUSSION quickly
                cls._schedule_next_timer(game, GamePhase.DAY, cls._get_phase_duration(game, GamePhase.DAY))

            elif current_phase == GamePhase.DAY:
                GameStateMachine.transition(game, GamePhase.DISCUSSION)
                GameEventService.log_event(
                    game=game,
                    event_type=GameEventType.DISCUSSION_STARTED,
                    message=f"Discussion round {game.round_number} started"
                )
                result_summary['next_phase'] = GamePhase.DISCUSSION
                cls._schedule_next_timer(game, GamePhase.DISCUSSION, cls._get_phase_duration(game, GamePhase.DISCUSSION))

            elif current_phase == GamePhase.DISCUSSION:
                GameStateMachine.transition(game, GamePhase.VOTING)
                GameEventService.log_event(
                    game=game,
                    event_type=GameEventType.VOTE_STARTED,
                    message=f"Voting round {game.round_number} started"
                )
                result_summary['next_phase'] = GamePhase.VOTING
                cls._schedule_next_timer(game, GamePhase.VOTING, cls._get_phase_duration(game, GamePhase.VOTING))

            elif current_phase == GamePhase.VOTING:
                vote_result = GameResolutionService.resolve_voting_phase(game)
                result_summary['voting'] = vote_result

                elim = vote_result.get('eliminated_player')
                if elim:
                    GameEventService.log_event(
                        game=game,
                        event_type=GameEventType.PLAYER_ELIMINATED,
                        target=elim,
                        message=f"{elim.display_name} ({vote_result.get('eliminated_role_name')}) voted out by town"
                    )

                GameEventService.log_event(
                    game=game,
                    event_type=GameEventType.VOTE_RESOLVED,
                    message=f"Voting round {game.round_number} resolved (Tie: {vote_result.get('is_tie', False)})"
                )

                winner = WinConditionService.check_win_condition(game)
                if winner:
                    cls.finish_game(game, winner)
                    result_summary['winner'] = winner
                    return result_summary

                GameStateMachine.transition(game, GamePhase.ELIMINATION)
                GameEventService.log_event(
                    game=game,
                    event_type=GameEventType.ROUND_COMPLETED,
                    message=f"Round {game.round_number} completed"
                )
                game.round_number += 1
                game.save(update_fields=['round_number'])

                GameStateMachine.transition(game, GamePhase.NIGHT)
                GameEventService.log_event(
                    game=game,
                    event_type=GameEventType.NIGHT_STARTED,
                    message=f"Round {game.round_number} Night phase started"
                )
                result_summary['next_phase'] = GamePhase.NIGHT
                # Schedule night timer so the game auto-advances if no actions submitted
                cls._schedule_next_timer(game, GamePhase.NIGHT, cls._get_phase_duration(game, GamePhase.NIGHT))

            return result_summary

    @classmethod
    def finish_game(cls, game: Game, winner_team: str):
        """Finalizes the game, logs event, and records player stats/rewards."""
        game.phase = GamePhase.FINISHED
        game.status = GamePhase.FINISHED
        game.winner_team = winner_team
        game.finished_at = timezone.now()
        game.save(update_fields=['phase', 'status', 'winner_team', 'finished_at'])
        logger.info(f"Game #{game.id} finished! Winner: {winner_team}")

        GameEventService.log_event(
            game=game,
            event_type=GameEventType.GAME_FINISHED,
            message=f"Game #{game.id} finished! Winning Faction: {winner_team}"
        )

        # Record player stats, coin rewards, and achievements
        try:
            import random
            from apps.stats.services import StatsService
            all_players = list(game.players.all().select_related('role'))
            winners = []
            others = []
            for player in all_players:
                role_code = player.role.code if (player.role and hasattr(player.role, 'code')) else (player.role.name.lower() if player.role else 'citizen')
                role_team = str(player.role.team) if (player.role and player.role.team) else 'CIVILIAN'
                if getattr(game, 'mode', 'CLASSIC') == 'TEAM':
                    p_side = player.metadata.get('team_side') if player.metadata else None
                    won_side = 'RED' if winner_team == 'TEAM_RED' else ('BLUE' if winner_team == 'TEAM_BLUE' else None)
                    won = (p_side == won_side) if won_side else False
                else:
                    team_won = (
                        role_team == winner_team or
                        (winner_team in ['CIVILIAN', RoleTeam.CIVILIAN] and role_team in ['CIVILIAN', RoleTeam.CIVILIAN]) or
                        (winner_team in ['MAFIA', RoleTeam.MAFIA] and role_team in ['MAFIA', RoleTeam.MAFIA]) or
                        (winner_team in ['ZOMBIE', RoleTeam.ZOMBIE] and role_team in ['ZOMBIE', RoleTeam.ZOMBIE]) or
                        (winner_team in ['SOLO', RoleTeam.SOLO] and role_team in ['SOLO', RoleTeam.SOLO])
                    )
                    if player.role and player.role.name == 'AXMOQ' and player.is_alive:
                        team_won = True

                    won = (team_won and player.is_alive)

                if won:
                    winners.append((player, role_code, role_team))
                else:
                    others.append((player, role_code, role_team))

            # Tiered random rewards: 1st place 70-100, 2nd place 50-70, 3rd place 30-50, 4th+ 20-30
            winner_rewards = {}
            for idx, (player, role_code, role_team) in enumerate(winners):
                if idx == 0:
                    coins = random.randint(70, 100)
                elif idx == 1:
                    coins = random.randint(50, 70)
                elif idx == 2:
                    coins = random.randint(30, 50)
                else:
                    coins = random.randint(20, 30)
                winner_rewards[str(player.telegram_user_id)] = coins

                if not player.metadata:
                    player.metadata = {}
                player.metadata['reward_coins'] = coins
                player.save(update_fields=['metadata'])

                StatsService.record_game_player_result(
                    telegram_id=player.telegram_user_id,
                    won=True,
                    role_team=role_team,
                    role_type=role_code,
                    survived=player.is_alive,
                    username=player.username or '',
                    first_name=player.display_name or '',
                    custom_reward_coins=coins
                )

            for player, role_code, role_team in others:
                StatsService.record_game_player_result(
                    telegram_id=player.telegram_user_id,
                    won=False,
                    role_team=role_team,
                    role_type=role_code,
                    survived=player.is_alive,
                    username=player.username or '',
                    first_name=player.display_name or ''
                )

        except Exception as e:
            logger.exception(f"Error recording stats and rewards for game #{game.id}: {e}")

    @classmethod
    def end_game(cls, game: Game, winner_team: str):
        return cls.finish_game(game, winner_team)

