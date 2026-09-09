import os
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
"""
MAFIA BOT FATHER — Shared Bot Game Engine (aiogram 3.x Engine)

Clean separation of concerns:
- Master Father Bot Dispatcher (@MafiasFather_bot): Creation, Tokens, Deployment, Economy.
- Child Game Bot Dispatcher (Game instances): Group Lobby, Night Actions, Voting, Roles, Economy.
"""
import logging
from aiogram import Dispatcher
from bot_runtime.handlers import lobby, night, voting, tournament, economy, admin, father_master, hero, giveaway

logger = logging.getLogger(__name__)


def create_master_dispatcher() -> Dispatcher:
    """Dispatcher specifically for Master Bot Father (@MafiasFather_bot)."""
    dp = Dispatcher()
    dp.include_router(father_master.router)
    return dp


def create_bot_dispatcher() -> Dispatcher:
    """Dispatcher for spawned Child Mafia Game Bot instances."""
    dp = Dispatcher()
    dp.include_router(lobby.router)
    dp.include_router(hero.router)
    dp.include_router(giveaway.router)
    dp.include_router(economy.router)
    dp.include_router(night.router)
    dp.include_router(voting.router)
    dp.include_router(tournament.router)
    dp.include_router(admin.router)
    return dp
