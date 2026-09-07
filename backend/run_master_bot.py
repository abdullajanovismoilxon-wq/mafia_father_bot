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

from aiogram import Bot
from apps.bots.models import Bot as BotModel, RuntimeStatus, BotStatus
from bot_runtime.engine import create_master_dispatcher
from bot_runtime.manager import BotRuntimeManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


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

    # Also start polling for any child bots registered in DB
    try:
        from asgiref.sync import sync_to_async
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

async def periodic_lobby_watchdog():
    """Background watchdog ensuring expired waiting lobbies are auto-cancelled precisely."""
    from apps.games.models import Game, GamePhase
    from django.utils import timezone
    from datetime import timedelta
    while True:
        try:
            now = timezone.now()
            expired_games = await sync_to_async(lambda: list(
                Game.objects.filter(
                    phase=GamePhase.WAITING,
                    phase_ends_at__isnull=False,
                    phase_ends_at__lt=now
                ).select_related('bot')
            ))()
            for g in expired_games:
                g.phase = GamePhase.CANCELED
                await sync_to_async(g.save)(update_fields=['phase'])
                logger.info(f"Watchdog auto-cancelled expired lobby {g.id} in chat {g.chat_id}")
        except Exception as e:
            logger.debug(f"Watchdog check error: {e}")
        await asyncio.sleep(5)
