"""
MAFIA BOT FATHER — Telegram Master & Multi-Bot Polling Runner
Starts polling for Master Bot Father and all active child bots in DB.
"""
import os
import sys
import asyncio
import logging
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
django.setup()

from asgiref.sync import sync_to_async
from aiogram import Bot
from apps.bots.models import Bot as BotModel, RuntimeStatus, BotStatus
from bot_runtime.engine import create_master_dispatcher
from bot_runtime.manager import BotRuntimeManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def periodic_game_watchdog(master_bot: Bot):
    """
    Continuous self-healing watchdog:
    1. Auto-cancels expired WAITING lobbies.
    2. Auto-advances stranded NIGHT games that exceed timeout.
    3. Auto-closes stranded VOTING games that exceed timeout.
    """
    from apps.games.models import Game, GamePhase
    from django.utils import timezone
    from datetime import timedelta
    from bot_runtime.handlers.night import advance_night_to_day
    from bot_runtime.handlers.voting import auto_close_voting

    while True:
        try:
            now = timezone.now()

            # 1. Cancel expired waiting lobbies
            expired_lobbies = await sync_to_async(lambda: list(
                Game.objects.filter(
                    phase=GamePhase.WAITING,
                    phase_ends_at__isnull=False,
                    phase_ends_at__lt=now
                ).select_related('bot')
            ))()
            for g in expired_lobbies:
                g.phase = GamePhase.CANCELED
                await sync_to_async(g.save)(update_fields=['phase'])
                logger.info(f"Watchdog auto-cancelled expired lobby {g.id} in chat {g.chat_id}")

            # 2. Recover stranded NIGHT games (updated_at > 90s ago)
            stuck_night_games = await sync_to_async(lambda: list(
                Game.objects.filter(
                    phase=GamePhase.NIGHT,
                    updated_at__lt=now - timedelta(seconds=90)
                ).select_related('bot')
            ))()
            for g in stuck_night_games:
                logger.warning(f"Watchdog detected stuck NIGHT in game {g.id}. Advancing to Day.")
                try:
                    await advance_night_to_day(g, master_bot)
                except Exception as ne:
                    logger.exception(f"Watchdog night advance error for game {g.id}: {ne}")

            # 3. Recover stranded VOTING games (updated_at > 75s ago)
            stuck_voting_games = await sync_to_async(lambda: list(
                Game.objects.filter(
                    phase=GamePhase.VOTING,
                    updated_at__lt=now - timedelta(seconds=75)
                ).select_related('bot')
            ))()
            for g in stuck_voting_games:
                logger.warning(f"Watchdog detected stuck VOTING in game {g.id}. Closing voting.")
                try:
                    await auto_close_voting(g, master_bot)
                except Exception as ve:
                    logger.exception(f"Watchdog voting close error for game {g.id}: {ve}")

        except Exception as e:
            logger.debug(f"Watchdog check error: {e}")
        await asyncio.sleep(5)


async def main():
    token = (
        os.environ.get('MASTER_BOT_TOKEN') or
        os.environ.get('TELEGRAM_BOT_TOKEN') or
        os.environ.get('TEST_TELEGRAM_BOT_TOKEN') or
        os.environ.get('BOT_TOKEN') or
        '8741801900:AAHtCUxO2zvG737po1_2mTOEW_hr8lA657g'
    )

    bot = Bot(token=token)
    try:
        bot_info = await bot.get_me()
        logger.info(f"✅ Master Mafia Father Bot connected: @{bot_info.username} ({bot_info.first_name}, ID: {bot_info.id})")
    except Exception as e:
        logger.error(f"❌ Failed to connect with bot token: {e}")
        await bot.session.close()
        return

    dp = create_master_dispatcher()

    # Start background watchdog
    asyncio.create_task(periodic_game_watchdog(bot))

    # Also start polling for any child bots registered in DB
    try:
        child_bots = await sync_to_async(
            lambda: list(BotModel.objects.exclude(telegram_bot_id=bot_info.id).filter(status=BotStatus.ACTIVE))
        )()
        for cb in child_bots:
            logger.info(f"Starting child bot polling for @{cb.telegram_username}...")
            asyncio.create_task(BotRuntimeManager.start_bot_polling(str(cb.id)))
    except Exception as e:
        logger.warning(f"Could not load child bots: {e}")

    logger.info("🚀 Bot Dispatcher is now polling for Telegram updates...")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot runner stopped.")
