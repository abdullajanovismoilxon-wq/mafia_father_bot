import os
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
"""
MAFIA BOT FATHER — Shared Bot Game Engine (aiogram 3.x Engine)

Clean separation of concerns:
- Master Father Bot Dispatcher (@MafiasFather_bot): Creation, Tokens, Deployment, Economy.
- Child Game Bot Dispatcher (Game instances): Group Lobby, Night Actions, Voting, Roles, Economy.
"""
import logging
from aiogram import BaseMiddleware, Dispatcher
from aiogram.types import Message
from bot_runtime.handlers import lobby, night, voting, tournament, economy, admin, father_master, hero, giveaway

logger = logging.getLogger(__name__)


class CommandAutoDeleteMiddleware(BaseMiddleware):
    """
    Automatically deletes command messages in group/supergroup chats
    to keep the group chat clean.
    """
    async def __call__(self, handler, event, data):
        if isinstance(event, Message):
            if event.chat and event.chat.type in ['group', 'supergroup']:
                text = event.text or event.caption or ""
                trimmed = text.strip().lower()
                is_command = (
                    trimmed.startswith('/') or
                    trimmed.startswith('!') or
                    '@utag' in trimmed or
                    trimmed.startswith('/utag') or
                    trimmed.startswith('!utag') or
                    trimmed == 'utag' or
                    trimmed == '@stop' or
                    trimmed == '!stop'
                )
                if is_command:
                    try:
                        await event.delete()
                    except Exception:
                        pass
        return await handler(event, data)


def create_master_dispatcher() -> Dispatcher:
    """Dispatcher specifically for Master Bot Father (@MafiasFather_bot)."""
    dp = Dispatcher()
    dp.message.outer_middleware(CommandAutoDeleteMiddleware())
    dp.include_router(father_master.router)
    return dp


def create_bot_dispatcher() -> Dispatcher:
    """Dispatcher for spawned Child Mafia Game Bot instances."""
    dp = Dispatcher()
    dp.message.outer_middleware(CommandAutoDeleteMiddleware())
    dp.message.outer_middleware(lobby.GroupUserTrackingMiddleware())
    dp.include_router(lobby.router)
    dp.include_router(hero.router)
    dp.include_router(giveaway.router)
    dp.include_router(economy.router)
    dp.include_router(night.router)
    dp.include_router(voting.router)
    dp.include_router(tournament.router)
    dp.include_router(admin.router)
    return dp

