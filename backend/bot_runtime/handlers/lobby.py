"""
MAFIA BOT FATHER — Telegram Game Lobby Handlers
Aligned with Telegram Mafia Bot UI Screenshots:
- PM /start menu with official Mafia bot greeting and buttons.
- Group /game lobby with live registered player names and '➕ Qo'shilish' button.
- Registered Telegram group commands.
- Deep-link join handling and role delivery for all 38 roles.
"""
import os
import asyncio
import html
import random
from datetime import timedelta
from typing import Optional, Dict, List, Any, Set, Tuple
import logging
from aiogram import Router, types, Bot, F, BaseMiddleware
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest, TelegramForbiddenError, TelegramAPIError
from asgiref.sync import sync_to_async
from django.utils import timezone
from django.conf import settings
from django.db.models import Q
from apps.bots.models import Bot as BotModel
from apps.games.models import Game, Player, GamePhase, RoleTeam
from apps.games.engine.game_service import GameService
from apps.games.engine.state_machine import InvalidStateTransitionError
from apps.stats.services import StatsService
from apps.superadmin.services import TextService, SettingService
from bot_runtime.keyboards.inline import (
    build_child_start_keyboard,
    build_group_lobby_keyboard,
    build_back_to_group_keyboard,
    build_night_target_keyboard,
    build_komissar_action_keyboard,
    build_bot_pm_keyboard,
    build_konchi_mines_keyboard,
    build_joker_boxes_setup_keyboard,
)

logger = logging.getLogger(__name__)
router = Router(name="lobby_router")

TIER_RANKS = {
    'STANDARD': 1,
    'SUPER': 2,
    'MEGA': 3,
}

def _check_bot_tier_access(bot_type: str, required_tier: str) -> bool:
    """Returns True if bot_type tier meets or exceeds required_tier."""
    return TIER_RANKS.get(str(bot_type).upper(), 1) >= TIER_RANKS.get(str(required_tier).upper(), 1)


def is_targeted_at_this_bot(message: types.Message, bot_username: str) -> bool:
    """Returns False if message command explicitly mentions another bot (@other_bot)."""
    if not message.text or not message.text.startswith('/'):
        return True
    first_token = message.text.split()[0]
    if '@' in first_token:
        target = first_token.split('@')[1].strip().lower()
        if target != bot_username.lower():
            return False
    return True


LOBBY_TIMERS: dict = {}

async def check_user_group_permission(bot: Bot, chat_id: int, user_id: int, required_level: str = 'ADMINS') -> tuple[bool, str]:
    """
    Checks if user meets the required permission in the Telegram group.
    Uses bot.get_chat_administrators for 100% reliable real-time admin detection.
    required_level:
      - 'ALL': anyone can execute
      - 'ADMINS': group admins or group creator (owner)
      - 'OWNER': only group creator (owner)
    """
    if required_level == 'ALL':
        return True, ""

    try:
        admins = await bot.get_chat_administrators(chat_id=chat_id)
        creator = next((m for m in admins if m.status == 'creator'), None)
        creator_id = creator.user.id if creator else None
        admin_ids = {m.user.id for m in admins}

        if required_level == 'OWNER':
            if creator_id and user_id == creator_id:
                return True, ""
            return False, "⚠️ Ushbu buyruqni faqat <b>guruh egasi (Creator)</b> bajara oladi!"

        if required_level == 'ADMINS':
            if user_id in admin_ids or (creator_id and user_id == creator_id):
                return True, ""
            return False, "⚠️ Ushbu buyruqni faqat <b>guruh adminlari yoki guruh egasi</b> bajara oladi!"

        return True, ""
    except Exception as e:
        logger.warning(f"get_chat_administrators error for user {user_id} in {chat_id}: {e}")
        try:
            member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
            if required_level == 'OWNER':
                if member.status == 'creator':
                    return True, ""
                return False, "⚠️ Ushbu buyruqni faqat <b>guruh egasi (Creator)</b> bajara oladi!"
            if required_level == 'ADMINS':
                if member.status in ['creator', 'administrator']:
                    return True, ""
                return False, "⚠️ Ushbu buyruqni faqat <b>guruh adminlari yoki guruh egasi</b> bajara oladi!"
        except Exception as m_err:
            logger.warning(f"get_chat_member error for user {user_id} in {chat_id}: {m_err}")
            return False, "⚠️ Ushbu buyruqni faqat <b>guruh adminlari yoki guruh egasi</b> bajara oladi!"


async def sync_group_info(bot: Bot, chat: types.Chat, bot_record: BotModel):
    """Records/updates active group and owner information in real-time."""
    if not chat or chat.type not in ["group", "supergroup"] or not bot_record:
        return
    try:
        owner_id = None
        owner_name = ""
        owner_username = ""
        try:
            admins = await bot.get_chat_administrators(chat_id=chat.id)
            creator = next((m for m in admins if m.status == 'creator'), None)
            if creator:
                owner_id = creator.user.id
                owner_name = creator.user.full_name or creator.user.first_name
                owner_username = creator.user.username or ""
        except Exception:
            pass

        import secrets
        from apps.bots.models import BotGroup
        from apps.games.models import Game
        
        def _db_save():
            total_games = Game.objects.filter(chat_id=chat.id).count()
            bg = BotGroup.objects.filter(chat_id=chat.id).first()
            if not bg:
                bg = BotGroup.objects.create(
                    bot=bot_record,
                    chat_id=chat.id,
                    title=chat.title or 'Telegram Guruh',
                    username=chat.username or '',
                    owner_telegram_id=owner_id,
                    owner_name=owner_name,
                    owner_username=owner_username,
                    total_games_played=total_games,
                    is_active=True,
                    cabinet_login=f"guruh_{abs(chat.id)}",
                    cabinet_password=f"mafia{secrets.randbelow(900000) + 100000}",
                )
            else:
                bg.title = chat.title or bg.title
                bg.username = chat.username or bg.username
                if bot_record:
                    bg.bot = bot_record
                if owner_id:
                    bg.owner_telegram_id = owner_id
                    bg.owner_name = owner_name or bg.owner_name
                    bg.owner_username = owner_username or bg.owner_username
                bg.total_games_played = total_games
                bg.is_active = True
                if not bg.cabinet_login:
                    bg.cabinet_login = f"guruh_{abs(chat.id)}"
                if not bg.cabinet_password:
                    bg.cabinet_password = f"mafia{secrets.randbelow(900000) + 100000}"
                bg.save()
        await sync_to_async(_db_save)()
    except Exception as e:
        logger.debug(f"Error syncing group info: {e}")


async def _run_lobby_timer(game_id: str, chat_id: int, bot: Bot, timeout: int = 300):
    """Waits timeout seconds (configured in SuperAdmin); resets if /game is called again; cancels game if /start_game was not called."""
    try:
        if timeout <= 0:
            timeout = 300

        while True:
            game = await sync_to_async(
                lambda: Game.objects.filter(id=game_id, phase=GamePhase.WAITING).first()
            )()
            if not game:
                break

            now = timezone.now()
            if not game.phase_ends_at:
                game.phase_ends_at = now + timedelta(seconds=timeout)
                await sync_to_async(game.save)(update_fields=['phase_ends_at'])

            remaining = (game.phase_ends_at - now).total_seconds()
            if remaining > 0.5:
                # Sleep in short chunks to remain responsive to resets/cancellations
                await asyncio.sleep(min(remaining, 3.0))
                continue

            # Timeout reached! Cancel lobby and delete message
            game.phase = GamePhase.CANCELED
            await sync_to_async(game.save)(update_fields=['phase'])

            if game.lobby_message_id:
                try:
                    target_chat = game.chat_id or chat_id
                    await bot.delete_message(chat_id=target_chat, message_id=game.lobby_message_id)
                except Exception as del_err:
                    logger.debug(f"Could not delete lobby message {game.lobby_message_id}: {del_err}")

            minutes_display = max(1, timeout // 60)
            try:
                await bot.send_message(
                    chat_id,
                    f"⚠️ <b>Vaqt cho'zilib ketdi!</b>\n"
                    f"<b>{minutes_display} daqiqa</b> ichida o'yin boshlanmaganligi sababli ro'yxatdan o'tish bekor qilindi.\n\n"
                    "Yangi o'yin boshlash uchun <code>/game</code> buyrug'ini yuboring.",
                    parse_mode="HTML"
                )
            except Exception as send_err:
                logger.warning(f"Could not send timeout message to chat {chat_id}: {send_err}")

            logger.info(f"Lobby for game {game_id} timed out after {timeout}s ({minutes_display} min) and was cancelled.")
            break
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.warning(f"Error in lobby timer for {game_id}: {e}")
    finally:
        LOBBY_TIMERS.pop(game_id, None)


def start_lobby_timer(game_id: str, chat_id: int, bot: Bot, timeout: int = 300):
    """Starts or resets a lobby timeout."""
    existing = LOBBY_TIMERS.get(game_id)
    if existing and not existing.done():
        existing.cancel()
    task = asyncio.create_task(_run_lobby_timer(game_id, chat_id, bot, timeout))
    LOBBY_TIMERS[game_id] = task
    return task


def cancel_lobby_timer(game_id: str):
    """Cancels running lobby timeout."""
    task = LOBBY_TIMERS.pop(game_id, None)
    if task and not task.done():
        task.cancel()


def format_lobby_text(game: Game, bot_name: str = "Bloody Mafia") -> str:
    """Formats group lobby message querying real players from DB."""
    from apps.games.models import Player
    from apps.superadmin.services import TextService
    players = list(Player.objects.filter(game_id=game.id).order_by('created_at'))
    player_count = len(players)

    tpl = TextService.get_text(
        'lobby_join_text',
        fallback="<b>{bot_name}</b>               <code>BM Admin</code>\n<b>Ro'yxatdan o'tish davom etmoqda!</b>\n<b>Ro'yxatdan o'tganlar:</b>\n\n{player_names}\n\n<b>Jami: {total} ta</b>"
    )

    if players:
        player_list_text = "\n".join([
            f'{i+1}. <a href="tg://user?id={p.telegram_user_id}">{html.escape(p.display_name)}</a>'
            for i, p in enumerate(players)
        ])
        return tpl.format(bot_name=html.escape(bot_name), player_names=player_list_text, total=player_count)
    else:
        return tpl.format(bot_name=html.escape(bot_name), player_names="<i>Hozircha hech kim qo'shilmadi</i>", total=0)


@router.message(CommandStart())
async def cmd_start_private(message: types.Message, command: CommandObject, bot: Bot):
    """Handles /start in PM and deep link game joining."""
    if message.chat.type != "private":
        return

    bot_info = await bot.get_me()
    args = command.args

    if args and args.startswith("join_"):
        game_id = args.replace("join_", "").strip()
        try:
            game = await sync_to_async(
                lambda: Game.objects.select_related('bot').get(id=game_id)
            )()
            if game.phase != GamePhase.WAITING:
                await message.answer("⚠️ Bu o'yinga ro'yxatdan o'tish yakunlangan.")
                return

            player, created = await sync_to_async(GameService.join_lobby)(
                game=game,
                telegram_user_id=message.from_user.id,
                username=message.from_user.username or '',
                display_name=message.from_user.full_name or message.from_user.first_name
            )

            if created:
                await message.answer(
                    "Siz o'yinga muvaffaqiyatli qo'shildingiz!",
                    reply_markup=build_back_to_group_keyboard(chat_id=game.chat_id),
                    parse_mode="HTML"
                )
                try:
                    bot_name = game.bot.name if game.bot else "Bloody Mafia"
                    new_text = await sync_to_async(format_lobby_text)(game, bot_name)
                    kb = build_group_lobby_keyboard(bot_info.username, str(game.id))
                    if game.lobby_message_id:
                        try:
                            await bot.edit_message_caption(
                                chat_id=game.chat_id,
                                message_id=game.lobby_message_id,
                                caption=new_text,
                                reply_markup=kb,
                                parse_mode="HTML"
                            )
                        except Exception:
                            await bot.edit_message_text(
                                text=new_text,
                                chat_id=game.chat_id,
                                message_id=game.lobby_message_id,
                                reply_markup=kb,
                                parse_mode="HTML"
                            )
                except Exception as e:
                    logger.warning(f"Could not update lobby message: {e}")
            else:
                await message.answer(
                    "Siz allaqachon ro'yxatdan o'tgansiz!",
                    reply_markup=build_back_to_group_keyboard(chat_id=game.chat_id),
                    parse_mode="HTML"
                )
        except Exception as e:
            logger.warning(f"Error in deep link join: {e}")
            await message.answer("❌ O'yin topilmadi yoki xatolik yuz berdi.")
        return

    # Normal PM /start menu
    tpl = await sync_to_async(TextService.get_text)(
        'lobby_pm_start_greeting',
        fallback="Salom, <b>{first_name}</b>! 🎭\n\nMen <b>Mafia Bot</b>man. Men guruhlarda do'stlaringiz bilan birga afsonaviy Mafiya o'yinini o'ynash uchun xizmat qilaman!\n\nGuruhda yangi o'yin ochish uchun <code>/game</code> buyrug'ini yuboring.\n\n💬 <i>Savol va takliflaringiz bo'lsa @ismoilo9 ga murojaat qiling.</i>"
    )
    greeting = tpl.format(first_name=html.escape(message.from_user.first_name))
    await message.answer(greeting, reply_markup=build_child_start_keyboard(bot_info.username), parse_mode="HTML")


@router.message(Command("game", "start_lobby", ignore_case=True))
async def cmd_create_game_lobby(message: types.Message, bot: Bot):
    """Handles /game in group chat."""
    if message.chat.type == "private":
        await message.answer("⚠️ Ushbu buyruq faqat guruhlarda ishlaydi! Meni biror guruhga qo'shing va u yerda <code>/game</code> deb yozing.", parse_mode="HTML")
        return

    bot_info = await bot.get_me()
    if not is_targeted_at_this_bot(message, bot_info.username):
        return

    chat_id = message.chat.id
    bot_record = await sync_to_async(
        lambda: BotModel.objects.filter(
            Q(telegram_bot_id=bot.id) | Q(telegram_username__iexact=bot_info.username)
        ).first()
    )()
    if not bot_record:
        bot_record = await sync_to_async(BotModel.objects.first)()
    await sync_group_info(bot, message.chat, bot_record)

    # Check if bot has administrator privileges in the group
    try:
        bot_member = await bot.get_chat_member(chat_id=chat_id, user_id=bot_info.id)
        if bot_member.status not in ['administrator', 'creator']:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="➕ Botga Adminlik berish 👑",
                        url=f"https://t.me/{bot_info.username}?startgroup=admin"
                    )
                ]
            ])
            await message.reply(
                f"⚠️ <b>Diqqat:</b> Guruhda o'yin yaratish, xabarlarni pin qilish va o'yinni boshqarish uchun botga <b>Guruh Administratori</b> huquqini bering! 👑\n\n"
                f"<i>Adminlik berilgach, qaytadan /game buyrug'ini yuboring.</i>",
                reply_markup=kb,
                parse_mode="HTML"
            )
            return
    except Exception as perm_check_err:
        logger.warning(f"Could not verify bot admin status in {chat_id}: {perm_check_err}")

    active_running_game = await sync_to_async(
        lambda: Game.objects.filter(
            chat_id=chat_id,
            phase__in=[GamePhase.STARTING, GamePhase.NIGHT, GamePhase.DAY, GamePhase.VOTING]
        ).order_by('-created_at').first()
    )()

    if active_running_game:
        now = timezone.now()
        is_stale = (
            (active_running_game.updated_at < now - timedelta(minutes=10)) or
            (active_running_game.created_at < now - timedelta(minutes=20))
        )
        if is_stale:
            active_running_game.phase = GamePhase.CANCELED
            await sync_to_async(active_running_game.save)(update_fields=['phase'])
            logger.info(f"Auto-cancelled stale running game {active_running_game.id} in chat {chat_id}")
        else:
            cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🛑 O'yinni to'xtatish va yangi ochish", callback_data=f"lobby:force_cancel:{active_running_game.id}")]
            ])
            await message.answer(
                "⚠️ <b>Ushbu guruhda o'yin allaqachon davom etmoqda!</b>\n\n"
                "O'yinni to'xtatish uchun /cancel yuboring yoki quyidagi tugmani bosing:",
                reply_markup=cancel_kb,
                parse_mode="HTML"
            )
            return

    bot_id_str = str(bot_record.id) if bot_record else ''
    game_perm = await sync_to_async(SettingService.get_group_or_bot_timing_str)(chat_id, bot_id_str, 'cmd_perm_game', 'ALL')
    allowed, err_msg = await check_user_group_permission(bot, chat_id, message.from_user.id, game_perm)
    if not allowed:
        await message.answer(err_msg, parse_mode="HTML")
        return

    lobby_timeout_min = await sync_to_async(SettingService.get_group_or_bot_timing)(chat_id, bot_id_str, 'lobby_timeout_minutes', 5)
    lobby_timeout_seconds = max(30, int(lobby_timeout_min) * 60)

    now = timezone.now()

    # Check if there is already a WAITING lobby in this chat - ALWAYS PRESERVE PLAYERS!
    active_waiting_game = await sync_to_async(
        lambda: Game.objects.filter(chat_id=chat_id, phase=GamePhase.WAITING).order_by('-created_at').first()
    )()

    if active_waiting_game:
        game = active_waiting_game
        # RESET COUNTDOWN: Every /game call gives a full fresh 5-minute timeout from now!
        game.phase_ends_at = now + timedelta(seconds=lobby_timeout_seconds)
        await sync_to_async(game.save)(update_fields=['phase_ends_at'])
        if game.lobby_message_id:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=game.lobby_message_id)
            except Exception:
                pass
    else:
        game = await sync_to_async(GameService.create_game)(
            bot=bot_record,
            chat_id=chat_id,
            mode="CLASSIC"
        )
        game.phase_ends_at = now + timedelta(seconds=lobby_timeout_seconds)
        await sync_to_async(game.save)(update_fields=['phase_ends_at'])

    bot_name = bot_record.name if bot_record else "Bloody Mafia"
    lobby_text = await sync_to_async(format_lobby_text)(game, bot_name)
    kb = build_group_lobby_keyboard(bot_info.username, str(game.id))

    from bot_runtime.handlers.night import send_dynamic_animation
    sent_msg = await send_dynamic_animation(
        bot=bot,
        chat_id=chat_id,
        media_key='gif_lobby',
        fallback_url="https://media.giphy.com/media/26hirEPeos6yugLDO/giphy.gif",
        caption=lobby_text,
        reply_markup=kb,
        parse_mode="HTML"
    )

    if sent_msg:
        game.lobby_message_id = sent_msg.message_id
        await sync_to_async(game.save)(update_fields=['lobby_message_id'])
        try:
            await bot.pin_chat_message(
                chat_id=chat_id,
                message_id=sent_msg.message_id,
                disable_notification=False
            )
        except Exception as pin_err:
            logger.warning(f"Could not pin lobby message in chat {chat_id}: {pin_err}")

    start_lobby_timer(str(game.id), chat_id, bot, timeout=lobby_timeout_seconds)


@router.message(Command("start_game", "go", "boshlash", "start", ignore_case=True))
async def cmd_start_game(message: types.Message, bot: Bot):
    """Handles /start_game in group chat. Distributes roles for all 38 roles."""
    if message.chat.type == "private":
        return

    bot_info = await bot.get_me()
    if not is_targeted_at_this_bot(message, bot_info.username):
        return

    bot_record = await sync_to_async(
        lambda: BotModel.objects.filter(telegram_username__iexact=bot_info.username).first()
    )()
    bot_id_str = str(bot_record.id) if bot_record else ''
    start_perm = await sync_to_async(SettingService.get_group_or_bot_timing_str)(message.chat.id, bot_id_str, 'cmd_perm_start_game', 'ADMINS')
    allowed, err_msg = await check_user_group_permission(bot, message.chat.id, message.from_user.id, start_perm)
    if not allowed:
        await message.answer(err_msg, parse_mode="HTML")
        return

    chat_id = message.chat.id
    game = await sync_to_async(
        lambda: Game.objects.filter(chat_id=chat_id, phase=GamePhase.WAITING).order_by('-created_at').first()
    )()

    if not game:
        ongoing_game = await sync_to_async(
            lambda: Game.objects.filter(
                chat_id=chat_id,
                phase__in=[GamePhase.NIGHT, GamePhase.DAY, GamePhase.VOTING]
            ).order_by('-created_at').first()
        )()
        if ongoing_game:
            cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🛑 O'yinni to'xtatish", callback_data=f"lobby:force_cancel:{ongoing_game.id}")]
            ])
            await message.answer(
                "⚠️ <b>O'yin allaqachon boshlangan va davom etmoqda!</b>\n"
                "To'xtatish uchun /cancel yuboring yoki quyidagi tugmani bosing:",
                reply_markup=cancel_kb,
                parse_mode="HTML"
            )
        else:
            await message.answer("⚠️ Faol o'yin topilmadi. Yangi o'yin ochish uchun <code>/game</code> buyrug'ini yuboring.", parse_mode="HTML")
        return

    cancel_lobby_timer(str(game.id))
    if game.lobby_message_id:
        try:
            await bot.unpin_chat_message(chat_id=game.chat_id, message_id=game.lobby_message_id)
        except Exception:
            pass
        try:
            await bot.delete_message(chat_id=game.chat_id, message_id=game.lobby_message_id)
        except Exception:
            pass

    try:
        start_result = await sync_to_async(GameService.start_game)(game=game)
        if isinstance(start_result, tuple) and len(start_result) == 2 and isinstance(start_result[0], list):
            assignments, game = start_result
        else:
            assignments = start_result

        living_players = [p for p, r in assignments]

        from bot_runtime.handlers.night import _register_ids, start_night_timer, role_icon, role_label
        _register_ids(str(game.id), living_players)

        living_roster = "\n".join([
            f'{i+1}. <a href="tg://user?id={p.telegram_user_id}">{html.escape(p.display_name)}</a>'
            for i, p in enumerate(living_players)
        ])

        mafia_members = [(p, r) for p, r in assignments if r.name in ["DON", "MAFIA", "ADVOKAT", "UBIYTSA", "JURNALIST", "AYGOQCHI", "LABORANT"]]

        # Group Message 1
        try:
            start_msg = await sync_to_async(TextService.get_text)(
                'lobby_game_started_text',
                fallback="🎮 <b>O'yin boshlandi!</b>\n\nRollar taqsimlanmoqda... Botga o'tib rolingizni ko'ring!"
            )
            await message.answer(
                start_msg,
                reply_markup=build_bot_pm_keyboard(bot_info.username),
                parse_mode="HTML"
            )
        except Exception:
            pass

        # Group Message 2 (Night GIF)
        night_tpl = await sync_to_async(TextService.get_text)(
            'night_start_announcement',
            fallback="🌙 <b>Qorong'u va daxshatlarga to'la tun boshlandi.</b>\nKo'chaga yana zulmat tushdi. <b>60 sekund</b> davomida harakatlaringizni bajaring!\n\n👥 <b>O'yinchilar: ({count} ta)</b>\n{players_list}"
        )
        try:
            night_text = night_tpl.format(round_num=1, count=len(living_players), players_list=living_roster)
        except Exception:
            night_text = (
                f"🌙 <b>Qorong'u va daxshatlarga to'la tun boshlandi.</b>\n"
                f"Qo'rqmaslar ko'chaga chiqishga jur'at qilishdi.\n\n"
                f"👥 <b>O'yinchilar:</b>\n{living_roster}\n\n"
                f"Tun davomida ⏳ <b>60 sekund</b> vaqt bor."
            )
        from bot_runtime.handlers.night import send_dynamic_animation
        await send_dynamic_animation(
            bot=bot,
            chat_id=message.chat.id,
            media_key='gif_night',
            fallback_url="https://media.giphy.com/media/26hirEPeos6yugLDO/giphy.gif",
            caption=night_text,
            reply_markup=build_bot_pm_keyboard(bot_info.username),
            parse_mode="HTML"
        )

        # Send Role Cards (All 38 Roles matching Screenshot 1)
        ROLE_DESCRIPTIONS = {
            'DON': "Siz Donsiz, shahar Mafialarining yetakchisisiz. Tunda kim o'lishini hal qilasiz va Komissar tekshiruvida begunoh ko'rinasiz.",
            'MAFIA': "Siz Mafiasiz, Donga bo'ysunasiz va sizga qarshilik qilganlarni o'ldirasiz. Don o'lsa siz yangi Don bo'lishingiz mumkin.",
            'DOCTOR': "Siz Shifokorsiz. Bu tunda bir fuqaroning hayotini saqlab qolishingiz mumkin.",
            'HAMSHIRA': "Siz Hamshirasiz. Shifokorning yordamchisisiz. Shifokor halok bo'lsa, uning o'rnini egallaysiz.",
            'DETECTIVE': "Siz Komissarsiz, shahar himoyachisisiz. Har tunda shubhali shaxsni tekshirishingiz yoki qurolingizdan otishingiz mumkin.",
            'KOMISSAR': "Siz Komissarsiz, shahar himoyachisisiz. Har tunda shubhali shaxsni tekshirishingiz yoki qurolingizdan otishingiz mumkin.",
            'SHERIFF': "Siz Komissarsiz, shahar himoyachisisiz. Har tunda shubhali shaxsni tekshirishingiz yoki qurolingizdan otishingiz mumkin.",
            'SERJANT': "Siz Serjantsiz, Komissarning o'ng qo'lisiz. Komissar halok bo'lsa, uning o'rniga o'tasiz.",
            'CITIZEN': "Siz oddiy fuqarosiz. Shaharni Mafialardan tozalash uchun kunduzgi muhokama va ovoz berishda faol qatnashing.",
            'OMADLI': "Siz Omadlisiz! Tungi suiqasd vaqtida omadingiz kulsa (50%) tirik qolasiz. Tunda vazifangiz yo'q, xotirjam uxlang.",
            'JANOB': "Siz Janobsiz! Kunduzgi ovoz berishda ovozingiz 2 taga teng bo'ladi va shaxsingiz oshkor bo'lmaydi.",
            'SOTQIN': "Siz Sotqinsiz. Tunda kimnidir tekshirasiz: agar u Mafia/Don/Qotil bo'lsa, tongda shaxsingizni yashirgan holda shaharga jar solasiz.",
            'ADMIRAL': "Siz Admiralsiz. Komissar va Serjant tirik ekan, sizni hech kim o'ldirolmaydi. Ular o'lsa yangi Komissar bo'lasiz.",
            'ROBINGUD': "Siz Robin Gudsiz! Har tunda 1 kishini o'ldira olasiz. Agar bitta o'yinda 2 ta tinch aholini o'ldirsangiz, aholi sizni toshbo'ron qiladi.",
            'FOTOPARATCHI': "Siz Fotoparatchisiz. Tunda kimnidir kuzatasiz: agar u tunda mehmonga borgan bo'lsa, kimnikiga borganini rasmga olib fosh qilasiz.",
            'DAYDI': "Siz Daydisiz. Tunda ichkilik so'rab mehmonga borasiz. Agar borgan joyingizda qotillik sodir bo'lsa, guvoh bo'lasiz.",
            'KEZUVCHI': "Siz Kezuvchisiz. Tunda tanlagan odamingizning tungi harakatini va kunduzgi ovozini bloklaysiz.",
            'ADVOKAT': "Siz Mafiyalar Advokatisiz. Tunda tanlagan hamkoringizni Komissar tekshiruvidan himoyalaysiz.",
            'UBIYTSA': "Siz yollanma Ubiytsasiz. Har tunda o'zingiz tanlagan fuqaroni yo'q qilasiz.",
            'JURNALIST': "Siz Jurnalistsiz. Tunda intervyu olgani borgan xonadoningizga kimlar kelganini kuzatib, Mafiyaga yetkazasiz.",
            'AYGOQCHI': "Siz Ayg'oqchisiz. Tunda istalgan o'yinchining rolini aniqlab, Mafiyaga oshkor qilasiz.",
            'LABORANT': "Siz Laborantsiz. Mafia a'zosini tanlasangiz himoya qilasiz, boshqalarni esa zaharlab o'ldirasiz.",
            'KIMYOGAR': "Siz Kimyogarsiz. Erkin rolsiz! Hohlasangiz davolaysiz, hohlasangiz zahar berasiz. Omon qolsangiz yutasiz.",
            'RAIS': "Siz Raissiz. Erkin rolsiz! Har tunda kimgadir 1-100 $ tarqatasiz. Omon qolsangiz yutasiz.",
            'BORI': "Siz Bo'risiz. Agar Mafia o'ldirsa — Mafiyaga aylanasiz, Komissar o'ldirsa — Serjantga aylanasiz. Boshqalar o'ldirsa — o'lasiz.",
            'AFERIST': "Siz Aferistsiz. Tunda kimningdir ovozini o'g'irlaysiz. Ertaga u ovoz berolmaydi, uning nomidan siz ovoz berasiz.",
            'GAZABKOR': "Siz G'azabkorsiz. Har tunda 1 kishini belgilaysiz. O'lganingizda barcha belgilanganlar siz bilan o'ladi. 3+ kishi belgilab o'lsangiz yutasiz.",
            'SEHRGAR': "Siz Sehrgarsiz. Don, Qotil, Komissar hujum qilsa o'lmaysiz va ularga rahm qilish yoki o'ldirish tanlovi beriladi.",
            'QOTIL': "Siz shafqatsiz Qotilsiz. Yakka o'ynaysiz. Har tunda 1 kishini o'ldirasiz.",
            'KONCHI': "Siz Konchisiz. Har tunda 10 ta kondan birini tanlaysiz (3 ta o'lim, 2 ta 💎, 5 ta 💵). Omon qolsangiz yutasiz.",
            'QAROQCHI': "Siz Qaroqchisiz. Tunda kimnikigadir pul o'g'irlashga borasiz. Pul topolmasangiz 50% HP urib ketasiz.",
            'QORBOBO': "Siz Qorbobosiz! Har tunda odamlarga qurollar yoki faol rollarni sovg'a qilasiz. Omon qolsangiz yutasiz.",
            'OSHPAZ': "Siz Oshpazsiz. Tunda maxsus taomingizni berasiz. Ertaga jabrlanuvchining boshi aylanib, ovozi adashib ketadi.",
            'AFSUNGAR': "Siz Afsungarsiz. Tunda sizni o'ldirgan qotil o'ladi. Kunduzi osilsangiz 1 kishini birga olib ketasiz.",
            'TUZOQCHI': "Siz Tuzoqchisiz. Tunda kimningdir uyiga tuzoq qo'yasiz. Oldiga kelgan har qanday mehmon o'ladi.",
            'AXMOQ': "Siz Axmoqsiz. Tunda kalla qo'yasiz. Mafiyaga teginsangiz u o'ladi!",
            'BUQALAMUN': "Siz Buqalamunsiz. 1-tunda tanlagan odamingizning roliga aylanasiz.",
            'JOKER': "Siz Jokersiz. Qutilarga bomba joylab aholini sinovdan o'tkazasiz.",
            'SUIDSID': "Siz Suidsidsiz. Agar sizni kunduzi osib o'ldirishsa — yakka o'zingiz g'alaba qozonasiz!",
            'ZOMBI': "Siz Zombisiz. Har tunda boshqalarni tishlab zombiga aylantirasiz.",
        }

        for player, role in assignments:
            rname = role.name
            gid = str(game.id)
            icon = role_icon(rname)
            label = role_label(rname)
            desc = ROLE_DESCRIPTIONS.get(rname, "Siz o'yin ishtirokchisisiz. Kunduzgi muhokama va ovoz berishda faol qatnashing.")

            # 1. Send Role Card Message (Image 1 top card)
            role_card_text = (
                f"<b>Siz - {icon} {label}siz!</b>\n\n"
                f"{desc}"
            )
            try:
                await bot.send_message(
                    player.telegram_user_id,
                    role_card_text,
                    reply_markup=build_back_to_group_keyboard(chat_id=game.chat_id),
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"Failed to send role card to {player.telegram_user_id}: {e}")

            # 2. Send Teammates Reminder if Mafia / Don (Image 1 middle card)
            if rname in ["DON", "MAFIA", "ADVOKAT", "UBIYTSA", "JURNALIST", "AYGOQCHI", "LABORANT"] and len(mafia_members) > 1:
                team_lines = []
                for mp, mr in mafia_members:
                    m_icon = role_icon(mr.name)
                    m_label = role_label(mr.name)
                    team_lines.append(f"<b>{html.escape(mp.display_name)}</b> - {m_icon} <b>{m_label}</b>")
                team_msg = "<b>Sheriklaringizni eslab qoling!</b>\n\n" + "\n".join(team_lines)
                try:
                    await bot.send_message(
                        player.telegram_user_id,
                        team_msg,
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

            # 3. Send Night Action Prompt (Image 1 bottom card)
            try:
                if rname in ["DON", "MAFIA"]:
                    kb = build_night_target_keyboard(gid, "k", living_players, str(player.id))
                    await bot.send_message(player.telegram_user_id, "<b>Kimni o'ldiramiz?</b>", reply_markup=kb, parse_mode="HTML")

                elif rname in ["DOCTOR", "HAMSHIRA"] and rname == "DOCTOR":
                    kb = build_night_target_keyboard(gid, "p", living_players, str(player.id))
                    await bot.send_message(player.telegram_user_id, "<b>Kimni davolaymiz?</b>", reply_markup=kb, parse_mode="HTML")

                elif rname in ["DETECTIVE", "KOMISSAR", "SHERIFF"]:
                    kb = build_komissar_action_keyboard(gid)
                    await bot.send_message(player.telegram_user_id, "<b>Harakatingizni tanlang:</b>", reply_markup=kb, parse_mode="HTML")

                elif rname == "QOTIL":
                    kb = build_night_target_keyboard(gid, "qot", living_players, str(player.id))
                    await bot.send_message(player.telegram_user_id, "<b>Qurbonni tanlang:</b>", reply_markup=kb, parse_mode="HTML")

                elif rname == "KEZUVCHI":
                    kb = build_night_target_keyboard(gid, "kez", living_players, str(player.id))
                    await bot.send_message(player.telegram_user_id, "<b>Kimnikiga mehmonga borasiz?</b>", reply_markup=kb, parse_mode="HTML")

                elif rname == "DAYDI":
                    kb = build_night_target_keyboard(gid, "day", living_players, str(player.id))
                    await bot.send_message(player.telegram_user_id, "<b>Kimnikiga borasiz?</b>", reply_markup=kb, parse_mode="HTML")

                elif rname == "ADVOKAT":
                    kb = build_night_target_keyboard(gid, "adv", living_players)
                    await bot.send_message(player.telegram_user_id, "<b>Kimni himoyalaysiz?</b>", reply_markup=kb, parse_mode="HTML")

                elif rname == "UBIYTSA":
                    kb = build_night_target_keyboard(gid, "ubi", living_players, str(player.id))
                    await bot.send_message(player.telegram_user_id, "<b>Kimni o'ldirasiz?</b>", reply_markup=kb, parse_mode="HTML")

                elif rname == "TUZOQCHI":
                    kb = build_night_target_keyboard(gid, "tuz", living_players, str(player.id))
                    await bot.send_message(player.telegram_user_id, "<b>Tuzoqni kimga qo'yasiz?</b>", reply_markup=kb, parse_mode="HTML")

                elif rname == "ZOMBI":
                    kb = build_night_target_keyboard(gid, "zom", living_players, str(player.id))
                    await bot.send_message(player.telegram_user_id, "<b>Kimni tishlaysiz?</b>", reply_markup=kb, parse_mode="HTML")

                elif rname == "KIMYOGAR":
                    kb = build_night_target_keyboard(gid, "kim", living_players, str(player.id))
                    await bot.send_message(player.telegram_user_id, "<b>Eliksirni kimga berasiz?</b>", reply_markup=kb, parse_mode="HTML")

                elif rname == "RAIS":
                    kb = build_night_target_keyboard(gid, "rai", living_players, str(player.id))
                    await bot.send_message(player.telegram_user_id, "<b>Sovg'ani kimga berasiz?</b>", reply_markup=kb, parse_mode="HTML")

                elif rname == "AFERIST":
                    kb = build_night_target_keyboard(gid, "afer", living_players, str(player.id))
                    await bot.send_message(player.telegram_user_id, "<b>Kimning ovozini o'g'irlamoqchisiz?</b>", reply_markup=kb, parse_mode="HTML")

                elif rname == "GAZABKOR":
                    kb = build_night_target_keyboard(gid, "gaz", living_players)
                    await bot.send_message(player.telegram_user_id, "<b>Kimni belgilamoqchisiz?</b>", reply_markup=kb, parse_mode="HTML")

                elif rname == "JURNALIST":
                    kb = build_night_target_keyboard(gid, "jurn", living_players, str(player.id))
                    await bot.send_message(player.telegram_user_id, "<b>Kimnikiga intervyuga borasiz?</b>", reply_markup=kb, parse_mode="HTML")

                elif rname == "SOTQIN":
                    kb = build_night_target_keyboard(gid, "sotq", living_players, str(player.id))
                    await bot.send_message(player.telegram_user_id, "<b>Kimni tekshirmoqchisiz?</b>", reply_markup=kb, parse_mode="HTML")

                elif rname == "ROBINGUD":
                    kb = build_night_target_keyboard(gid, "rob", living_players, str(player.id))
                    await bot.send_message(player.telegram_user_id, "<b>Kamon o'qi bilan kimni otasiz?</b>", reply_markup=kb, parse_mode="HTML")

                elif rname == "AYGOQCHI":
                    kb = build_night_target_keyboard(gid, "ayg", living_players, str(player.id))
                    await bot.send_message(player.telegram_user_id, "<b>Qaysi o'yinchining rolini bilmoqchisiz?</b>", reply_markup=kb, parse_mode="HTML")

                elif rname == "KONCHI":
                    kb = build_konchi_mines_keyboard(gid)
                    await bot.send_message(player.telegram_user_id, "<b>Qaysi konni qazimoqchisiz?</b>", reply_markup=kb, parse_mode="HTML")

                elif rname == "FOTOPARATCHI":
                    kb = build_night_target_keyboard(gid, "foto", living_players, str(player.id))
                    await bot.send_message(player.telegram_user_id, "<b>Kimni rasmga olmoqchisiz?</b>", reply_markup=kb, parse_mode="HTML")

                elif rname == "QAROQCHI":
                    kb = build_night_target_keyboard(gid, "qar", living_players, str(player.id))
                    await bot.send_message(player.telegram_user_id, "<b>Kimning pullarini shilmoqchisiz?</b>", reply_markup=kb, parse_mode="HTML")

                elif rname == "LABORANT":
                    kb = build_night_target_keyboard(gid, "lab", living_players, str(player.id))
                    await bot.send_message(player.telegram_user_id, "<b>Nishonni tanlang:</b>", reply_markup=kb, parse_mode="HTML")

                elif rname == "QORBOBO":
                    kb = build_night_target_keyboard(gid, "qor", living_players, str(player.id))
                    await bot.send_message(player.telegram_user_id, "<b>Sovg'ani kimga topshirasiz?</b>", reply_markup=kb, parse_mode="HTML")

                elif rname == "OSHPAZ":
                    kb = build_night_target_keyboard(gid, "osh", living_players, str(player.id))
                    await bot.send_message(player.telegram_user_id, "<b>Maxsus taomingizni kimga yedirasiz?</b>", reply_markup=kb, parse_mode="HTML")

                elif rname == "AXMOQ":
                    kb = build_night_target_keyboard(gid, "axm", living_players, str(player.id))
                    await bot.send_message(player.telegram_user_id, "<b>Kimni tanlaysiz?</b>", reply_markup=kb, parse_mode="HTML")

                elif rname == "JOKER":
                    kb = build_joker_boxes_setup_keyboard(gid)
                    await bot.send_message(player.telegram_user_id, "<b>Bombani qaysi qutilarga joylaysiz?</b>", reply_markup=kb, parse_mode="HTML")
            except Exception as e:
                logger.warning(f"Failed to send night prompt to {player.telegram_user_id}: {e}")

        # Start Night Timer with bot timing setting
        bot_id_str = str(game.bot.id) if game and game.bot else ''
        n_dur = await sync_to_async(SettingService.get_group_or_bot_timing)(game.chat_id, bot_id_str, 'night_duration', 60)
        start_night_timer(str(game.id), bot, duration=n_dur)

    except ValueError as e:
        await message.answer(
            f"⚠️ <b>O'yinni boshlab bo'lmadi:</b>\n"
            f"Kamida <b>4 nafar o'yinchi</b> ro'yxatdan o'tishi kerak! Iltimos, o'yinchilar <b>Qo'shilish ↗</b> tugmasi orqali qo'shilishini kuting.",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.exception("Error starting game:")
        await message.answer(f"❌ O'yinni boshlashda xatolik yuz berdi.", parse_mode="HTML")


@router.message(Command("roles", "rollar", "qoidalar", ignore_case=True))
async def cmd_roles_catalog(message: types.Message, bot: Bot):
    """Handles /roles command opening the Roles Mini App."""
    bot_info = await bot.get_me()
    if not is_targeted_at_this_bot(message, bot_info.username):
        return

    from apps.superadmin.services import SettingService
    base_url = SettingService.get('webapp_base_url', os.environ.get('WEBAPP_BASE_URL', 'https://16-171-175-23.sslip.io')).rstrip('/')
    webapp_url = f"{base_url}/webapp/roles/"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎭 Rollar Katalogi (Mini App) ↗", web_app=WebAppInfo(url=webapp_url))]
    ])
    await message.answer(
        "🎭 <b>Mafia Rollar Katalogi:</b>\n\n"
        "O'yindagi barcha <b>38 ta rollar</b>, ularning qobiliyatlari, jamoalari va vazifalarini ko'rish uchun quyidagi Mini App tugmasini bosing:",
        reply_markup=kb,
        parse_mode="HTML"
    )


@router.message(Command("cancel", "stop", "toxtatish", "reset", ignore_case=True))
async def cmd_stop_game(message: types.Message, bot: Bot):
    """Cancels ongoing or waiting game."""
    if message.chat.type == "private":
        return

    bot_info = await bot.get_me()
    if not is_targeted_at_this_bot(message, bot_info.username):
        return

    bot_record = await sync_to_async(
        lambda: BotModel.objects.filter(telegram_username__iexact=bot_info.username).first()
    )()
    bot_id_str = str(bot_record.id) if bot_record else ''
    stop_perm = await sync_to_async(SettingService.get_group_or_bot_timing_str)(message.chat.id, bot_id_str, 'cmd_perm_stop_game', 'ADMINS')
    allowed, err_msg = await check_user_group_permission(bot, message.chat.id, message.from_user.id, stop_perm)
    if not allowed:
        await message.answer(err_msg, parse_mode="HTML")
        return

    chat_id = message.chat.id
    active_game = await sync_to_async(
        lambda: Game.objects.filter(
            chat_id=chat_id,
            phase__in=[GamePhase.WAITING, GamePhase.STARTING, GamePhase.NIGHT, GamePhase.DAY, GamePhase.VOTING]
        ).order_by('-created_at').first()
    )()

    if not active_game:
        # Also check if @utag is running in this chat
        task_key = (bot_info.id, chat_id)
        tag_task = ACTIVE_TAG_TASKS.pop(task_key, None) or ACTIVE_TAG_TASKS.pop(chat_id, None)
        if tag_task and not tag_task.done():
            tag_task.cancel()
            await message.answer("🛑 <b>A'zolarni chaqirish jarayoni to'xtatildi!</b>", parse_mode="HTML")
            return
        await message.answer("ℹ️ Guruhda to'xtatish uchun faol o'yin topilmadi.")
        return

    active_game.phase = GamePhase.CANCELED
    await sync_to_async(active_game.save)(update_fields=['phase'])
    cancel_lobby_timer(str(active_game.id))

    if active_game.lobby_message_id:
        try:
            await bot.unpin_chat_message(chat_id=chat_id, message_id=active_game.lobby_message_id)
        except Exception:
            pass
        try:
            await bot.delete_message(chat_id=chat_id, message_id=active_game.lobby_message_id)
        except Exception:
            pass

    await message.answer("🛑 <b>O'yin to'xtatildi va ro'yxatdan o'tish bekor qilindi.</b>\nYangi o'yin boshlash uchun /game buyrug'ini yuboring.", parse_mode="HTML")


@router.message(Command("leave", "chiqish", "tark", "quit", ignore_case=True))
async def cmd_leave_game(message: types.Message, bot: Bot):
    """Allows players to leave either a waiting lobby or an active ongoing game."""
    user = message.from_user
    if not user:
        return

    chat_id = message.chat.id
    bot_info = await bot.get_me()
    if not is_targeted_at_this_bot(message, bot_info.username):
        return

    # Find the active or waiting game in this chat, or player's active game if in private
    if message.chat.type in ["group", "supergroup"]:
        game = await sync_to_async(
            lambda: Game.objects.filter(
                chat_id=chat_id,
                phase__in=[GamePhase.WAITING, GamePhase.STARTING, GamePhase.NIGHT, GamePhase.DAY, GamePhase.VOTING]
            ).order_by('-created_at').first()
        )()
    else:
        player_record = await sync_to_async(
            lambda: Player.objects.filter(
                telegram_user_id=user.id,
                game__phase__in=[GamePhase.WAITING, GamePhase.STARTING, GamePhase.NIGHT, GamePhase.DAY, GamePhase.VOTING]
            ).select_related('game').order_by('-game__created_at').first()
        )()
        game = player_record.game if player_record else None

    if not game:
        await message.answer("ℹ️ Siz qatnashayotgan yoki guruhda faol bo'lgan o'yin topilmadi.")
        return

    success, phase_mode, display_name, role_name, winner = await sync_to_async(GameService.leave_game)(
        game=game, telegram_user_id=user.id
    )

    if not success:
        if phase_mode == 'ALREADY_DEAD':
            await message.answer("⚠️ Siz allaqachon o'yindan chiqqansiz yoki halok bo'lgansiz.")
        else:
            await message.answer("ℹ️ Siz ushbu o'yin ro'yxatida emassiz.")
        return

    # 1. Left Waiting Lobby
    if phase_mode == 'LOBBY':
        bot_name = game.bot.name if game.bot else "Bloody Mafia"
        new_text = await sync_to_async(format_lobby_text)(game, bot_name)
        kb = build_group_lobby_keyboard(bot_info.username, str(game.id))

        if game.lobby_message_id and message.chat.type in ["group", "supergroup"]:
            try:
                await bot.edit_message_caption(
                    chat_id=game.chat_id,
                    message_id=game.lobby_message_id,
                    caption=new_text,
                    reply_markup=kb,
                    parse_mode="HTML"
                )
            except Exception:
                try:
                    await bot.edit_message_text(
                        chat_id=game.chat_id,
                        message_id=game.lobby_message_id,
                        text=new_text,
                        reply_markup=kb,
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

        if message.chat.type in ["group", "supergroup"]:
            await message.answer(f"🚪 <b>{display_name}</b> ro'yxatdan chiqdi.", parse_mode="HTML")
        else:
            await message.answer("🚪 Siz o'yin ro'yxatidan muvaffaqiyatli chiqdingiz.")

    # 2. Left Active Ongoing Game
    elif phase_mode == 'ACTIVE':
        from bot_runtime.handlers.night import role_label, role_icon
        r_icon = role_icon(role_name)
        r_name = role_label(role_name)
        role_display = f"{r_icon} {r_name}".strip()

        mention = f'<a href="tg://user?id={user.id}">{html.escape(display_name)}</a>'
        leave_msg = f"{mention} bu shaxarning yovuzliklariga chiday olmay o'zini osib qo'ydi. U {role_display} edi"

        if game.chat_id:
            try:
                await bot.send_message(game.chat_id, leave_msg, parse_mode="HTML")
            except Exception:
                pass

        if message.chat.type == "private":
            await message.answer("🚪 Siz o'yinni tark etdingiz.")

        if winner:
            from bot_runtime.handlers.night import _announce_game_winner
            try:
                await _announce_game_winner(game, winner, bot)
            except Exception as v_err:
                logger.warning(f"Error announcing victory after leave: {v_err}")


@router.callback_query(lambda c: c.data and c.data.startswith("lobby:"))
async def handle_lobby_callback(callback: types.CallbackQuery, bot: Bot):
    """Handles lobby join/leave/start/cancel inline buttons."""
    parts = callback.data.split(":")
    action = parts[1]
    game_id = parts[2]

    bot_info = await bot.get_me()

    try:
        game = await sync_to_async(
            lambda: Game.objects.select_related('bot').get(id=game_id)
        )()

        if action == "force_cancel":
            game.phase = GamePhase.CANCELED
            await sync_to_async(game.save)(update_fields=['phase'])
            cancel_lobby_timer(str(game.id))
            if game.lobby_message_id:
                try:
                    await bot.delete_message(chat_id=game.chat_id, message_id=game.lobby_message_id)
                except Exception:
                    pass
            await callback.answer("🛑 O'yin to'xtatildi!")
            await callback.message.edit_text(
                "🛑 <b>Oldingi o'yin to'xtatildi va lobby o'chirildi!</b>\n\n"
                "Yangi o'yin boshlash uchun /game buyrug'ini yuboring.",
                parse_mode="HTML"
            )
            return

        if game.phase != GamePhase.WAITING:
            await callback.answer("⚠️ O'yinga yozilish yakunlangan.", show_alert=True)
            return

        if action == "join":
            if callback.from_user and game.chat_id:
                record_group_user(game.chat_id, callback.from_user)
            player, created = await sync_to_async(GameService.join_lobby)(
                game=game,
                telegram_user_id=callback.from_user.id,
                username=callback.from_user.username or '',
                display_name=callback.from_user.full_name or callback.from_user.first_name
            )
            if created:
                await callback.answer("✅ Siz o'yinga qo'shildingiz!")
                bot_name = game.bot.name if game.bot else "Bloody Mafia"
                new_text = await sync_to_async(format_lobby_text)(game, bot_name)
                kb = build_group_lobby_keyboard(bot_info.username, str(game.id))
                try:
                    await callback.message.edit_text(text=new_text, reply_markup=kb, parse_mode="HTML")
                except Exception:
                    pass
            else:
                await callback.answer("ℹ️ Siz allaqachon ro'yxatdan o'tgansiz.", show_alert=True)

        elif action == "leave":
            removed = await sync_to_async(GameService.leave_lobby)(
                game=game, telegram_user_id=callback.from_user.id
            )
            if removed:
                await callback.answer("🚪 Siz o'yindan chiqdingiz.")
                bot_name = game.bot.name if game.bot else "Bloody Mafia"
                new_text = await sync_to_async(format_lobby_text)(game, bot_name)
                kb = build_group_lobby_keyboard(bot_info.username, str(game.id))
                try:
                    await callback.message.edit_text(text=new_text, reply_markup=kb, parse_mode="HTML")
                except Exception:
                    pass
            else:
                await callback.answer("Siz ro'yxatda yo'qsiz.", show_alert=True)

    except Exception as e:
        logger.warning(f"Error in lobby callback: {e}")
        await callback.answer("Xatolik yuz berdi.", show_alert=True)



# Child bot feedback callback
@router.callback_query(lambda c: c.data == "start:feedback")
async def handle_child_feedback_button_click(callback: types.CallbackQuery):
    """Prompts user in child bot to type their question or suggestion."""
    from bot_runtime.handlers.father_master import FEEDBACK_WAITING_USERS
    FEEDBACK_WAITING_USERS[callback.from_user.id] = True
    await callback.answer()
    await callback.message.answer(
        "✍️ <b>Savol yoki taklifingizni yozib qoldiring:</b>\n\n"
        "Sizning murojaatingiz to'g'ridan-to'g'ri platforma administratoriga (@ismoilo9) yetkaziladi.\n"
        "Iltimos, xabaringizni shu yerga yozib yuboring:",
        parse_mode="HTML"
    )


# ---------------------------------------------------------------------------
# Creative Group Member Tagging (@utag / /utag)
# ---------------------------------------------------------------------------
ACTIVE_TAG_TASKS: dict = {}
GROUP_TRACKED_USERS: dict = {}


def record_group_user(chat_id: int, user: Optional[types.User]):
    """Records any real human member seen active in the group."""
    if not user or user.is_bot or user.id in (777000, 1087968824):
        return
    username = user.username or ''
    if username.lower().endswith('bot'):
        return
    chat_dict = GROUP_TRACKED_USERS.setdefault(chat_id, {})
    display_name = user.full_name or user.first_name or f"Foydalanuvchi {user.id}"
    chat_dict[user.id] = {
        'telegram_user_id': user.id,
        'display_name': display_name,
        'username': username,
        'is_bot': False
    }


class GroupUserTrackingMiddleware(BaseMiddleware):
    """Outer middleware to continuously record any user sending messages in groups."""
    async def __call__(self, handler, event: types.TelegramObject, data: dict):
        if isinstance(event, types.Message) and event.chat and event.chat.type in ["group", "supergroup"]:
            if event.from_user:
                record_group_user(event.chat.id, event.from_user)
        return await handler(event, data)


router.message.outer_middleware(GroupUserTrackingMiddleware())


UTAG_CREATIVE_PHRASES = [
    # ─── 1. O'ZBEKCHA MEMLAR, INSTAGRAM VA VIRAL GAPLAR ────────────────────────
    "Instagramda reels ko'rib o'tirmasdan bir o'yinga kiring! 🎬😂",
    "Shunchaki tomoshabin bo'lib turasizmi yoki jangga kirasizmi? 😎",
    "Meni eshitayotgan bo'lsangiz bitta layk... yo'g'e o'yinga kiring! 🤣",
    "Bir paytlar bitta odam ham shunaqa jim o'tirgan ekan... 🗿",
    "Uxlashga hali erta, guruhda jang boshlanyapti! ⚔️🔥",
    "Admin ko'rmasdan bitta qizg'in o'yin o'ynab olaylik! 🤫",
    "Lavash sovuq yeyilmaydi, Mafiya kutib turilmaydi! 🌯😋",
    "Ko'zlaringiz qizarib ketmadimi reel ko'raverib? Keling o'ynaymiz! 👀",
    "Bugungi kun tartibi: 1. Turish, 2. Mafiyaga kirish, 3. Yutish! 🏆",
    "Bitta o'yinda o'zingizni ko'rsatib qo'ying-a! 🔥",
    "Sizsiz guruhda svet o'chib qolgandek jimjitlik bo'lyapti! 💡⚡",
    "Odam degan ham shuncha passiv bo'ladimi, qani olg'a! 😂",
    "Tugadi... hamma yig'ildi, faqat bitta siz yetishmayapsiz! ⏳",
    "Bir dona o'yin, keyin xohlagancha uxlaysiz! 😴",
    "Shaharda tartibsizlik, siz esa xotirjam choy ichyapsiz! ☕",
    "Bu yerda sizsiz mafiyani yengib bo'lmayapti, yordam bering! 🕵️‍♂️",
    "Instagram algoritmi sizni topolmasa ham biz topdik! 📱🎯",
    "Birovga aytmang, bugun aynan siz g'olib bo'lasiz! 🤫🥇",
    "Chaqirsak kelmaysiz, o'zingiz boshlamaysiz, qani endi bir ko'raylik! 🤷‍♂️",
    "Guruhda yangi shov-shuv: siz o'yinga kirarmishsiz! 🚀",
    "Miyani charxlaymiz, bir dona mafiya o'ynaylik! 🧠💡",
    "Eski qadrdonlar yig'ilyapti, siz qayerdasiz? 🤝",
    "Statistikangizni ko'tarish vaqti keldi! 📊✨",
    "Don sizdan qo'rqyapti, shuning uchun kirmayapsizmi? 🤵👀",
    "Keling, bugun kim kimligini ko'rsatib qo'yamiz! 🎭",
    "Ismoil Maftunani sevadi ❤️",
    "Gap egasini topadi, o'yinchi esa o'yinni! 🎯",
    "Arvohlardan qo'rqasizmi? Masalan mendan! 😂👻",
    "Guruhga ozgina shovqin va fayz kerak! 🎉🥳",
    "Kechagina g'olib bo'laman degandingiz, qani amalda ko'rsating! 🥇",
    "Yana qancha kutaylik? O'yin boshlanyapti! ⏰",
    "Qani, mafiyalar oviga chiqamiz! 🏹⚔️",
    "Uyquni chetga suring, hozir o'yin vaqti! ⚡",
    "Bitta kirib chiqing, o'rganib qolasiz! 😉🎮",
    "Tinch aholi aynan sizdan umidvor! 🛡️",
    "Qani, kim mafiya, kim begunoh ekanini aniqlaymiz! 🔎",
    "Guruhning eng faol o'yinchisi siz bo'lasiz, ishonavering! 🌟",
    "O'tirishdan foyda yo'q, bitta o'yin kayfiyatni ko'taradi! 🚀",
    "Sukut saqlash bo'yicha Ginnes rekordini o'rnatmoqchimisiz? 😂",
    "Telegramdagi eng zo'r o'yinchi shu yerda ekan-ku! 👑",
    "Telefonni qo'lga oling va o'yinga kiring! 📲",
    "Shahar xavf ostida, qahramonlik qilish vaqti keldi! 🦸‍♂️",
    "Sizni kutib sochlarimiz oqarib ketdi-ku! 👴👵",
    "Keling, ajoyib lahzalarni birga yaratamiz! 🎊",
    "Bugun omad siz tomonda, tekshirib ko'ring! 🍀",
    "Kimdir sizni o'yinda ko'rishni juda xohlamoqda! 💌",
    "Xafa bo'lish yo'q, faqat do'stona jang! 🤝",
    "O'yinga kirmaganlar jarimaga tortiladi! 🚓👮‍♂️",
    "Guruh ahli sizni sog'inib qoldi, qayerdasiz? 🤗",
    "Sizsiz o'yin qizimayapti, tezroq keling! 🔥",
    # ─── 2. YANGI KREATIK, HAZILOMUZ VA JANGARI GAPLAR ────────────────────────
    "Yotvolib kinoteatr qilmang, keling o'yinga kiring! 🍿🎬",
    "Komissar sizni qidiryapti, guvohlik berishingiz kerak! 🕵️‍♂️📑",
    "Don sizga salom yo'lladi, o'yinga taklif qilyapti! 🎩🍸",
    "Shifokor aytdi: Mafiya o'ynash kayfiyatga juda foydali ekan! 🩺💊",
    "Internet trafigingiz bekorga ketmasin, o'yinga kiring! 📶⚡",
    "Qani kim Don, kim Komissar? Bugun aniqlaymiz! 🎭⚔️",
    "Sizni kutib kofe sovib qoldi-ku! ☕🧊",
    "Siz kirsangiz guruhda bayram bo'lib ketadi! 🎈🥳",
    "Yashirin qobiliyatlaringizni ishga soladigan vaqt keldi! 🧠💥",
    "Hamma tayyor, qizil chiziqni bosib o'yinga kiring! 🏁🚗",
    "Ushbu xabarni o'qiganingiz uchun darhol o'yinga kirishingiz shart! 📜⚖️",
    "Bugun mafiyalarni bittama-bitta fosh qilamiz! 🔍🔦",
    "Shahar tinch aholisiga sizdek yetakchi kerak! 🛡️🏰",
    "Qo'rqmang, mafiyalar faqat tunda chiqadi! 🌃👻",
    "Sizning mahoratingiz oldida Don ham lol qoladi! 🌟👏",
    "Pulingiz ko'pmi yoki tajribangiz? O'yinda ko'rsating! 💰🎮",
    "Tungi ov boshlanmoqda, qurollaringizni shaylang! 🔫🌙",
    "Bitta g'alaba bilan guruh rekordini yangilang! 🏆🥇",
    "Maftunkor o'yinchi, sizsiz bu o'yin to'liq bo'lmaydi! ✨🌸",
    "Ko'p o'ylamang, intuitsiyangizga ishoning va kiring! 🔮🎯",
    "Sizni butun shahar qutqaruvchi deb bilyapti! 🌆🦸",
    "Agar kirmasangiz, mafiyalar shaharni egallab oladi! 😱⚠️",
    "Telegramdagi eng shiddatli jang boshlanmoqda! 💣🔥",
    "Bitta 'Qo'shilish' tugmasini bosish shunchalik qiyinmi? 😉👆",
    "Guruhning eng afsonaviy o'yinchisi qani? Ha, bu sizsiz! 👑⚡",
    "Uxlash foyda bermaydi, Mafiyada g'alaba qozonish kerak! 🛌❌",
    "Qani do'stlar, bitta qizg'in davra quramiz! 🤝🔥",
    "Siz kirmasangiz admin xafa bo'lib qoladi! 🥺👉👈",
    "Bu safar aniq yutasiz, bashoratchilar shunday dedi! 🔮⭐",
    "Shovqin-suron boshlandi, chetda qolib ketmang! 📣🎉",
    "Tarixda qoladigan jangni o'tkazib yubormang! 📜⚔️",
    "Siz uchun maxsus o'rin ajratib qo'yildi! 🪑✨",
    "Qani bitta ko'rsatib qo'ying qanday o'ynashni! 🚀😎",
    "Guruhda hamma sizni kutyapti, tezroq! 🏃‍♂️💨",
    "Sizsiz o'yin xuddi tuzsiz ovqatdek bo'lyapti! 🍲🧂",
    "Ko'z ochib yumguncha o'yin tugaydi, kiring tez! ⚡⏱️",
    "Shaharning yangi qahramoni bo'lishga tayyormisiz? 🎖️🌃",
    "Qo'shiling va guruhning eng kuchlisi kimligini isbotlang! 💪🔝",
    "Sizning ismingiz allaqachon afsonalarga aylangan! 📖🌟",
    "Hozir aynan sizning yordamingiz kerak bo'lyapti! 🆘🤝",
    "Kimdir siz bilan bir jamoada bo'lishni orzu qilyapti! 💭👫",
    "Zarbalar ketma-ketligi boshlandi, jangga kiring! 🥊⚡",
    "Tungi sukunatni buzib, g'alaba qozonamiz! 🌌🏆",
    "Siz o'yinga kirsangiz, raqiblar taslim bo'ladi! 🏳️😂",
    "Hamma o'yinda, siz nima qilib o'tiribsiz? 🧐📲",
    "Bugungi reytingda 1-o'ringa chiqish imkoniyati! 📊🥇",
    "Mafiya olamining eng kutilgan mehmonsiz! 🚪✨",
    "Qani do'stim, bitta zo'r partiya qilaylik! 🎲🎯",
    "Guruh ahli sizning donoligingizga muhtoj! 🦉💡",
    "O'yin start oldi, darhol saflarga qo'shiling! 🚀🛡️",
    "Siz kelsangiz guruhga fayz kiradi, marhamat! 🌺💐",
    "Shaharda yangi Don paydo bo'ldi, uni to'xtating! 🎩⚠️",
    "G'alaba ta'mini birga totib ko'raylik! 🍰🍾",
    "Telefon ekraniga emas, o'yinga e'tibor bering! 📱👀",
    "Sizning harakatlaringiz hamma uchun namuna! 🌟🎖️",
    "Bir marta kiring, afsuslanmaysiz! 💯✨",
    "Shahar posbonlari safida sizga joy tayyor! 🛡️👮",
    "Bugungi kechaning eng qizg'in dramasi shu yerda! 🎭🎬",
    "Tinch aholiga umid bag'ishlang, o'yinga kiring! 🕊️🏙️",
    "Siz bo'lmasangiz kim bu shaharni qutqaradi? 🤷‍♂️🦸",
    "Barcha rollar sizni kutmoqda, omadingizni sinang! 🃏🎲",
    "Yashirin sirlar fosh bo'lish arafasida! 🗝️🔍",
    "Guruhimizning yulduzi, sahnaga marhamat! 🌟🎤",
    "Sizsiz qiziq emas, keling birga o'ynaymiz! 🤝🔥",
    "Bugun sizning kuningiz bo'ladi, ishonamiz! ☀️🎉",
    "Shiddatli jang boshlanishiga sanoqli soniyalar qoldi! ⏳💣",
    "Dovruqingiz butun guruhga tarqalsin! 📣🏆",
    "Do'stlaringiz allaqachon bu yerda, siz qayerdasiz? 👥🏃",
    "Guruh tarixidagi eng unutilmas o'yinga xush kelibsiz! 🌟🎪",
    "Olg'a, faqat g'alaba sari! 🚀🏁",
]


@router.message(Command("stop_tag", "cancel_tag", ignore_case=True))
@router.message(F.text.func(lambda t: bool(t and (
    t.lower().strip() in ['@stop', '@stop_tag', '!stop', '/stop_tag', '/cancel_tag', '!stop_tag', 'stop_tag', '@stop!'] or
    t.lower().startswith('@stop ') or
    t.lower().startswith('@stop\n') or
    t.lower().startswith('/stop_tag')
))))
async def cmd_stop_utag(message: types.Message, bot: Bot):
    """Cancels ongoing @utag tagging process in the group with @stop or /stop_tag."""
    chat_id = message.chat.id
    if message.from_user:
        record_group_user(chat_id, message.from_user)

    bot_info = await bot.get_me()
    bot_record = await sync_to_async(
        lambda: BotModel.objects.filter(telegram_username__iexact=bot_info.username).first()
    )()
    bot_id_str = str(bot_record.id) if bot_record else ''
    stop_tag_perm = await sync_to_async(SettingService.get_group_or_bot_timing_str)(chat_id, bot_id_str, 'cmd_perm_stop_tag', 'ADMINS')
    allowed, err_msg = await check_user_group_permission(bot, chat_id, message.from_user.id if message.from_user else 0, stop_tag_perm)
    if not allowed:
        await message.reply(err_msg, parse_mode="HTML")
        return

    task_key = (bot_info.id, chat_id)
    task = ACTIVE_TAG_TASKS.pop(task_key, None) or ACTIVE_TAG_TASKS.pop(chat_id, None)
    if task and not task.done():
        task.cancel()
        await message.answer("🛑 <b>A'zolarni chaqirish jarayoni to'xtatildi!</b>", parse_mode="HTML")
    else:
        await message.answer("ℹ️ Hozirda faol chaqirish (@utag) jarayoni mavjud emas.")


@router.message(Command("utag", ignore_case=True))
@router.message(F.text.func(lambda t: bool(t and ('@utag' in t.lower() or t.lower().startswith('/utag') or t.lower().startswith('!utag') or t.lower().strip() == 'utag'))))
async def handle_utag_mention_or_command(message: types.Message, bot: Bot):
    """
    Handles @utag call in groups:
    Iterates over group members and tags them one-by-one with creative inviting messages.
    Tags ALL real users: with @username or with direct profile link if without username.
    Excludes all bots.
    """
    if message.chat.type not in ["group", "supergroup"]:
        return

    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else 0
    if message.from_user:
        record_group_user(chat_id, message.from_user)

    bot_info = await bot.get_me()
    bot_record = await sync_to_async(
        lambda: BotModel.objects.filter(
            Q(telegram_bot_id=bot.id) | Q(telegram_username__iexact=bot_info.username)
        ).first()
    )()
    bot_id_str = str(bot_record.id) if bot_record else ''

    # 1. Permission check with dynamic group setting (OWNER, ADMINS, ALL)
    utag_perm = await sync_to_async(SettingService.get_group_or_bot_timing_str)(chat_id, bot_id_str, 'cmd_perm_utag', 'ADMINS')
    allowed, err_msg = await check_user_group_permission(bot, chat_id, user_id, required_level=utag_perm)
    if not allowed:
        await message.reply(err_msg, parse_mode="HTML")
        return

    # Cancel previous tag task if running
    task_key = (bot_info.id, chat_id)
    prev_task = ACTIVE_TAG_TASKS.pop(task_key, None) or ACTIVE_TAG_TASKS.pop(chat_id, None)
    if prev_task and not prev_task.done():
        prev_task.cancel()

    # 2. Collect distinct group members / active players from ALL sources
    def _collect_group_members():
        members_map = {}

        # 1. Historical players in games for this group
        players_qs = Player.objects.filter(game__chat_id=chat_id).values('telegram_user_id', 'display_name', 'username').distinct()
        for p in players_qs:
            uid = p['telegram_user_id']
            uname = p['username'] or ''
            if uid and uid != bot_info.id and uid not in (777000, 1087968824) and not uname.lower().endswith('bot'):
                members_map[uid] = {
                    'telegram_user_id': uid,
                    'display_name': p['display_name'] or uname or "O'yinchi",
                    'username': uname,
                    'is_bot': False
                }

        # 2. BotGroup owner
        from apps.bots.models import BotGroup, BotUser
        bg_qs = BotGroup.objects.filter(chat_id=chat_id).values('owner_telegram_id', 'owner_name', 'owner_username')
        for bg in bg_qs:
            ouid = bg['owner_telegram_id']
            ouname = bg['owner_username'] or ''
            if ouid and ouid != bot_info.id and ouid not in (777000, 1087968824) and not ouname.lower().endswith('bot'):
                if ouid not in members_map:
                    members_map[ouid] = {
                        'telegram_user_id': ouid,
                        'display_name': bg['owner_name'] or ouname or "Guruh Egasi",
                        'username': ouname,
                        'is_bot': False
                    }

        # 3. Tracked in-memory users seen in group
        if chat_id in GROUP_TRACKED_USERS:
            for uid, info in GROUP_TRACKED_USERS[chat_id].items():
                if uid not in members_map and not info.get('is_bot') and uid not in (bot_info.id, 777000, 1087968824):
                    members_map[uid] = info

        # 4. BotUser records for this bot
        if bot_record:
            bu_qs = BotUser.objects.filter(bot=bot_record).values('telegram_id', 'first_name', 'last_name', 'username')[:300]
            for bu in bu_qs:
                buid = bu['telegram_id']
                buname = bu['username'] or ''
                if buid and buid != bot_info.id and buid not in (777000, 1087968824) and not buname.lower().endswith('bot'):
                    if buid not in members_map:
                        full_name = f"{bu['first_name'] or ''} {bu['last_name'] or ''}".strip()
                        members_map[buid] = {
                            'telegram_user_id': buid,
                            'display_name': full_name or buname or "O'yinchi",
                            'username': buname,
                            'is_bot': False
                        }

        # 5. Other players on this bot
        if bot_record:
            bot_players_qs = Player.objects.filter(game__bot=bot_record).values('telegram_user_id', 'display_name', 'username').distinct()[:200]
            for bp in bot_players_qs:
                bpuid = bp['telegram_user_id']
                bpuname = bp['username'] or ''
                if bpuid and bpuid != bot_info.id and bpuid not in (777000, 1087968824) and not bpuname.lower().endswith('bot'):
                    if bpuid not in members_map:
                        members_map[bpuid] = {
                            'telegram_user_id': bpuid,
                            'display_name': bp['display_name'] or bpuname or "O'yinchi",
                            'username': bpuname,
                            'is_bot': False
                        }

        # 6. Active PlayerProfiles if list is small
        if len(members_map) < 30:
            from apps.stats.models import PlayerProfile
            profiles = PlayerProfile.objects.all().order_by('-created_at')[:100]
            for prof in profiles:
                puid = prof.telegram_id
                puname = prof.telegram_username or ''
                if puid and puid != bot_info.id and puid not in (777000, 1087968824) and not puname.lower().endswith('bot'):
                    if puid not in members_map:
                        members_map[puid] = {
                            'telegram_user_id': puid,
                            'display_name': prof.full_name or puname or "O'yinchi",
                            'username': puname,
                            'is_bot': False
                        }

        return members_map

    members_dict = await sync_to_async(_collect_group_members)()

    # Also collect administrators from Telegram chat
    try:
        admins = await bot.get_chat_administrators(chat_id=chat_id)
        for a in admins:
            if not a.user.is_bot and a.user.id not in (777000, 1087968824, bot_info.id):
                uname = a.user.username or ''
                if not uname.lower().endswith('bot'):
                    members_dict[a.user.id] = {
                        'telegram_user_id': a.user.id,
                        'display_name': a.user.full_name or a.user.first_name or "Admin",
                        'username': uname,
                        'is_bot': False
                    }
    except Exception as e:
        logger.warning(f"Error fetching administrators for @utag: {e}")

    members_list = list(members_dict.values())
    if not members_list:
        await message.reply("ℹ️ Guruhda chaqirish uchun a'zolar topilmadi.")
        return

    random.shuffle(members_list)
    try:
        await message.reply(f"📢 <b>Guruh a'zolarini chaqirish boshlandi!</b> (Jami: {len(members_list)} ta a'zo)\n<i>(To'xtatish uchun: <code>@stop</code> yozing)</i>", parse_mode="HTML")
    except Exception:
        pass

    async def _tag_loop():
        try:
            for m in members_list:
                if task_key not in ACTIVE_TAG_TASKS and chat_id not in ACTIVE_TAG_TASKS:
                    break
                uid = m.get('telegram_user_id')
                if not uid or m.get('is_bot') or uid in (bot_info.id, 777000, 1087968824):
                    continue

                phrase = random.choice(UTAG_CREATIVE_PHRASES)
                if m.get('username'):
                    uname_clean = str(m['username']).lstrip('@')
                    tag_str = f"@{uname_clean}"
                else:
                    name_esc = html.escape(str(m.get('display_name') or "O'yinchi"))
                    tag_str = f'<a href="tg://user?id={uid}">{name_esc}</a>'

                text = f"{tag_str} {phrase}"

                # Robust message sending with Flood Control retry and BadRequest recovery
                for attempt in range(3):
                    if task_key not in ACTIVE_TAG_TASKS and chat_id not in ACTIVE_TAG_TASKS:
                        break
                    try:
                        await bot.send_message(chat_id, text, parse_mode="HTML")
                        break
                    except TelegramRetryAfter as flood:
                        logger.warning(f"Telegram flood control in utag (chat {chat_id}): sleeping {flood.retry_after + 1}s")
                        await asyncio.sleep(flood.retry_after + 1)
                    except TelegramBadRequest as br_err:
                        logger.debug(f"HTML error in utag, falling back to plain text: {br_err}")
                        try:
                            plain_tag = f"@{str(m['username']).lstrip('@')}" if m.get('username') else str(m.get('display_name') or "O'yinchi")
                            await bot.send_message(chat_id, f"{plain_tag} {phrase}")
                        except Exception:
                            pass
                        break
                    except TelegramForbiddenError:
                        logger.warning(f"Bot forbidden in chat {chat_id} during utag")
                        return
                    except Exception as send_err:
                        logger.warning(f"Error sending utag message for user {uid} (attempt {attempt+1}): {send_err}")
                        await asyncio.sleep(1.0)

                await asyncio.sleep(1.2)

            # Check if all completed naturally without cancellation
            if task_key in ACTIVE_TAG_TASKS or chat_id in ACTIVE_TAG_TASKS:
                try:
                    await bot.send_message(
                        chat_id,
                        f"✅ <b>Guruh a'zolarini chaqirish yakunlandi!</b> (Jami: {len(members_list)} ta a'zo)",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
        except asyncio.CancelledError:
            logger.info(f"Utag task cancelled for chat {chat_id}")
        except Exception as loop_err:
            logger.exception(f"Unexpected error in _tag_loop for chat {chat_id}: {loop_err}")
        finally:
            ACTIVE_TAG_TASKS.pop(task_key, None)
            ACTIVE_TAG_TASKS.pop(chat_id, None)

    task = asyncio.create_task(_tag_loop())
    ACTIVE_TAG_TASKS[task_key] = task
    ACTIVE_TAG_TASKS[chat_id] = task


@router.message(Command("cabinet", "kabinet", "settings", "sozlamalar", ignore_case=True))
async def cmd_group_cabinet_info(message: types.Message, bot: Bot):
    """Provides group cabinet login, password, and direct Mini App WebApp link."""
    if message.chat.type == "private":
        await message.answer("⚠️ Guruh kabineti ma'lumotlari guruhlar uchun mo'ljallangan. Meni guruhingizga qo'shing va guruhda <code>/cabinet</code> deb yozing.", parse_mode="HTML")
        return

    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else 0
    bot_info = await bot.get_me()
    
    bot_record = await sync_to_async(
        lambda: BotModel.objects.filter(
            Q(telegram_bot_id=bot.id) | Q(telegram_username__iexact=bot_info.username)
        ).first()
    )()
    if not bot_record:
        bot_record = await sync_to_async(BotModel.objects.first)()

    await sync_group_info(bot, message.chat, bot_record)

    from apps.bots.models import BotGroup
    group = await sync_to_async(
        lambda: BotGroup.objects.filter(chat_id=chat_id).first()
    )()

    if not group:
        await message.reply("⚠️ Guruh ma'lumotlari topilmadi.")
        return

    # Check admin permission
    allowed, err_msg = await check_user_group_permission(bot, chat_id, user_id, required_level='ADMINS')
    if not allowed:
        await message.reply("⚠️ Guruh kabineti ma'lumotlarini faqat <b>guruh adminlari yoki guruh egasi</b> ko'rishi mumkin.", parse_mode="HTML")
        return

    webapp_base = getattr(settings, 'WEBAPP_BASE_URL', '') or 'https://api.bloodymafia.uz'
    webapp_url = f"{webapp_base}/webapp/profile/?tg_id={user_id}&tab=group&group_id={group.id}"

    text = (
        f"👥 <b>Guruh Boshqaruv Kabineti</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🏛 <b>Guruh:</b> {html.escape(group.title)}\n"
        f"🤖 <b>Bot:</b> @{bot_info.username}\n\n"
        f"🔑 <b>Kabinet Logini:</b> <code>{group.cabinet_login}</code>\n"
        f"🔒 <b>Kabinet Paroli:</b> <code>{group.cabinet_password}</code>\n\n"
        f"⚙️ <i>Mini App orqali guruh sozlamalari, o'yinchi yig'ish vaqti, tun va ovoz berish vaqtlari hamda buyruqlar ruxsatini boshqarishingiz mumkin:</i>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Guruh Kabinetiga Kirish 🚀", web_app=WebAppInfo(url=webapp_url))]
    ])

    await message.reply(text, reply_markup=kb, parse_mode="HTML")


@router.my_chat_member()
async def handle_bot_chat_member_update(event: types.ChatMemberUpdated, bot: Bot):
    """Triggered whenever bot is added to a group or its administrator status changes."""
    if event.chat.type not in ["group", "supergroup"]:
        return
    try:
        new_status = event.new_chat_member.status
        bot_info = await bot.get_me()
        bot_record = await sync_to_async(
            lambda: BotModel.objects.filter(
                Q(telegram_bot_id=bot.id) | Q(telegram_username__iexact=bot_info.username)
            ).first()
        )()
        if bot_record:
            await sync_group_info(bot, event.chat, bot_record)

        if new_status in ['member', 'restricted']:
            bot_name = bot_info.first_name or "Mafia Bot"
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="➕ Botga Adminlik berish 👑",
                        url=f"https://t.me/{bot_info.username}?startgroup=admin"
                    )
                ]
            ])
            await bot.send_message(
                chat_id=event.chat.id,
                text=(
                    f"👋 <b>Assalomu alaykum!</b>\n"
                    f"Men <b>{html.escape(bot_name)}</b> botiman 🎭\n\n"
                    f"⚠️ Guruhda o'yinlarni bekamu-ko'st o'tkazishim (o'yin xabarlarini pin qilish, sukut rejimini yoqish va rollarni tarqatish) uchun menga <b>Guruh Administratori</b> huquqlarini bering! 👑\n\n"
                    f"<i>Admin huquqi berilgach, /game buyrug'ini yuboring.</i>"
                ),
                reply_markup=kb,
                parse_mode="HTML"
            )
        elif new_status == 'administrator':
            await bot.send_message(
                chat_id=event.chat.id,
                text=(
                    f"🎉 <b>Rahmat! Menga administratorlik huquqi berildi.</b>\n\n"
                    f"Endi bemalol <b>/game</b> buyrug'i orqali qizg'in Mafiya o'yinlarini boshlashingiz mumkin! 🚀\n"
                    f"<i>Guruh sozlamalari va kabinet: /cabinet</i>"
                ),
                parse_mode="HTML"
            )
    except Exception as e:
        logger.debug(f"Error in handle_bot_chat_member_update: {e}")



