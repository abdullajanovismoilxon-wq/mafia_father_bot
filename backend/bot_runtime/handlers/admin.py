"""
MAFIA BOT FATHER — Telegram Admin Commands Handler
RBAC protected commands for platform administrators and platform owner (@ismoilo9).
"""
import logging
from aiogram import Router, types
from aiogram.filters import Command
from asgiref.sync import sync_to_async
from apps.users.models import User, UserRole
from apps.games.models import Game, GamePhase
from apps.bots.models import Bot as BotModel
from apps.stats.models import PlayerProfile

logger = logging.getLogger(__name__)
router = Router(name="admin_router")


async def _is_admin_user(telegram_id: int) -> bool:
    """Verifies whether Telegram user has administrator or platform owner privileges."""
    profile = await sync_to_async(
        lambda: PlayerProfile.objects.filter(telegram_id=telegram_id).select_related('user').first()
    )()
    if not profile:
        return False
    if profile.is_platform_owner:
        return True
    if profile.user and profile.user.is_admin_or_staff:
        return True
    return False


@router.message(Command("admin"))
async def cmd_admin_overview(message: types.Message):
    """Admin summary command."""
    if not await _is_admin_user(message.from_user.id):
        await message.reply("⛔️ **Kirish taqiqlangan.** Bu buyruq faqat platforma maʼmurlari uchun.", parse_mode="Markdown")
        return

    active_games = await sync_to_async(
        lambda: Game.objects.filter(phase__in=[GamePhase.STARTING, GamePhase.NIGHT, GamePhase.DAY, GamePhase.DISCUSSION, GamePhase.VOTING]).count()
    )()
    total_bots = await sync_to_async(lambda: BotModel.objects.exclude(status='DELETED').count())()
    total_players = await sync_to_async(lambda: PlayerProfile.objects.count())()

    text = (
        "🛡 **MAFIA BOT FATHER — ADMIN BOSHQARUV MARKAZI**\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"🎮 **Faol oʻyinlar:** {active_games} ta\n"
        f"🤖 **Barcha botlar:** {total_bots} ta\n"
        f"👥 **Jami oʻyinchilar:** {total_players} ta\n\n"
        "📌 **Boshqaruv buyruqlari:**\n"
        "• `/admin_games` — Jonli oʻyinlar monitoringi\n"
        "• `/admin_bots` — Bot flotini koʻrish"
    )
    await message.answer(text, parse_mode="Markdown")


@router.message(Command("admin_games"))
async def cmd_admin_games(message: types.Message):
    """Live games monitor for admin."""
    if not await _is_admin_user(message.from_user.id):
        await message.reply("⛔️ Kirish taqiqlangan.", parse_mode="Markdown")
        return

    active_games = await sync_to_async(
        lambda: list(Game.objects.filter(
            phase__in=[GamePhase.STARTING, GamePhase.NIGHT, GamePhase.DAY, GamePhase.DISCUSSION, GamePhase.VOTING]
        ).select_related('bot').prefetch_related('players')[:10])
    )()

    if not active_games:
        await message.answer("🎮 Hozirda faol oʻyinlar yoʻq.")
        return

    lines = ["🎮 **JONLI OʻYINLAR ROʻYXATI:**\n"]
    for g in active_games:
        alive_count = len([p for p in g.players.all() if p.is_alive])
        lines.append(
            f"• **Game #{g.id}** ({g.bot.name})\n"
            f"  Bosqich: {g.phase} | Raund: {g.round_number} | Tiriklar: {alive_count}/{g.players.count()}"
        )

    await message.answer("\n".join(lines), parse_mode="Markdown")


@router.message(Command("admin_bots"))
async def cmd_admin_bots(message: types.Message):
    """Bot fleet summary for admin."""
    if not await _is_admin_user(message.from_user.id):
        await message.reply("⛔️ Kirish taqiqlangan.", parse_mode="Markdown")
        return

    bots = await sync_to_async(
        lambda: list(BotModel.objects.exclude(status='DELETED').select_related('owner')[:15])
    )()

    lines = ["🤖 **BOT FLOTI HOLATI:**\n"]
    for b in bots:
        status_icon = "🟢" if b.status == 'ACTIVE' else "🟡"
        owner_name = b.owner.email if b.owner else "System"
        lines.append(f"{status_icon} **{b.name}** (@{b.telegram_username}) — Egasi: {owner_name}")

    await message.answer("\n".join(lines), parse_mode="Markdown")
