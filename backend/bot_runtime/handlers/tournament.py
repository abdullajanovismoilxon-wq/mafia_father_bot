"""
Telegram Tournament Handlers.
Provides basic tournament interaction via Telegram bot commands.
All tournament logic is delegated to TournamentService — no business logic here.
"""
import logging
from aiogram import Router, types, Bot
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from apps.bots.models import Bot as BotModel
from apps.tournaments.models import Tournament, TournamentStatus
from apps.tournaments.services import TournamentService, TournamentValidationError

logger = logging.getLogger(__name__)
router = Router()


async def _get_bot_model_by_token(bot: Bot) -> BotModel:
    """Helper retrieving Bot DB entity by token."""
    raw_token = bot.token
    for b in BotModel.objects.select_related('credential').all():
        if hasattr(b, 'credential') and b.credential.get_token() == raw_token:
            return b
    raise ValueError("Unregistered Bot Instance token.")


def _build_tournament_keyboard(tournament) -> InlineKeyboardMarkup:
    """Build tournament inline keyboard."""
    buttons = [[
        InlineKeyboardButton(
            text="🎯 Join Tournament",
            callback_data=f"tournament:join:{tournament.id}"
        ),
    ], [
        InlineKeyboardButton(
            text="🏆 Leaderboard",
            callback_data=f"tournament:leaderboard:{tournament.id}"
        ),
        InlineKeyboardButton(
            text="📋 Rules",
            callback_data=f"tournament:rules:{tournament.id}"
        ),
    ]]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("create_tournament"))
async def cmd_create_tournament(message: types.Message, bot: Bot):
    """
    /create_tournament <name> — creates a tournament (bot owner command).
    Example: /create_tournament Spring Cup
    """
    if message.chat.type == "private":
        await message.answer("⚠️ Tournament commands work in Group Chats.")
        return

    args = message.text.split(maxsplit=1)
    name = args[1].strip() if len(args) > 1 else "Mafia Tournament"

    try:
        bot_model = await _get_bot_model_by_token(bot)
        tournament = TournamentService.create_tournament(
            owner=bot_model.owner,
            name=name,
            description="",
            max_players=24,
            players_per_game=6,
            total_rounds=3,
        )
        # Open registration immediately
        TournamentService.open_registration(tournament)
        tournament.bot = bot_model
        tournament.save(update_fields=['bot'])

        kb = _build_tournament_keyboard(tournament)
        await message.answer(
            f"🏆 **TOURNAMENT CREATED**\n\n"
            f"**{tournament.name}**\n\n"
            f"📊 Max Players: {tournament.max_players}\n"
            f"🎮 Players/Game: {tournament.players_per_game}\n"
            f"🔄 Rounds: {tournament.total_rounds}\n\n"
            f"Registration is **OPEN**! Click **Join Tournament** to participate.",
            reply_markup=kb,
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.exception("Error creating tournament:")
        await message.answer(f"❌ Error: {str(e)}")


@router.message(Command("tournament"))
async def cmd_tournament_status(message: types.Message, bot: Bot):
    """/tournament — shows the current active tournament status."""
    try:
        bot_model = await _get_bot_model_by_token(bot)
        tournament = Tournament.objects.filter(
            bot=bot_model,
            status__in=[TournamentStatus.REGISTRATION, TournamentStatus.ACTIVE]
        ).first()

        if not tournament:
            await message.answer("📭 No active tournament at the moment.")
            return

        participants_count = tournament.participants.filter(status='ACTIVE').count()
        kb = _build_tournament_keyboard(tournament)

        await message.answer(
            f"🏆 **{tournament.name}**\n\n"
            f"Status: **{tournament.status}**\n"
            f"Participants: **{participants_count}/{tournament.max_players}**\n"
            f"Round: {tournament.current_round}/{tournament.total_rounds}\n",
            reply_markup=kb,
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.exception("Error showing tournament:")
        await message.answer(f"❌ Error: {str(e)}")


@router.message(Command("leaderboard"))
async def cmd_leaderboard(message: types.Message, bot: Bot):
    """/leaderboard — shows the current tournament leaderboard."""
    try:
        bot_model = await _get_bot_model_by_token(bot)
        tournament = Tournament.objects.filter(
            bot=bot_model,
            status__in=[TournamentStatus.ACTIVE, TournamentStatus.FINISHED]
        ).first()

        if not tournament:
            await message.answer("📭 No active tournament.")
            return

        leaderboard = TournamentService.get_leaderboard(tournament)
        if not leaderboard:
            await message.answer("No scores yet. Games haven't started.")
            return

        lines = [f"🏆 **{tournament.name} — LEADERBOARD**\n"]
        medals = ["🥇", "🥈", "🥉"]
        for entry in leaderboard[:10]:
            rank = entry['rank']
            medal = medals[rank - 1] if rank <= 3 else f"{rank}."
            lines.append(
                f"{medal} **{entry['display_name']}** — {entry['score']} pts "
                f"({entry['games_won']}W | {entry['kills']}K | {entry['survival_count']}S)"
            )

        await message.answer("\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        logger.exception("Error showing leaderboard:")
        await message.answer(f"❌ Error: {str(e)}")


@router.callback_query(lambda c: c.data and c.data.startswith("tournament:"))
async def handle_tournament_callback(callback: CallbackQuery, bot: Bot):
    """Handle tournament inline keyboard callbacks."""
    parts = callback.data.split(":")
    action = parts[1]
    tournament_id = parts[2] if len(parts) > 2 else None

    try:
        tournament = Tournament.objects.get(id=tournament_id)
        user = callback.from_user

        if action == "join":
            try:
                TournamentService.register_participant(
                    tournament=tournament,
                    telegram_user_id=user.id,
                    display_name=user.full_name or user.first_name,
                    username=user.username or '',
                )
                count = tournament.participants.filter(status='ACTIVE').count()
                await callback.answer(f"✅ Joined! Participants: {count}/{tournament.max_players}")
            except TournamentValidationError as e:
                await callback.answer(str(e), show_alert=True)

        elif action == "leaderboard":
            leaderboard = TournamentService.get_leaderboard(tournament)
            if not leaderboard:
                await callback.answer("No scores yet!", show_alert=True)
                return
            lines = [f"🏆 {tournament.name}\n"]
            for entry in leaderboard[:5]:
                lines.append(f"{entry['rank']}. {entry['display_name']} — {entry['score']} pts")
            await callback.answer("\n".join(lines), show_alert=True)

        elif action == "rules":
            scoring = tournament.get_default_scoring()
            rules_text = (
                f"📋 Tournament Rules\n\n"
                f"Scoring:\n"
                f"• Participation: +{scoring['participation']}\n"
                f"• Survival: +{scoring['survival']}\n"
                f"• Winning faction: +{scoring['winning_faction']}\n"
                f"• Mafia elimination: +{scoring['mafia_elimination']}\n"
                f"• Final survivor: +{scoring['final_survivor']}\n\n"
                f"Players per game: {tournament.players_per_game}\n"
                f"Total rounds: {tournament.total_rounds}"
            )
            await callback.answer(rules_text, show_alert=True)

    except Tournament.DoesNotExist:
        await callback.answer("Tournament not found.", show_alert=True)
    except Exception as e:
        logger.exception("Error in tournament callback:")
        await callback.answer(f"Error: {str(e)}", show_alert=True)
