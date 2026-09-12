"""
Bot Runtime Manager Abstraction
Manages lifecycle (start, stop, polling execution) of dynamic Telegram bot instances.
Uses a single shared Dispatcher for child bots to avoid aiogram 3.x router re-attachment errors.
Provides resilient, concurrent safe_send_message and safe_send_batch utilities.
"""
import logging
import asyncio
from typing import Dict, Optional, Any, List, Tuple
from aiogram import Bot, Dispatcher, types
from aiogram.exceptions import TelegramRetryAfter, TelegramForbiddenError, TelegramBadRequest, TelegramAPIError
from asgiref.sync import sync_to_async
from apps.bots.models import Bot as BotModel, RuntimeStatus, BotStatus

logger = logging.getLogger(__name__)


async def safe_send_message(
    bot: Bot,
    chat_id: int,
    text: str,
    reply_markup: Optional[Any] = None,
    parse_mode: Optional[str] = "HTML",
    disable_web_page_preview: bool = True,
    max_retries: int = 2
) -> Optional[types.Message]:
    """
    Resilient message sender:
    - Retries automatically on TelegramRetryAfter (FloodWait).
    - Silently handles user blocks (TelegramForbiddenError) and deleted chats (TelegramBadRequest).
    - Prevents single-user errors from crashing or delaying game loops.
    """
    if not bot or not chat_id:
        return None

    for attempt in range(max_retries + 1):
        try:
            return await bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                disable_web_page_preview=disable_web_page_preview
            )
        except TelegramRetryAfter as flood:
            wait_time = max(1, int(flood.retry_after) + 1)
            logger.warning(f"Telegram flood limit for chat {chat_id}: sleeping {wait_time}s (attempt {attempt+1}/{max_retries+1})")
            await asyncio.sleep(wait_time)
        except (TelegramForbiddenError, TelegramBadRequest) as ignorable:
            logger.debug(f"Ignorable Telegram error sending to {chat_id}: {ignorable}")
            return None
        except Exception as e:
            logger.warning(f"Error sending message to {chat_id} (attempt {attempt+1}): {e}")
            if attempt < max_retries:
                await asyncio.sleep(0.5)
            else:
                return None
    return None


async def safe_send_batch(
    bot: Bot,
    items: List[Tuple[int, str, Optional[Any], Optional[str]]],
    max_concurrency: int = 10
) -> List[Optional[types.Message]]:
    """
    Sends messages to multiple users concurrently using an asyncio Semaphore.
    items: List of (chat_id, text, reply_markup, parse_mode)
    """
    sem = asyncio.Semaphore(max_concurrency)

    async def _send_one(chat_id: int, text: str, reply_markup: Optional[Any], parse_mode: Optional[str]):
        async with sem:
            return await safe_send_message(
                bot=bot,
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )

    tasks = [
        _send_one(
            chat_id=item[0],
            text=item[1],
            reply_markup=item[2] if len(item) > 2 else None,
            parse_mode=item[3] if len(item) > 3 else "HTML"
        )
        for item in items
    ]
    return await asyncio.gather(*tasks, return_exceptions=True)


class BotRuntimeManager:
    """Manager managing runtime polling loops for active bot instances."""

    _active_tasks: Dict[str, asyncio.Task] = {}
    _active_bots: Dict[str, Bot] = {}
    _child_dp: Optional[Dispatcher] = None

    @classmethod
    def get_child_dispatcher(cls) -> Dispatcher:
        """Returns lazy singleton child bot Dispatcher."""
        if cls._child_dp is None:
            from bot_runtime.engine import create_bot_dispatcher
            cls._child_dp = create_bot_dispatcher()
        return cls._child_dp

    @classmethod
    def get_bot(cls, bot_id: str) -> Optional[Bot]:
        """Returns the active Bot instance for a bot ID, or retrieves/creates one if credentials exist."""
        bot_id_str = str(bot_id)
        if bot_id_str in cls._active_bots:
            return cls._active_bots[bot_id_str]
        try:
            bot_obj = BotModel.objects.select_related('credential').filter(id=bot_id).first()
            if bot_obj and hasattr(bot_obj, 'credential'):
                raw_token = bot_obj.credential.get_token()
                if raw_token:
                    bot = Bot(token=raw_token)
                    cls._active_bots[bot_id_str] = bot
                    return bot
        except Exception as e:
            logger.warning(f"Could not retrieve bot for {bot_id}: {e}")
        return None

    @classmethod
    def get_bot_for_game(cls, game: Any, fallback_bot: Optional[Bot] = None) -> Bot:
        """Resolves the exact Telegram Bot instance configured for this game."""
        try:
            bot_id = getattr(game, 'bot_id', None)
            if bot_id:
                resolved = cls.get_bot(str(bot_id))
                if resolved:
                    return resolved
        except Exception as e:
            logger.warning(f"Error resolving bot for game: {e}")
        return fallback_bot

    @classmethod
    async def start_bot_polling(cls, bot_id: str) -> bool:
        """Starts polling loop for a bot instance in background task with conflict-free lifecycle."""
        try:
            def _get_bot_data():
                bot_obj = BotModel.objects.select_related('credential').filter(id=bot_id).first()
                if not bot_obj or not hasattr(bot_obj, 'credential'):
                    return None, None, None
                return bot_obj.id, bot_obj.telegram_username, bot_obj.credential.get_token()

            obj_id, username, raw_token = await sync_to_async(_get_bot_data)()

            if not raw_token:
                logger.error(f"Cannot start bot {bot_id}: Token decryption failed or missing credential.")
                return False

            # Stop existing instance if running (without marking OFFLINE in DB)
            await cls.stop_bot_polling(bot_id, mark_db=False)

            bot = Bot(token=raw_token)
            dp = cls.get_child_dispatcher()

            async def _polling_task():
                try:
                    bot_info = await bot.get_me()
                    logger.info(f"✅ Child bot @{bot_info.username} (ID: {bot_info.id}) polling loop started.")

                    # Register Telegram UI Bot Commands matching Private & Group scopes
                    try:
                        from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats
                        
                        pm_commands = [
                            BotCommand(command="start", description="Botni ishga tushirish"),
                            BotCommand(command="profile", description="Shaxsiy profil va do'kon"),
                            BotCommand(command="roles", description="Rollar haqida ma'lumot"),
                        ]
                        await bot.set_my_commands(pm_commands, scope=BotCommandScopeAllPrivateChats())

                        group_commands = [
                            BotCommand(command="game", description="O'yin yaratish"),
                            BotCommand(command="team", description="Jamoaviy o'yin yaratish (Qizil vs Ko'k)"),
                            BotCommand(command="start_game", description="O'yinni boshlash"),
                            BotCommand(command="leave", description="O'yindan chiqish"),
                            BotCommand(command="changegive", description="Guruhga olmos ulashish 💎"),
                            BotCommand(command="changemoney", description="Guruhga dollar ulashish 💶"),
                            BotCommand(command="utag", description="Guruh a'zolarini chaqirish"),
                            BotCommand(command="stop_tag", description="Chaqirishni to'xtatish"),
                            BotCommand(command="geroyinfo", description="Geroy ma'lumotlari"),
                            BotCommand(command="stop", description="O'yinni to'xtatish"),
                        ]
                        await bot.set_my_commands(group_commands, scope=BotCommandScopeAllGroupChats())
                    except Exception as cmd_err:
                        logger.warning(f"Could not set commands for @{bot_info.username}: {cmd_err}")

                    # Sync bot_id and telegram_username to DB
                    def _update_bot_info():
                        BotModel.objects.filter(id=bot_id).update(
                            telegram_bot_id=bot_info.id,
                            telegram_username=bot_info.username,
                            status=BotStatus.ACTIVE,
                            runtime_status=RuntimeStatus.RUNNING
                        )
                    await sync_to_async(_update_bot_info)()

                    # Delete any previous webhook
                    try:
                        await bot.delete_webhook(drop_pending_updates=False)
                    except Exception:
                        pass

                    offset = None
                    allowed = ["message", "callback_query", "chat_member", "my_chat_member", "poll_answer"]

                    while True:
                        try:
                            updates = await bot.get_updates(
                                offset=offset,
                                timeout=20,
                                allowed_updates=allowed
                            )
                            for update in updates:
                                offset = update.update_id + 1
                                asyncio.create_task(dp.feed_update(bot, update))
                        except asyncio.CancelledError:
                            break
                        except Exception as loop_err:
                            logger.warning(f"Update fetch error for @{bot_info.username}: {loop_err}")
                            await asyncio.sleep(2)

                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"❌ Child bot @{username} polling stopped with error: {e}")
                finally:
                    try:
                        await bot.session.close()
                    except Exception:
                        pass

            task = asyncio.create_task(_polling_task())
            cls._active_tasks[str(bot_id)] = task
            cls._active_bots[str(bot_id)] = bot

            def _mark_running():
                BotModel.objects.filter(id=bot_id).update(status=BotStatus.ACTIVE, runtime_status=RuntimeStatus.RUNNING)

            await sync_to_async(_mark_running)()
            return True

        except Exception as e:
            logger.exception(f"Failed to start bot instance {bot_id}: {e}")
            return False

    @classmethod
    async def stop_bot_polling(cls, bot_id: str, mark_db: bool = True) -> bool:
        """Gracefully cancels polling loop task for a bot instance and awaits termination."""
        try:
            task = cls._active_tasks.pop(str(bot_id), None)
            if task and not task.done():
                task.cancel()
                try:
                    await asyncio.wait_for(asyncio.shield(task), timeout=2.0)
                except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
                    pass

            bot = cls._active_bots.pop(str(bot_id), None)
            if bot:
                try:
                    await bot.delete_webhook(drop_pending_updates=False)
                except Exception:
                    pass
                try:
                    await bot.session.close()
                except Exception:
                    pass

            if mark_db:
                def _mark_offline():
                    BotModel.objects.filter(id=bot_id).update(status=BotStatus.PAUSED, runtime_status=RuntimeStatus.OFFLINE)
                await sync_to_async(_mark_offline)()

            logger.info(f"Bot instance {bot_id} stopped.")
            return True
        except Exception as e:
            logger.exception(f"Error stopping bot {bot_id}: {e}")
            return False
