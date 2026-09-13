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

from django.db import models
from asgiref.sync import sync_to_async
from aiogram import Bot
from apps.bots.models import Bot as BotModel, RuntimeStatus, BotStatus
from bot_runtime.engine import create_master_dispatcher
from bot_runtime.manager import BotRuntimeManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def resume_active_games_on_startup(master_bot: Bot):
    """
    Resumes active in-flight games on bot startup so games seamlessly continue without freezing.
    """
    from apps.games.models import Game, GamePhase
    from bot_runtime.handlers.night import start_night_timer, advance_night_to_day
    from bot_runtime.handlers.voting import auto_close_voting

    try:
        active_games = await sync_to_async(lambda: list(
            Game.objects.filter(
                phase__in=[GamePhase.NIGHT, GamePhase.DAY, GamePhase.DISCUSSION, GamePhase.VOTING]
            ).select_related('bot', 'bot__credential')
        ))()

        for g in active_games:
            try:
                game_bot = BotRuntimeManager.get_bot_for_game(g, master_bot)
                gid = str(g.id)
                if g.phase == GamePhase.NIGHT:
                    logger.info(f"🔄 Resuming NIGHT phase for Game {gid} in Chat {g.chat_id}")
                    start_night_timer(gid, game_bot)
                elif g.phase in [GamePhase.DAY, GamePhase.DISCUSSION]:
                    logger.info(f"🔄 Resuming DAY phase for Game {gid} in Chat {g.chat_id}")
                    asyncio.create_task(advance_night_to_day(g, game_bot))
                elif g.phase == GamePhase.VOTING:
                    logger.info(f"🔄 Resuming VOTING phase for Game {gid} in Chat {g.chat_id}")
                    async def _delayed_close(game_obj, b_obj):
                        await asyncio.sleep(10)
                        await auto_close_voting(game_obj, b_obj)
                    asyncio.create_task(_delayed_close(g, game_bot))
            except Exception as res_err:
                logger.warning(f"Error resuming Game {g.id}: {res_err}")

    except Exception as e:
        logger.warning(f"Error in resume_active_games_on_startup: {e}")


async def periodic_game_watchdog(master_bot: Bot):
    """
    Continuous self-healing watchdog with generous timeouts:
    1. Auto-cancels expired WAITING lobbies (>30 mins old).
    2. Recovers genuinely stuck NIGHT games (>5 mins without progress).
    3. Recovers genuinely stuck DAY / DISCUSSION games (>5 mins without progress).
    4. Recovers genuinely stuck VOTING games (>5 mins without progress).
    """
    from apps.games.models import Game, GamePhase
    from django.utils import timezone
    from datetime import timedelta
    from bot_runtime.handlers.night import advance_night_to_day, ADVANCING_NIGHT_GAMES
    from bot_runtime.handlers.voting import auto_close_voting, CLOSING_VOTING_GAMES, HANGING_VOTES

    while True:
        try:
            now = timezone.now()

            # 1. Cancel expired waiting lobbies (timed out by phase_ends_at or >30 mins old)
            expired_lobbies = await sync_to_async(lambda: list(
                Game.objects.filter(
                    phase=GamePhase.WAITING
                ).filter(
                    (models.Q(phase_ends_at__isnull=False) & models.Q(phase_ends_at__lt=now)) |
                    (models.Q(phase_ends_at__isnull=True) & models.Q(created_at__lt=now - timedelta(minutes=30)))
                ).select_related('bot', 'bot__credential')
            ))()
            for g in expired_lobbies:
                g.phase = GamePhase.CANCELED
                g.status = GamePhase.CANCELED
                await sync_to_async(g.save)(update_fields=['phase', 'status', 'updated_at'])
                logger.info(f"Watchdog auto-cancelled expired lobby {g.id} in chat {g.chat_id}")

            # 2. Recover genuinely stuck NIGHT games (updated_at > 3 mins ago and not currently advancing)
            stuck_night_games = await sync_to_async(lambda: list(
                Game.objects.filter(
                    phase=GamePhase.NIGHT,
                    updated_at__lt=now - timedelta(minutes=3)
                ).select_related('bot', 'bot__credential')
            ))()
            for g in stuck_night_games:
                gid = str(g.id)
                if gid in ADVANCING_NIGHT_GAMES:
                    continue
                logger.warning(f"Watchdog detected stuck NIGHT in game {g.id}. Advancing to Day.")
                try:
                    game_bot = BotRuntimeManager.get_bot_for_game(g, master_bot)
                    await advance_night_to_day(g, game_bot)
                except Exception as ne:
                    logger.exception(f"Watchdog night advance error for game {g.id}: {ne}")

            # 3. Recover genuinely stuck DAY / DISCUSSION games (updated_at > 3 mins ago)
            stuck_day_games = await sync_to_async(lambda: list(
                Game.objects.filter(
                    phase__in=[GamePhase.DAY, GamePhase.DISCUSSION],
                    updated_at__lt=now - timedelta(minutes=3)
                ).select_related('bot', 'bot__credential')
            ))()
            for g in stuck_day_games:
                gid = str(g.id)
                logger.warning(f"Watchdog detected stuck DAY/DISCUSSION in game {g.id}. Advancing to Voting...")
                try:
                    game_bot = BotRuntimeManager.get_bot_for_game(g, master_bot)
                    g.phase = GamePhase.VOTING
                    g.status = GamePhase.VOTING
                    await sync_to_async(g.save)(update_fields=['phase', 'status', 'updated_at'])
                    await auto_close_voting(g, game_bot, force=True)
                except Exception as de:
                    logger.exception(f"Watchdog day advance error for game {g.id}: {de}")

            # 4. Recover genuinely stuck VOTING games (updated_at > 3 mins ago)
            stuck_voting_games = await sync_to_async(lambda: list(
                Game.objects.filter(
                    phase=GamePhase.VOTING,
                    updated_at__lt=now - timedelta(minutes=3)
                ).select_related('bot', 'bot__credential')
            ))()
            for g in stuck_voting_games:
                gid = str(g.id)
                logger.warning(f"Watchdog detected stuck VOTING in game {g.id}. Force closing voting.")
                try:
                    game_bot = BotRuntimeManager.get_bot_for_game(g, master_bot)
                    await auto_close_voting(g, game_bot, force=True)
                except Exception as ve:
                    logger.exception(f"Watchdog voting close error for game {g.id}: {ve}")

        except Exception as e:
            logger.debug(f"Watchdog check error: {e}")
        await asyncio.sleep(10)


async def periodic_bot_sync_task(master_bot: Bot):
    """
    Periodically synchronizes running child bots with the database:
    1. If a bot is deleted or status changed to PAUSED/SUSPENDED/DELETED/ERROR -> stops polling.
    2. If a bot is active in database (status=ACTIVE) and not yet running -> starts polling with cooldown.
    """
    master_bot_id = None
    try:
        me = await master_bot.get_me()
        master_bot_id = me.id
    except Exception as e:
        logger.warning(f"Could not get master bot ID for sync: {e}")

    failed_cooldown: dict[str, float] = {}

    while True:
        try:
            import time
            current_time = time.time()

            db_query = BotModel.objects.filter(status=BotStatus.ACTIVE)
            if master_bot_id:
                db_query = db_query.exclude(telegram_bot_id=master_bot_id)

            active_db_bots = await sync_to_async(lambda: list(db_query))()
            active_db_bot_ids = {str(b.id) for b in active_db_bots}
            running_bot_ids = set(BotRuntimeManager._active_tasks.keys())

            # 1. Stop bots that are no longer active in DB
            for running_id in running_bot_ids:
                if running_id not in active_db_bot_ids:
                    logger.info(f"🛑 Stopping deactivated/paused bot {running_id}...")
                    await BotRuntimeManager.stop_bot_polling(running_id)

            # 2. Start bots that are active in DB but not yet running (respecting 60s cooldown on failure)
            for b in active_db_bots:
                bid = str(b.id)
                task = BotRuntimeManager._active_tasks.get(bid)
                if not task or task.done():
                    last_fail = failed_cooldown.get(bid, 0)
                    if current_time - last_fail < 60:
                        continue  # Wait cooldown before attempting retry

                    logger.info(f"▶️ Starting active child bot @{b.telegram_username} ({bid})...")
                    success = await BotRuntimeManager.start_bot_polling(bid)
                    if not success:
                        failed_cooldown[bid] = current_time

        except Exception as e:
            logger.debug(f"Bot sync error: {e}")

        await asyncio.sleep(10)


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

    # Resume all active games so existing games seamlessly continue from where they left off
    await resume_active_games_on_startup(bot)

    # Start background watchdog & dynamic bot synchronization tasks
    asyncio.create_task(periodic_game_watchdog(bot))
    asyncio.create_task(periodic_bot_sync_task(bot))

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
