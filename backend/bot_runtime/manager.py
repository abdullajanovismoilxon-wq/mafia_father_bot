"""
Bot Runtime Manager Abstraction
Manages lifecycle (start, stop, polling execution) of dynamic Telegram bot instances.
Uses a single shared Dispatcher for child bots to avoid aiogram 3.x router re-attachment errors.
"""
import logging
import asyncio
from typing import Dict, Optional
from aiogram import Bot, Dispatcher
from asgiref.sync import sync_to_async
from apps.bots.models import Bot as BotModel, RuntimeStatus

logger = logging.getLogger(__name__)


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
    async def start_bot_polling(cls, bot_id: str) -> bool:
        """Starts polling loop for a bot instance in background task."""
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

            # Stop existing instance if running
            await cls.stop_bot_polling(bot_id)

            bot = Bot(token=raw_token)
            dp = cls.get_child_dispatcher()

            async def _polling_task():
                try:
                    bot_info = await bot.get_me()
                    logger.info(f"✅ Child bot @{bot_info.username} (ID: {bot_info.id}) polling loop started.")

                    # Register Telegram UI Bot Commands matching Private & Group scopes
                    try:
                        from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats
                        
                        # 1. PM commands: Strictly 3 (/start, /profile, /roles)
                        pm_commands = [
                            BotCommand(command="start", description="Botni ishga tushirish"),
                            BotCommand(command="profile", description="Shaxsiy profil va do'kon"),
                            BotCommand(command="roles", description="Rollar haqida ma'lumot"),
                        ]
                        await bot.set_my_commands(pm_commands, scope=BotCommandScopeAllPrivateChats())

                        # 2. Group commands (clean menu with leave, geroyinfo, game commands, utag)
                        group_commands = [
                            BotCommand(command="game", description="O'yin yaratish"),
                            BotCommand(command="start_game", description="O'yinni boshlash"),
                            BotCommand(command="leave", description="O'yindan chiqish"),
                            BotCommand(command="utag", description="Guruh a'zolarini chaqirish"),
                            BotCommand(command="stop_tag", description="Chaqirishni to'xtatish"),
                            BotCommand(command="geroyinfo", description="Geroy ma'lumotlari"),
                            BotCommand(command="roles", description="Rollar haqida ma'lumot"),
                            BotCommand(command="stop", description="O'yinni to'xtatish"),
                        ]
                        await bot.set_my_commands(group_commands, scope=BotCommandScopeAllGroupChats())
                    except Exception as cmd_err:
                        logger.warning(f"Could not set commands for @{bot_info.username}: {cmd_err}")

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
                BotModel.objects.filter(id=bot_id).update(runtime_status=RuntimeStatus.RUNNING)

            await sync_to_async(_mark_running)()
            return True

        except Exception as e:
            logger.exception(f"Failed to start bot instance {bot_id}: {e}")
            return False

    @classmethod
    async def stop_bot_polling(cls, bot_id: str) -> bool:
        """Gracefully cancels polling loop task for a bot instance."""
        try:
            task = cls._active_tasks.pop(str(bot_id), None)
            if task and not task.done():
                task.cancel()

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

            def _mark_offline():
                BotModel.objects.filter(id=bot_id).update(runtime_status=RuntimeStatus.OFFLINE)

            await sync_to_async(_mark_offline)()
            logger.info(f"Bot instance {bot_id} stopped.")
            return True
        except Exception as e:
            logger.exception(f"Error stopping bot {bot_id}: {e}")
            return False
