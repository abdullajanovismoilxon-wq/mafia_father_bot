"""
MAFIA BOT FATHER — Night Phase Handlers (Full 21 Roles Game Loop)
==================================================================
- Full support for all 21 Mafia roles
- Mafia PM relay chat (all living Mafia team members: Don, Mafia, Advokat, Ubiytsa, Kimyogar)
- Police PM relay chat (living Komissar and Serjant)
- Joker bomb plant & victim box guess
- Zombie bite & Vaccine cure prompt
- AFK inactivity elimination announcements
- Dynamic succession (Don -> Mafia, Komissar -> Serjant, Doctor -> Hamshira)
"""
import html
import asyncio
import logging
import random
from typing import Any, Optional, Dict, List, Set, Tuple
from aiogram import Router, Bot, F, types
from aiogram.types import CallbackQuery, Message
from asgiref.sync import sync_to_async
from django.db.models import Q
from django.conf import settings
from apps.stats.models import PlayerProfile
from apps.games.models import Game, Player, NightActionType, GamePhase, RoleTeam, Role
from apps.games.engine.actions import NightActionService, ActionValidationError
from apps.games.engine.game_service import GameService
from apps.games.engine.resolution import GameResolutionService
from apps.games.engine.win_conditions import WinConditionService
from apps.superadmin.services import SettingService, TextService
from bot_runtime.keyboards.inline import (
    build_voting_keyboard,
    build_bot_pm_keyboard,
    build_back_to_group_keyboard,
    build_night_target_keyboard,
    build_komissar_action_keyboard,
    build_hanging_keyboard,
    build_joker_boxes_setup_keyboard,
    build_joker_guess_keyboard,
    build_vaksina_prompt_keyboard,
    _player_team_badge,
    _player_health_badge,
    _short,
)

logger = logging.getLogger(__name__)
router = Router(name="night_router")

# In-memory stores
KOMISSAR_RESULTS: dict = {}
NIGHT_TASKS: dict = {}
LAST_WORDS_PENDING: dict = {}
GAME_ID_MAP: dict = {}
PLAYER_ID_MAP: dict = {}
JOKER_TEMP_BOXES: dict = {}  # {game_id: {user_id: [1, 2]}}
VOTING_TASKS: dict = {}
ADVANCING_NIGHT_GAMES: set = set()

ROLE_ICONS = {
    "DON": "🤵🏻",
    "MAFIA": "🤵🏼",
    "DOCTOR": "👨🏼‍⚕️",
    "SHIFOKOR": "👨🏼‍⚕️",
    "DOKTOR": "👨🏼‍⚕️",
    "DETECTIVE": "🕵🏻‍♂️",
    "KOMISSAR": "🕵🏻‍♂️",
    "SHERIFF": "🕵🏻‍♂️",
    "CITIZEN": "👨🏼",
    "TINCH AHOLI": "👨🏼",
    "FUQARO": "👨🏼",
    "SERJANT": "👮🏼‍♂️",
    "HAMSHIRA": "👩🏼‍⚕️",
    "OMADLI": "🤞🏼",
    "JANOB": "🎖",
    "SOTQIN": "🤓",
    "ADMIRAL": "🧑🏻‍✈️",
    "ROBINGUD": "🏹",
    "ROBIN GUD": "🏹",
    "FOTOPARATCHI": "📸",
    "DAYDI": "🍾",
    "KEZUVCHI": "💃",
    "ADVOKAT": "💼",
    "UBIYTSA": "🥷",
    "YOLLANMA QOTIL": "🥷",
    "JURNALIST": "👩🏼‍💻",
    "AYGOQCHI": "🦇",
    "LABORANT": "👩‍🔬",
    "KIMYOGAR": "🧪",
    "RAIS": "💰",
    "MER": "💰",
    "BORI": "🐺",
    "BO'RI": "🐺",
    "AFERIST": "🤹🏻",
    "GAZABKOR": "🧌",
    "SEHRGAR": "🧙‍♂️",
    "QOTIL": "🔪",
    "MANIAK": "🔪",
    "KONCHI": "⛏",
    "QAROQCHI": "🏴‍☠️",
    "QORBOBO": "🎅🏻",
    "OSHPAZ": "👨🏼‍🍳",
    "AFSUNGAR": "🔮",
    "TUZOQCHI": "🕸",
    "AXMOQ": "🤪",
    "BUQALAMUN": "🦎",
    "JOKER": "🃏",
    "SUIDSID": "🤡",
    "SUITSID": "🤡",
    "ZOMBI": "🧟",
    "KUPIDON": "💘",
    "KAMIKADZE": "🧨",
    "LIDER": "👑",
    "KOLDUN": "⚡",
}

ROLE_LABELS = {
    "DON": "Don",
    "MAFIA": "Mafia",
    "DOCTOR": "Shifokor",
    "SHIFOKOR": "Shifokor",
    "DOKTOR": "Shifokor",
    "DETECTIVE": "Komissar",
    "KOMISSAR": "Komissar",
    "SHERIFF": "Komissar",
    "CITIZEN": "Tinch aholi",
    "TINCH AHOLI": "Tinch aholi",
    "FUQARO": "Tinch aholi",
    "SERJANT": "Serjant",
    "HAMSHIRA": "Hamshira",
    "OMADLI": "Omadli",
    "JANOB": "Janob",
    "SOTQIN": "Sotqin",
    "ADMIRAL": "Admiral",
    "ROBINGUD": "Robin Gud",
    "ROBIN GUD": "Robin Gud",
    "FOTOPARATCHI": "Fotoparatchi",
    "DAYDI": "Daydi",
    "KEZUVCHI": "Kezuvchi",
    "ADVOKAT": "Advokat",
    "UBIYTSA": "Ubiytsa",
    "YOLLANMA QOTIL": "Ubiytsa",
    "JURNALIST": "Jurnalist",
    "AYGOQCHI": "Ayg'oqchi",
    "LABORANT": "Laborant",
    "KIMYOGAR": "Kimyogar",
    "RAIS": "Rais",
    "MER": "Rais",
    "BORI": "Bo'ri",
    "BO'RI": "Bo'ri",
    "AFERIST": "Aferist",
    "GAZABKOR": "G'azabkor",
    "SEHRGAR": "Sehrgar",
    "QOTIL": "Qotil",
    "MANIAK": "Qotil",
    "KONCHI": "Konchi",
    "QAROQCHI": "Qaroqchi",
    "QORBOBO": "Qorbobo",
    "OSHPAZ": "Oshpaz",
    "AFSUNGAR": "Afsungar",
    "TUZOQCHI": "Tuzoqchi",
    "AXMOQ": "Axmoq",
    "BUQALAMUN": "Buqalamun",
    "HAMSHIRA": "Hamshira",
    "JOKER": "Joker",
    "SUIDSID": "Suidsid",
    "SUITSID": "Suidsid",
    "ZOMBI": "Zombi",
}


def role_icon(name: str) -> str:
    if not name:
        return "👤"
    normalized = str(name).strip().upper()
    if normalized in ROLE_ICONS:
        return ROLE_ICONS[normalized]
    for k, icon in ROLE_ICONS.items():
        if k in normalized or normalized in k:
            return icon
    return "👤"


def role_label(name: str) -> str:
    if not name:
        return ""
    normalized = str(name).strip().upper()
    return ROLE_LABELS.get(normalized, name)


def _register_ids(game_id: str, players: list):
    GAME_ID_MAP[_short(game_id)] = str(game_id)
    for p in players:
        pid = str(p.id)
        PLAYER_ID_MAP[_short(pid)] = pid


async def _resolve_player_id(game, short_pid: str) -> str:
    if short_pid in PLAYER_ID_MAP:
        return PLAYER_ID_MAP[short_pid]
    players = await sync_to_async(lambda: list(game.players.all()))()
    for p in players:
        if str(p.id).startswith(short_pid):
            return str(p.id)
    return short_pid


async def _resolve_game_id(short_gid: str) -> str:
    if short_gid in GAME_ID_MAP:
        return GAME_ID_MAP[short_gid]
    games = await sync_to_async(
        lambda: list(Game.objects.filter(
            phase__in=[GamePhase.NIGHT, GamePhase.DAY, GamePhase.DISCUSSION,
                       GamePhase.VOTING, GamePhase.STARTING]
        ).values_list('id', flat=True))
    )()
    for gid in games:
        if str(gid).startswith(short_gid):
            return str(gid)
    return short_gid


async def _expire_last_words(user_id: int):
    duration = await sync_to_async(SettingService.get_int)('last_words_duration', 50)
    await asyncio.sleep(duration)
    LAST_WORDS_PENDING.pop(user_id, None)


# ---------------------------------------------------------------------------
# CORE: Night timer & Phase transition
# ---------------------------------------------------------------------------

async def run_night_timer(game_id: str, bot: Any, night_duration: int = 60):
    """Waits night_duration seconds (respecting custom GroupCabinet setting) then advances Night → Dawn."""
    try:
        # Dynamically fetch group-level custom duration if game exists
        try:
            g = await sync_to_async(lambda: Game.objects.select_related('bot').filter(id=game_id).first())()
            if g:
                from apps.superadmin.services import SettingService
                bot_id_str = str(g.bot_id) if getattr(g, 'bot_id', None) else ''
                night_duration = await sync_to_async(SettingService.get_group_or_bot_timing)(
                    g.chat_id, bot_id_str, 'night_duration', int(night_duration) if night_duration else 60
                )
        except Exception:
            pass

        if not isinstance(night_duration, (int, float)):
            try:
                night_duration = int(night_duration)
            except Exception:
                night_duration = 60

        logger.info(f"⏳ Running night timer for game {game_id}: {night_duration}s")
        await asyncio.sleep(night_duration)

        game = await sync_to_async(
            lambda: Game.objects.select_related('bot').get(id=game_id)
        )()
        if game.phase != GamePhase.NIGHT:
            logger.info(f"Night timer for game {game_id} expired, but phase is {game.phase}. Skipping.")
            return

        await advance_night_to_day(game, bot)

    except asyncio.CancelledError:
        logger.info(f"Night timer for game {game_id} cancelled.")
    except Exception as e:
        logger.exception(f"Error in run_night_timer for game {game_id}: {e}")


def cancel_night_timer(game_id: str):
    task = NIGHT_TASKS.pop(game_id, None)
    if task and not task.done():
        try:
            curr = asyncio.current_task()
            if curr is None or curr != task:
                task.cancel()
        except Exception:
            pass

def start_night_timer(game_id: str, bot: Any, duration: int = 60, **kwargs):
    # Detect swapped arguments if any
    actual_bot = bot
    actual_duration = duration
    if isinstance(bot, (int, float)) and hasattr(duration, 'send_message'):
        actual_bot = duration
        actual_duration = int(bot)
    elif not isinstance(actual_duration, (int, float)):
        try:
            actual_duration = int(actual_duration)
        except Exception:
            actual_duration = 60

    cancel_night_timer(game_id)
    new_task = asyncio.create_task(run_night_timer(game_id, actual_bot, actual_duration))
    NIGHT_TASKS[game_id] = new_task


async def _check_and_advance_night_if_ready(game: Game, bot: Bot):
    """
    Night phase timing is strictly governed by run_night_timer (configured in GroupCabinet / SuperAdmin).
    No early cutoff to ensure exact cabinet configured duration is respected.
    """
    pass


# ---------------------------------------------------------------------------
# Night → Dawn Transition & Group Event Announcements
# ---------------------------------------------------------------------------


async def send_dynamic_animation(
    bot: Bot,
    chat_id: int,
    media_key: str,
    fallback_url: str = "",
    caption: str = "",
    reply_markup=None,
    parse_mode: str = "HTML"
):
    """Sends dynamic GIF, image, video, or Telegram file_id with local disk caching and cross-bot resilience."""
    import os
    import aiohttp
    from aiogram import types
    from django.conf import settings
    from apps.superadmin.services import TextService
    from asgiref.sync import sync_to_async

    # 1. Check local bundled/cached gif file first
    local_gif_path = os.path.join(settings.BASE_DIR, 'media', 'gifs', f"{media_key}.gif")
    if not os.path.exists(local_gif_path):
        alt_key = media_key.replace('gif_', '')
        alt_path = os.path.join(settings.BASE_DIR, 'media', 'gifs', f"{alt_key}.gif")
        if os.path.exists(alt_path):
            local_gif_path = alt_path

    # 2. Fetch live value from SuperAdmin database
    media_val = await sync_to_async(TextService.get_text)(media_key, fallback=fallback_url)
    media_val = media_val.strip() if media_val else ""
    if not media_val and fallback_url:
        media_val = fallback_url.strip()

    # If media_val points to an uploaded local file
    custom_local = None
    if media_val and '/media/uploads/' in media_val:
        fname = media_val.split('/media/uploads/')[-1].split('?')[0]
        fpath = os.path.join(settings.MEDIA_ROOT, 'uploads', fname)
        if os.path.exists(fpath):
            custom_local = fpath
    elif media_val and os.path.isabs(media_val) and os.path.exists(media_val):
        custom_local = media_val

    target_local = custom_local or (local_gif_path if os.path.exists(local_gif_path) else None)

    # If we have a verified local file, send it via FSInputFile (instant, 100% reliable)
    if target_local:
        try:
            target = types.FSInputFile(target_local)
            ext = os.path.splitext(target_local)[1].lower()
            if ext in ['.jpg', '.jpeg', '.png', '.webp']:
                return await bot.send_photo(chat_id=chat_id, photo=target, caption=caption, reply_markup=reply_markup, parse_mode=parse_mode)
            elif ext in ['.mp4', '.mov', '.webm']:
                return await bot.send_video(chat_id=chat_id, video=target, caption=caption, reply_markup=reply_markup, parse_mode=parse_mode)
            else:
                return await bot.send_animation(chat_id=chat_id, animation=target, caption=caption, reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception as e:
            logger.warning(f"Error sending local media file {target_local}: {e}")

    # If it's a URL and we don't have it on disk yet
    if media_val and (media_val.startswith('http://') or media_val.startswith('https://')):
        # Try downloading and caching to disk
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(media_val, timeout=aiohttp.ClientTimeout(total=2.5)) as resp:
                    if resp.status == 200:
                        content_bytes = await resp.read()
                        os.makedirs(os.path.dirname(local_gif_path), exist_ok=True)
                        with open(local_gif_path, 'wb') as f:
                            f.write(content_bytes)
                        target = types.FSInputFile(local_gif_path)
                        return await bot.send_animation(chat_id=chat_id, animation=target, caption=caption, reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception as dl_err:
            logger.debug(f"Download for {media_key} failed or timed out: {dl_err}")

        # Try sending URL directly
        try:
            return await bot.send_animation(
                chat_id=chat_id,
                animation=media_val,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        except Exception as url_err:
            logger.warning(f"Direct URL send failed for {media_key}: {url_err}")

    elif media_val:
        # Telegram File ID
        try:
            return await bot.send_animation(
                chat_id=chat_id,
                animation=media_val,
                caption=caption,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        except Exception as file_id_err:
            logger.warning(f"Send by File ID failed for {media_key}: {file_id_err}")

    # Fallback if local file exists
    if os.path.exists(local_gif_path):
        try:
            target = types.FSInputFile(local_gif_path)
            return await bot.send_animation(chat_id=chat_id, animation=target, caption=caption, reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception:
            pass

    # Final fallback: text message
    try:
        return await bot.send_message(
            chat_id=chat_id,
            text=caption,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
    except Exception:
        return None


async def advance_night_to_day(game: Game, bot: Bot):
    """Processes night actions via GameResolutionService and announces dawn results."""
    game_id = str(game.id)
    if game_id in ADVANCING_NIGHT_GAMES:
        logger.info(f"Game {game_id} is already advancing night to day. Skipping duplicate call.")
        return
    ADVANCING_NIGHT_GAMES.add(game_id)
    try:
        cancel_night_timer(game_id)
        from bot_runtime.manager import BotRuntimeManager
        bot = BotRuntimeManager.get_bot_for_game(game, bot)

        game = await sync_to_async(Game.objects.select_related('bot').get)(id=game_id)
        if game.phase != GamePhase.NIGHT:
            return

        # 1. Resolve all night actions
        night_result = await sync_to_async(GameResolutionService.resolve_night_phase)(game)

        # 2. Advance Game Phase to DAY
        await sync_to_async(GameService.advance_phase)(game, GamePhase.DAY)
        game = await sync_to_async(Game.objects.select_related('bot').get)(id=game_id)

        eliminated_list = night_result.get('eliminated_players', [])
        afk_list = night_result.get('afk_eliminated_players', [])

        # --- Dawn Announcement Msg 1 (with dynamic Dawn GIF) ---
        try:
            dawn_msg1 = await sync_to_async(TextService.get_text)(
                'dawn_intro_text',
                fallback="🌅 <b>Tong otdi!</b>\nShahar aholisi uyg'onmoqda..."
            )
            await send_dynamic_animation(
                bot=bot,
                chat_id=game.chat_id,
                media_key='gif_dawn',
                fallback_url="https://media.giphy.com/media/l41JGlWa1xOjJSsV2/giphy.gif",
                caption=dawn_msg1,
                parse_mode="HTML"
            )
        except Exception as d1_err:
            logger.warning(f"Dawn msg 1 failed: {d1_err}")

        await asyncio.sleep(1.0)

        # --- Dawn Announcement Msg 2: Casualties & Saves ---
        eliminated_list = night_result.get('eliminated_players', [])
        afk_list = night_result.get('afk_eliminated_players', [])

        death_lines = []
        for el in eliminated_list:
            p = el['player'] if isinstance(el, dict) else el
            rname = el['role_name'] if isinstance(el, dict) else (p.role.name if p.role else 'CITIZEN')
            ktype = el.get('killer_type', 'mafia') if isinstance(el, dict) else 'mafia'
            icon = role_icon(rname)
            label = role_label(rname)
            target_mention = f'<a href="tg://user?id={p.telegram_user_id}">{html.escape(p.display_name)}</a>'

            if ktype == 'tuzoqchi':
                tpl = await sync_to_async(TextService.get_text)('dawn_death_tuzoq', fallback="🕸 {target_name} tuzoqqa ilinib halok bo'ldi!\nU: {role_icon} {role_name} edi.")
            elif ktype == 'afsungar':
                tpl = await sync_to_async(TextService.get_text)('dawn_death_afsungar', fallback="🧙🏼 Afsungarga hujum qilgan {target_name} o'z la'nati qurboni bo'ldi!\nU: {role_icon} {role_name} edi.")
            elif ktype == 'komissar_retaliate':
                tpl = await sync_to_async(TextService.get_text)('dawn_death_ubiytsa_retaliate', fallback="🥷 Komissarga suiqasd qilmoqchi bo'lgan Ubiytsa {target_name} otib o'ldirildi!\nU: {role_icon} {role_name} edi.")
            elif ktype == 'kimyogar_poison':
                tpl = await sync_to_async(TextService.get_text)('dawn_death_kimyogar', fallback="🧪 {target_name} Kimyogarning zaharli eliksiridan halok bo'ldi!\nU: {role_icon} {role_name} edi.")
            elif ktype == 'axmoq_headbutt':
                tpl = await sync_to_async(TextService.get_text)('dawn_death_axmoq', fallback="🤪 {target_name} Axmoqning kalla zarbasidan halok bo'ldi!\nU: {role_icon} {role_name} edi.")
            elif ktype == 'qotil':
                tpl = await sync_to_async(TextService.get_text)('dawn_death_qotil', fallback="🔪 {target_name} shafqatsiz Qotil tomonidan o'ldirildi.\nU: {role_icon} {role_name} edi.")
            elif ktype == 'komissar':
                tpl = await sync_to_async(TextService.get_text)('dawn_death_komissar', fallback="🔫 {target_name} Komissar tomonidan otib o'ldirildi.\nU: {role_icon} {role_name} edi.")
            else:
                tpl = await sync_to_async(TextService.get_text)('dawn_death_mafia', fallback="🩸 {target_name} Mafiyalar tomonidan vahshiylarcha o'ldirildi.\nU: {role_icon} {role_name} edi.")

            death_lines.append(
                tpl.replace('{target_name}', target_mention)
                .replace('{role_icon}', icon)
                .replace('{role_name}', label)
            )

        if death_lines:
            dawn_msg2 = "\n\n".join(death_lines)
        elif night_result.get('shield_saved_players'):
            dawn_msg2 = "🛡 <b>Tunda kimdir shaxsiy himoya qalqoni tufayli o'limdan omon qoldi!</b>\nHech kim qurbon bo'lmadi."
        elif night_result.get('doctor_saved_players'):
            dawn_msg2 = "🩺 <b>Ishonish qiyin!</b> Lekin, bu tunda hech kim o'lmadi...\nShifokor kimnidir o'limdan qutqardi!"
        else:
            dawn_msg2 = "😴 <b>Bu tun tinch o'tdi.</b> Hech kim qurbon bo'lmadi."

        try:
            await bot.send_message(game.chat_id, dawn_msg2, parse_mode="HTML")
        except Exception as e:
            logger.warning(f"Dawn msg 2 failed: {e}")

        # --- AFK Announcements ---
        for afk_p in afk_list:
            rname = afk_p.role.name if afk_p.role else "CITIZEN"
            icon = role_icon(rname)
            label = role_label(rname)
            p_mention = f'<a href="tg://user?id={afk_p.telegram_user_id}">{html.escape(afk_p.display_name)}</a>'
            afk_msg = (
                f"💤 Aholidan kimdir {icon} {label} {p_mention} o'limidan oldin:\n"
                f'"Men o\'yin paytida boshqa uxlamayma-a-a-a-a-a-an!" - deb qichqirganini eshitgan.'
            )
            try:
                await bot.send_message(game.chat_id, afk_msg, parse_mode="HTML")
                await bot.send_message(afk_p.telegram_user_id, "⚠️ Siz 2 kun hech narsa qilmadingiz va o'yindan chetlatildingiz.")
            except Exception:
                pass

        # --- Shield Saves Notification to Players in PM ---
        shield_saved = night_result.get('shield_saved_players', [])
        for sp in shield_saved:
            try:
                await bot.send_message(
                    sp.telegram_user_id,
                    "🛡 <b>Inventaringizdagi 'Tungi himoya' ishlatildi!</b>\n\n"
                    "Bu tunda sizga suiqasd uyushtirilgan edi. Shaxsiy himoya qalqoningiz ishga tushib, sizni o'limdan saqlab qoldi!",
                    parse_mode="HTML"
                )
            except Exception:
                pass

        # --- Visited Players PM Notifications (Shifokor, Kezuvchi, Daydi, Advokat, Kimyogar) ---
        for doc_p in night_result.get('doctor_visited_players', []):
            if doc_p.is_alive:
                try:
                    await bot.send_message(
                        doc_p.telegram_user_id,
                        "👨🏼‍⚕️ <b>Shifokor siznikiga mehmonga keldi!</b>\n"
                        "U sizni tekshirib, xavfsizligingizni ta'minlab ketdi.",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

        for kez_p in night_result.get('kezuvchi_visited_players', []):
            if kez_p.is_alive:
                try:
                    await bot.send_message(
                        kez_p.telegram_user_id,
                        "💃 <b>Kezuvchi siznikiga mehmonga keldi!</b>\n"
                        "Siz bu tunda hech qanday amal bajara olmaysiz va bugungi kunduzgi ovoz berishda qatnasha olmaysiz.",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

        for day_p in night_result.get('daydi_visited_players', []):
            if day_p.is_alive:
                try:
                    await bot.send_message(
                        day_p.telegram_user_id,
                        "🍾 <b>Bu tunda mast Daydi siznikiga mehmonga keldi!</b>\n"
                        "Eshigingizni taqillatib, ichkilik so'rab ketdi.",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

        for adv_p in night_result.get('advokat_visited_players', []):
            if adv_p.is_alive:
                try:
                    await bot.send_message(
                        adv_p.telegram_user_id,
                        "💼 <b>Advokat siznikiga tashrif buyurdi!</b>\n"
                        "Komissar tekshiruvidan sizni himoyalash uchun qonuniy choralar ko'rib qo'ydi.",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

        for kim_p in night_result.get('kimyogar_healed_players', []):
            if kim_p.is_alive:
                try:
                    await bot.send_message(
                        kim_p.telegram_user_id,
                        "🧪 <b>Kimyogar siznikiga mehmonga keldi!</b>\n"
                        "Sizga shifobaxsh eliksir ichirib, sog'lig'ingizni tiklab ketdi.",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

        # --- Doridan himoya PM Notification ---
        for dp in night_result.get('dori_shield_saved_players', []):
            try:
                await bot.send_message(
                    dp.telegram_user_id,
                    "💊 <b>Inventaringizdagi 'Doridan himoya' ishlatildi!</b>\n\n"
                    "Bu tunda Kezuvchi siznikiga kelib dori bermoqchi bo'ldi. Ammo inventaringizdagi Doridan himoya qalqoni tufayli dori ta'sir qilmadi va siz bloklanmadingiz!",
                    parse_mode="HTML"
                )
            except Exception:
                pass

        # --- Fake Document (Hujjat) PM Notification ---
        for hp in night_result.get('hujjat_used_players', []):
            try:
                await bot.send_message(
                    hp.telegram_user_id,
                    "📁 <b>Inventaringizdagi 'Hujjatlar' (soxta hujjat) ishlatildi!</b>\n\n"
                    "Bu tunda Komissar sizni tekshirdi. Soxta hujjatingiz tufayli u sizni Tinch aholi deb o'yladi va siz fosh bo'lmadingiz!",
                    parse_mode="HTML"
                )
            except Exception:
                pass

        # --- Daydi Clues Delivery ---
        daydi_results = night_result.get('daydi_results', [])
        for dr in daydi_results:
            try:
                await bot.send_message(dr['daydi_user_id'], dr['message'], parse_mode="HTML")
            except Exception:
                pass

        # --- Sotqin Snitches (Group Anonymous Broadcast) ---
        sotqin_snitches = night_result.get('sotqin_snitches', [])
        for snitched_p in sotqin_snitches:
            try:
                snitch_mention = f'<a href="tg://user?id={snitched_p.telegram_user_id}">{html.escape(snitched_p.display_name)}</a>'
                await bot.send_message(
                    game.chat_id,
                    f"🤓 <b>Sotqin shaharga xabar tarqatdi!</b>\n\n"
                    f"«Aholiga ma'lum bo'lishicha, {snitch_mention} shubhali qora niyatli kimsalar (Mafiya/Qotil) bilan aloqador!»",
                    parse_mode="HTML"
                )
            except Exception:
                pass

        # --- Fotoparatchi Snaps (Group Anonymous Broadcast) ---
        fotoparatchi_snaps = night_result.get('fotoparatchi_snaps', [])
        for snap in fotoparatchi_snaps:
            try:
                p_visitor, p_host = snap
                v_mention = f'<a href="tg://user?id={p_visitor.telegram_user_id}">{html.escape(p_visitor.display_name)}</a>'
                h_mention = f'<a href="tg://user?id={p_host.telegram_user_id}">{html.escape(p_host.display_name)}</a>'
                await bot.send_message(
                    game.chat_id,
                    f"📸 <b>Fotoparatchi tunda shov-shuvli suratga oldi!</b>\n\n"
                    f"Suratda ko'rinishicha, {v_mention} tunda {h_mention} ning xonadoniga mehmonga borgan!",
                    parse_mode="HTML"
                )
            except Exception:
                pass

        # --- Qorbobo Gifts (PM + Group Announcement) ---
        qorbobo_gifts = night_result.get('qorbobo_gifts', [])
        for qg in qorbobo_gifts:
            try:
                await bot.send_message(
                    qg['target_user_id'],
                    f"🎅🏻 <b>Qorbobo sizga maxsus sovg'a ulashdi!</b>\n\n"
                    f"🎁 Inventaringizga <b>{qg['item_name']}</b> qo'shildi!",
                    parse_mode="HTML"
                )
            except Exception:
                pass
        if qorbobo_gifts:
            try:
                await bot.send_message(
                    game.chat_id,
                    "🎅🏻 <b>Qorbobo qorong'u tunda bir fuqaroning eshigi tagiga ajoyib sovg'a qoldirib ketdi! 🎁</b>",
                    parse_mode="HTML"
                )
            except Exception:
                pass

        # --- Rais Gift Delivery (PM + Group Announcement) ---
        rais_gifts = night_result.get('rais_gifts', [])
        for rg in rais_gifts:
            try:
                dia_text = f" va <b>{rg['diamonds']} 💎 Olmos</b>" if rg.get('diamonds', 0) > 0 else ""
                await bot.send_message(
                    rg['target_user_id'],
                    f"💰 <b>Rais sizga sovg'a ulashdi!</b>\nHisobingizga <b>+{rg['coins']} 💶 Dollar</b>{dia_text} o'tkazildi!",
                    parse_mode="HTML"
                )
            except Exception:
                pass
        if rais_gifts:
            try:
                await bot.send_message(
                    game.chat_id,
                    "💰 <b>Saxiy Rais shahar aholisidan biriga xazinadan pul ulashdi! 💵</b>",
                    parse_mode="HTML"
                )
            except Exception:
                pass

        # --- Qaroqchi Robbery Logs (Group Broadcast) ---
        robbery_logs = night_result.get('robbery_logs', [])
        for rlog in robbery_logs:
            try:
                await bot.send_message(game.chat_id, rlog, parse_mode="HTML")
            except Exception:
                pass

        # --- Konchi Mining Results (PM + Group) ---
        konchi_results = night_result.get('konchi_results', [])
        for kr in konchi_results:
            try:
                if kr['status'] == 'diamond':
                    await bot.send_message(
                        kr['user_id'],
                        f"⛏ <b>Tabriklaymiz!</b> Siz {kr['mine']}-kondan <b>1 💎 Olmos</b> qazib oldingiz!",
                        parse_mode="HTML"
                    )
                    await bot.send_message(
                        game.chat_id,
                        "⛏ <b>Konchi qorong'u konda yaraqlagan qimmatbaho olmos 💎 topib oldi!</b>",
                        parse_mode="HTML"
                    )
                elif kr['status'] == 'money':
                    await bot.send_message(
                        kr['user_id'],
                        f"⛏ <b>Konda omadingiz keldi!</b> Siz {kr['mine']}-kondan <b>+{kr['coins']} 💶 Dollar</b> topdingiz!",
                        parse_mode="HTML"
                    )
                elif kr['status'] == 'saved_by_slip_shield':
                    await bot.send_message(
                        kr['user_id'],
                        f"🛡 <b>Sirpanishdan himoya qalqoni ishga tushdi!</b>\nSiz {kr['mine']}-konda halokatga uchradingiz, ammo himoya qalqoni sizni omon saqlab qoldi!",
                        parse_mode="HTML"
                    )
                elif kr['status'] == 'died':
                    await bot.send_message(
                        kr['user_id'],
                        f"💀 <b>Halokat!</b> Siz {kr['mine']}-konda chuqur jarlikka qulab halok bo'ldingiz!",
                        parse_mode="HTML"
                    )
            except Exception:
                pass

        # --- Oshpaz Dizzy Meals (PM) ---
        oshpaz_feed_players = night_result.get('oshpaz_feed_players', [])
        for op in oshpaz_feed_players:
            if op.is_alive:
                try:
                    await bot.send_message(
                        op.telegram_user_id,
                        "👨🏼‍🍳 <b>Tunda Oshpaz sizga juda mazali, ammo bosh aylantiruvchi taom berib ketdi!</b>\n\n"
                        "Kunduzgi ovoz berishda boshingiz aylanib, ovozingiz tasodifiy boshqa o'yinchiga ketib qolishi mumkin!",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

        # --- Aferist Vote Steal (PM) ---
        aferist_stolen_players = night_result.get('aferist_stolen_players', [])
        for ap in aferist_stolen_players:
            if ap.is_alive:
                try:
                    await bot.send_message(
                        ap.telegram_user_id,
                        "🤹🏻 <b>Tunda Aferist sizning ovozingizni o'g'irlab ketdi!</b>\n\n"
                        "Bugun kunduzgi yig'ilishda siz ovoz bera olmaysiz. Sizning nomingizdan Aferist ovoz beradi!",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

        # --- Aygoqchi Spy Reports (PM) ---
        aygoqchi_spies = night_result.get('aygoqchi_spies', [])
        for a_spy in aygoqchi_spies:
            tgt_name = html.escape(a_spy['target_name'])
            r_ic = role_icon(a_spy['role_name'])
            r_lb = role_label(a_spy['role_name'])
            spy_msg = f"🦇 <b>Ayg'oqchi ma'lumoti:</b>\n{tgt_name} ning shaxsi fosh bo'ldi — u <b>{r_ic} {r_lb}</b>!"
            try:
                await bot.send_message(a_spy['actor_user_id'], spy_msg, parse_mode="HTML")
            except Exception:
                pass

        # --- Jurnalist Reports (PM) ---
        jurnalist_reports = night_result.get('jurnalist_reports', [])
        for jr in jurnalist_reports:
            tgt_name = html.escape(jr['target_name'])
            visitors = jr.get('visitors', [])
            if visitors:
                v_names = ", ".join([html.escape(v.display_name) for v in visitors])
                j_msg = f"👩🏼‍💻 <b>Jurnalist hisoboti:</b>\nTunda {tgt_name} ning xonadoniga mehmonlar kelgani kuzatildi: <b>{v_names}</b>!"
            else:
                j_msg = f"👩🏼‍💻 <b>Jurnalist hisoboti:</b>\nTunda {tgt_name} ning xonadoniga hech kim kelmadi, tinchlik hukm surdi."
            try:
                await bot.send_message(jr['actor_user_id'], j_msg, parse_mode="HTML")
            except Exception:
                pass

        # --- Joker Deliveries (Victim gets box picker PM) ---
        joker_deliveries = night_result.get('joker_deliveries', [])
        for jd in joker_deliveries:
            try:
                kb = build_joker_guess_keyboard(str(game.id))
                await bot.send_message(
                    jd['target_user_id'],
                    "🃏 <b>Joker sizga sovg'a yubordi.</b>\nUlardan birida o'limingiz yashiringan!\nQutilardan birini tanlang:",
                    reply_markup=kb,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"Could not send Joker box prompt: {e}")

        # --- Zombie Infections & Vaccine Prompt ---
        infected_players = night_result.get('infected_players', [])
        from apps.economy.models import Inventory
        for ip in infected_players:
            has_vaccine = await sync_to_async(
                lambda: Inventory.objects.filter(
                    telegram_id=ip.telegram_user_id, item__code='vaksina', is_active=True, quantity__gt=0
                ).exists()
            )()
            if has_vaccine:
                try:
                    kb = build_vaksina_prompt_keyboard(str(game.id))
                    await bot.send_message(
                        ip.telegram_user_id,
                        "🧟 <b>Sizni tunda Zombi tishlab ketdi!</b>\n"
                        "Inventaringizda <b>💉 Vaksina</b> mavjud. Uni ishlatib asil rolingizga qaytmoqchimisiz?",
                        reply_markup=kb,
                        parse_mode="HTML"
                    )
                except Exception:
                    pass
            else:
                try:
                    await bot.send_message(
                        ip.telegram_user_id,
                        "🧟 <b>Sizni tunda Zombi tishlab ketdi!</b>\nEndi siz Zombilar tomonidasiz!",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

        # --- Successions ---
        if night_result.get('new_don'):
            nd = night_result['new_don']
            try:
                await bot.send_message(game.chat_id, "🤵🏻 <b>Mafialardan biri Don bo'ldi!</b>\nO'yin davom etadi...", parse_mode="HTML")
                await bot.send_message(nd.telegram_user_id, "🤵🏻 <b>Siz endi DON siz!</b>\nMafiyalar yetakchisi bo'ldingiz.", parse_mode="HTML")
            except Exception:
                pass

        if night_result.get('new_komissar'):
            nk = night_result['new_komissar']
            try:
                await bot.send_message(game.chat_id, "👮🏼‍♂️ <b>Serjant Komissar lavozimini egalladi!</b>", parse_mode="HTML")
                await bot.send_message(nk.telegram_user_id, "🕵🏻‍♂️ <b>Siz endi KOMISSAR siz!</b>\nShaharni himoya qiling.", parse_mode="HTML")
            except Exception:
                pass

        if night_result.get('new_doctor'):
            ndoc = night_result['new_doctor']
            try:
                await bot.send_message(game.chat_id, "👩🏼‍⚕️ <b>Hamshira Shifokor lavozimini egalladi!</b>", parse_mode="HTML")
                await bot.send_message(ndoc.telegram_user_id, "👨🏼‍⚕️ <b>Siz endi SHIFOKOR siz!</b>\nAholini davolang.", parse_mode="HTML")
            except Exception:
                pass

        # --- Prompt Last Words (50s) to killed players with exact death cause in PM ---
        def _get_night_death_pm_text(ktype: str) -> str:
            if ktype == 'tuzoqchi':
                return "🕸 <b>Tunda Tuzoqchining xavfli tuzog'iga tushib halok bo'ldingiz!</b>"
            elif ktype == 'afsungar':
                return "🧙🏼 <b>Tunda Afsungarga hujum qildingiz va uning la'nati o'zingizga qaytib halok bo'ldingiz!</b>"
            elif ktype == 'komissar_retaliate':
                return "🥷 <b>Komissarga suiqasd qilmoqchi bo'ldingiz, ammo Komissar hushyorlik bilan sizni otib o'ldirdi!</b>"
            elif ktype in ['kimyogar_poison', 'kimyogar']:
                return "🧪 <b>Tunda Kimyogar sizga zaharli eliksir ichirib zaharladi va siz halok bo'ldingiz!</b>"
            elif ktype in ['axmoq_headbutt', 'axmoq']:
                return "🤪 <b>Tunda Axmoq sizga qattiq kalla zarbasi berdi va siz halok bo'ldingiz!</b>"
            elif ktype == 'qotil':
                return "🔪 <b>Tunda shafqatsiz Qotil sizni pichoqlab o'ldirdi! Siz halok bo'ldingiz.</b>"
            elif ktype == 'komissar':
                return "🔫 <b>Tunda Komissar sizni shubhali deb hisoblab, otib o'ldirdi! Siz halok bo'ldingiz.</b>"
            else:
                return "🩸 <b>Tunda Mafiyalar sizni vahshiylarcha o'ldirishdi! Siz halok bo'ldingiz.</b>"

        for el in eliminated_list:
            p = el['player'] if isinstance(el, dict) else el
            rname = el['role_name'] if isinstance(el, dict) else (p.role.name if p.role else 'CITIZEN')
            ktype = el.get('killer_type', 'mafia') if isinstance(el, dict) else 'mafia'
            death_pm_reason = _get_night_death_pm_text(ktype)
            try:
                await bot.send_message(
                    p.telegram_user_id,
                    f"{death_pm_reason}\n\n"
                    f"🗣 <b>So'ngi so'zingizni aytishingiz uchun 50 sekund vaqt berildi:</b>\n"
                    f"<i>Qisqa so'ngi so'zingizni yozing (guruhga e'lon qilinadi):</i>",
                    parse_mode="HTML"
                )
                LAST_WORDS_PENDING[p.telegram_user_id] = {
                    'game_id': str(game.id),
                    'chat_id': game.chat_id,
                    'role_name': rname,
                    'display_name': p.display_name,
                }
                asyncio.create_task(_expire_last_words(p.telegram_user_id))
            except Exception:
                pass

        # --- Check Win Condition after Dawn announcements & PM notifications ---
        winner = await sync_to_async(WinConditionService.check_win_condition)(game)
        if winner:
            await asyncio.sleep(2.5)
            await sync_to_async(GameService.finish_game)(game, winner)
            await _announce_game_winner(game, winner, bot)
            return

        await asyncio.sleep(1.0)

        # --- Dawn Announcement Msg 3: Living Players List & Roles List ---
        all_players = await sync_to_async(
            lambda: list(game.players.all().order_by('created_at').select_related('role'))
        )()
        living_players = [p for p in all_players if p.is_alive]
        _register_ids(game_id, living_players)

        if len(living_players) == 0:
            logger.info(f"All players eliminated at night in game {game_id}.")
            try:
                await bot.send_message(
                    game.chat_id,
                    "💀 <b>O'yin yakunlandi!</b>\n\nBarcha o'yinchilar halok bo'ldi. Hech kim g'alaba qozonmadi.",
                    parse_mode="HTML"
                )
            except Exception:
                pass
            await sync_to_async(GameService.finish_game)(game, winner=None)
            return

        living_lines = "\n".join([
            f'{all_players.index(p) + 1}. {_player_team_badge(p)}<a href="tg://user?id={p.telegram_user_id}">{html.escape(p.display_name)}</a>{_player_health_badge(p)}'
            for p in living_players
        ])

        from collections import Counter
        civilians_roles = Counter()
        mafias_roles = Counter()
        solos_roles = Counter()

        for p in living_players:
            if p.role:
                r_name = role_label(p.role.name) or p.role.name
                r_icon = role_icon(p.role.name)
                r_team = str(getattr(p.role, 'team', 'CIVILIAN')).upper()
                r_code = str(getattr(p.role, 'code', '') or p.role.name).lower()
                role_str = f"{r_icon} {r_name}"

                if r_team == 'MAFIA' or r_code in ['don', 'mafia', 'advokat', 'ubiytsa', 'jurnalist', 'aygoqchi', 'laborant']:
                    mafias_roles[role_str] += 1
                elif r_team in ['SOLO', 'NEUTRAL', 'ZOMBIE'] or r_code in [
                    'qotil', 'kimyogar', 'rais', 'bori', 'aferist', 'gazabkor', 'sehrgar',
                    'konchi', 'qaroqchi', 'qorbobo', 'oshpaz', 'afsungar', 'tuzoqchi',
                    'axmoq', 'buqalamun', 'joker', 'suidsid', 'suitsid', 'zombi', 'maniak', 'koldun'
                ]:
                    solos_roles[role_str] += 1
                else:
                    civilians_roles[role_str] += 1
            else:
                civilians_roles["👨🏼 Tinch aholi"] += 1

        def _format_faction_line(faction_title: str, role_counter: Counter) -> str:
            total = sum(role_counter.values())
            items = []
            for r_str, cnt in role_counter.items():
                if cnt > 1:
                    items.append(f"{r_str} ({cnt})")
                else:
                    items.append(f"{r_str}")
            return f"{faction_title} ({total}): {', '.join(items)}"

        group_parts = []
        if civilians_roles:
            group_parts.append(_format_faction_line("🟢 Tinch aholi", civilians_roles))
        if mafias_roles:
            group_parts.append(_format_faction_line("🔴 Mafia", mafias_roles))
        if solos_roles:
            group_parts.append(_format_faction_line("🟡 Yakkalar", solos_roles))

        living_roles_str = "\n\n".join(group_parts) if group_parts else "Yo'q"

        bot_username = "mafia_bot"
        try:
            bot_info = await bot.get_me()
            bot_username = bot_info.username
        except Exception:
            pass

        dawn_template = await sync_to_async(TextService.get_text)(
            'dawn_living_players_format',
            fallback="{players_list}\n\n<b>Ulardan:</b>\n{roles_list}\n\n<b>Jami:</b> {count}\n\nEndi kechaning natijalarini muhokama qilamiz...\nOvoz berishgacha ⏳ <b>20 sekund</b> qoldi"
        )
        if '{roles_list}' in dawn_template:
            dawn_msg3 = (
                dawn_template.replace('{count}', str(len(living_players)))
                .replace('{players_list}', living_lines)
                .replace('{roles_list}', living_roles_str)
                .replace('{seconds}', '20')
            )
        else:
            dawn_msg3 = (
                f"{living_lines}\n\n"
                f"<b>Ulardan:</b>\n{living_roles_str}\n\n"
                f"<b>Jami:</b> {len(living_players)}\n\n"
                f"Endi kechaning natijalarini muhokama qilamiz...\n"
                f"Ovoz berishgacha ⏳ <b>20 sekund</b> qoldi"
            )
        try:
            await bot.send_message(
                game.chat_id,
                dawn_msg3,
                reply_markup=build_bot_pm_keyboard(bot_username),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Dawn msg 3 failed: {e}")

        # --- Send Detective Investigation Results (to Detective AND Serjant/Admiral) ---
        inv_results = night_result.get('investigation_results', [])
        for inv in inv_results:
            try:
                det_uid = inv.get('detective_user_id')
                if not det_uid and 'actor_id' in inv:
                    actor_p = await sync_to_async(Player.objects.filter(id=inv['actor_id']).first)()
                    if actor_p:
                        det_uid = actor_p.telegram_user_id

                target_name = inv.get('target_display_name')
                if not target_name and 'target_id' in inv:
                    tp = await sync_to_async(Player.objects.filter(id=inv['target_id']).first)()
                    if tp:
                        target_name = tp.display_name
                target_name = target_name or "Gumonlanuvchi"

                rname = inv.get('role_name', 'CITIZEN')
                r_icon = role_icon(rname)
                r_label = role_label(rname)
                role_display = f"{r_icon} {r_label}".strip() if r_icon else r_label

                inv_text = (
                    f"🕵🏻‍♂️ <b>Tekshiruv natijasi:</b>\n\n"
                    f"Tekshirilgan: <b>{html.escape(target_name)}</b>\n"
                    f"Roli: <b>{html.escape(role_display)}</b>"
                )
                if det_uid:
                    await bot.send_message(det_uid, inv_text, parse_mode="HTML")

                # Also send to living Serjant / Admiral police partners
                serjant_players = await sync_to_async(
                    lambda: list(
                        Player.objects.filter(
                            game=game, is_alive=True, role__name__in=['SERJANT', 'ADMIRAL']
                        ).exclude(telegram_user_id=det_uid)
                    )
                )()
                for sp in serjant_players:
                    try:
                        serj_text = (
                            f"👮🏼‍♂️ <b>Komissar tekshiruvi natijasi:</b>\n\n"
                            f"Tekshirilgan: <b>{html.escape(target_name)}</b>\n"
                            f"Roli: <b>{html.escape(role_display)}</b>"
                        )
                        await bot.send_message(sp.telegram_user_id, serj_text, parse_mode="HTML")
                    except Exception:
                        pass
            except Exception as inv_err:
                logger.warning(f"Investigation result delivery error: {inv_err}")

        # --- Send Doctor Healing Results ---
        doc_results = night_result.get('doctor_actions_results', [])
        for doc in doc_results:
            try:
                doc_uid = doc.get('doctor_user_id')
                t_name = html.escape(doc.get('target_name', "O'yinchi"))
                if doc_uid:
                    if doc.get('is_saved'):
                        doc_text = f"✅ Siz <b>{t_name}</b> ni o'limdan qutqarib qoldingiz!"
                    else:
                        doc_text = f"ℹ️ Siz <b>{t_name}</b> ni qutqarib qola olmadingiz."
                    await bot.send_message(doc_uid, doc_text, parse_mode="HTML")
            except Exception as doc_err:
                logger.warning(f"Doctor result delivery error: {doc_err}")

        # --- Send Dawn Hero Prompts (Don / Komissar with active Hero) ---
        from apps.economy.models import PlayerHero
        from bot_runtime.keyboards.inline import build_hero_dawn_ask_keyboard

        for lp in living_players:
            r_name = lp.role.name if lp.role else ''
            r_code = lp.role.code.lower() if (lp.role and hasattr(lp.role, 'code')) else ''
            if r_name in ['DON', 'DETECTIVE', 'KOMISSAR'] or r_code in ['don', 'komissar', 'detective']:
                hero = await sync_to_async(
                    lambda u_id=lp.telegram_user_id: PlayerHero.objects.filter(
                        telegram_id=u_id, is_active=True, charges__gt=0
                    ).first()
                )()
                if hero:
                    r_lbl = "🤵🏻 Don" if (r_name == 'DON' or r_code == 'don') else "🕵🏻‍♂️ Komissar"
                    prompt_text = (
                        f"🥷 <b>Geroydan foydalanasizmi?</b>\n\n"
                        f"Siz o'yinda <b>{r_lbl}</b> siz!\n"
                        f"🥷 Geroyingiz: <b>{hero.name}</b> (⭐ Daraja: {hero.level}, 🩸 Zaryad: {hero.charges} ta, 👊 Kuch: {hero.power_min}-{hero.power_max}%)\n\n"
                        f"Tongda biror o'yinchiga zarba berishni xohlaysizmi?"
                    )
                    kb = build_hero_dawn_ask_keyboard(str(game.id), str(lp.id))
                    try:
                        await bot.send_message(lp.telegram_user_id, prompt_text, reply_markup=kb, parse_mode="HTML")
                    except Exception as h_err:
                        logger.warning(f"Could not send dawn hero prompt to {lp.telegram_user_id}: {h_err}")

        # --- Wait configured seconds then start voting ---
        bot_id_str = str(game.bot_id) if game and getattr(game, 'bot_id', None) else ''
        dawn_wait = await sync_to_async(SettingService.get_group_or_bot_timing)(game.chat_id, bot_id_str, 'dawn_wait_duration', 15)
        try:
            dawn_wait = int(dawn_wait)
        except Exception:
            dawn_wait = 15
        await asyncio.sleep(dawn_wait)

        # Transition cleanly to voting phase
        await transition_day_to_voting(game, bot)

    except Exception as e:
        logger.exception(f"Error in advance_night_to_day for game {game_id}: {e}")
        try:
            g = await sync_to_async(Game.objects.select_related('bot').get)(id=game_id)
            if g.phase in [GamePhase.NIGHT, GamePhase.DAY, GamePhase.DISCUSSION] and g.status not in ['FINISHED', 'CANCELED']:
                await transition_day_to_voting(g, bot)
        except Exception as fb_err:
            logger.error(f"Fallback transition in advance_night_to_day failed: {fb_err}")
    finally:
        ADVANCING_NIGHT_GAMES.discard(game_id)


async def transition_day_to_voting(game: Game, bot: Bot):
    """Transitions game from DAY to VOTING phase and starts the exact cabinet voting timer."""
    game_id = str(game.id)
    try:
        from bot_runtime.manager import BotRuntimeManager
        bot = BotRuntimeManager.get_bot_for_game(game, bot)

        game = await sync_to_async(Game.objects.select_related('bot').get)(id=game_id)
        if game.status in [GamePhase.FINISHED, 'FINISHED', GamePhase.CANCELED, 'CANCELED']:
            return

        winner = await sync_to_async(WinConditionService.check_win_condition)(game)
        if winner:
            await sync_to_async(GameService.finish_game)(game, winner)
            await _announce_game_winner(game, winner, bot)
            return

        # Advance to VOTING phase safely
        try:
            await sync_to_async(GameService.advance_phase)(game, GamePhase.VOTING)
        except Exception as trans_err:
            logger.warning(f"Advance phase error in game {game_id}: {trans_err}")
            game.phase = GamePhase.VOTING
            game.status = GamePhase.VOTING
            await sync_to_async(game.save)(update_fields=['phase', 'status', 'updated_at'])

        game = await sync_to_async(Game.objects.select_related('bot').get)(id=game_id)
        bot_id_str = str(game.bot_id) if getattr(game, 'bot_id', None) else ''
        bot_username = "mafia_bot"
        try:
            bot_info = await bot.get_me()
            bot_username = bot_info.username
        except Exception:
            pass

        voting_duration = await sync_to_async(SettingService.get_group_or_bot_timing)(game.chat_id, bot_id_str, 'voting_duration', 20)
        try:
            voting_duration = int(voting_duration)
        except Exception:
            voting_duration = 20

        try:
            await bot.send_message(
                game.chat_id,
                f"⚖️ <b>Aybdorlarni aniqlash va jazolash vaqti keldi!</b>\n\n"
                f"Ovoz berish uchun <b>{voting_duration} sekund</b> vaqtingiz bor.\n"
                f"Botga o'tib, gumondor o'yinchini tanlang!",
                reply_markup=build_bot_pm_keyboard(bot_username),
                parse_mode="HTML"
            )
        except Exception:
            pass

        living_players = await sync_to_async(
            lambda: list(game.players.filter(is_alive=True).select_related('role'))
        )()
        _register_ids(game_id, living_players)

        # Send PM voting keyboards
        for player in living_players:
            if player.metadata and player.metadata.get('blocked_voting_round') == game.round_number:
                try:
                    await bot.send_message(
                        player.telegram_user_id,
                        "💃 <b>Kezuvchi dori bergani sababli bu kun ovoz bera olmaysiz!</b>"
                    )
                except Exception:
                    pass
                continue

            try:
                kb = build_voting_keyboard(str(game.id), living_players, str(player.id))
                await bot.send_message(
                    player.telegram_user_id,
                    "⚖️ <b>Ovoz berish boshlandi!</b>\nKimni gumon qilyapsiz? Tanlang:",
                    reply_markup=kb,
                    parse_mode="HTML"
                )
            except Exception:
                pass

        # Auto-close voting task (runs for exactly voting_duration)
        async def _voting_countdown():
            await asyncio.sleep(voting_duration)
            from bot_runtime.handlers.voting import auto_close_voting
            try:
                g = await sync_to_async(Game.objects.select_related('bot').get)(id=game_id)
                if g.phase == GamePhase.VOTING:
                    from bot_runtime.manager import BotRuntimeManager
                    actual_b = BotRuntimeManager.get_bot_for_game(g, bot)
                    await auto_close_voting(g, actual_b)
            except Exception as v_err:
                logger.warning(f"Voting auto-close error: {v_err}")

        cancel_task = VOTING_TASKS.pop(game_id, None)
        if cancel_task and not cancel_task.done():
            try:
                if asyncio.current_task() != cancel_task:
                    cancel_task.cancel()
            except Exception:
                pass

        VOTING_TASKS[game_id] = asyncio.create_task(_voting_countdown())

    except Exception as e:
        logger.exception(f"Error in transition_day_to_voting for game {game_id}: {e}")
        try:
            g = await sync_to_async(Game.objects.select_related('bot').get)(id=game_id)
            if g.phase in [GamePhase.NIGHT, GamePhase.DAY, GamePhase.DISCUSSION] and g.status not in ['FINISHED', 'CANCELED']:
                g.phase = GamePhase.VOTING
                g.status = GamePhase.VOTING
                await sync_to_async(g.save)(update_fields=['phase', 'status', 'updated_at'])
                from bot_runtime.handlers.voting import auto_close_voting
                asyncio.create_task(auto_close_voting(g, bot))
        except Exception as fb_err:
            logger.error(f"Fallback transition in transition_day_to_voting failed: {fb_err}")


# ---------------------------------------------------------------------------
# Winner Announcement
# ---------------------------------------------------------------------------

async def _announce_game_winner(game: Game, winner: str, bot: Bot, story_lines: list = None):
    from bot_runtime.manager import BotRuntimeManager
    from apps.superadmin.services import SettingService
    from bot_runtime.keyboards.inline import _player_team_badge

    bot = BotRuntimeManager.get_bot_for_game(game, bot)

    all_players = await sync_to_async(
        lambda: list(game.players.all().select_related('role'))
    )()

    winners = []
    others = []
    for p in all_players:
        if getattr(game, 'mode', 'CLASSIC') == 'TEAM':
            p_side = p.metadata.get('team_side') if p.metadata else None
            won_side = 'RED' if winner == 'TEAM_RED' else ('BLUE' if winner == 'TEAM_BLUE' else None)
            team_won = (p_side == won_side) if won_side else False
            # In TEAM mode, ALL members of the winning team win (even if eliminated/dead)!
            if team_won:
                winners.append(p)
            else:
                others.append(p)
        else:
            team = p.role.team if p.role else RoleTeam.CIVILIAN
            rname = p.role.name if p.role else 'CITIZEN'
            benign_solo_roles = {
                'RAIS', 'QORBOBO', 'OSHPAZ', 'KONCHI', 'AFERIST', 'BUQALAMUN', 'SUIDSID', 'SUITSID', 'BORI', "BO'RI", 'AXMOQ', 'QAROQCHI'
            }

            if winner in [RoleTeam.CIVILIAN, 'CIVILIAN']:
                team_won = (team == RoleTeam.CIVILIAN or rname in benign_solo_roles)
            elif winner in [RoleTeam.MAFIA, 'MAFIA']:
                team_won = (team == RoleTeam.MAFIA)
            elif winner in [RoleTeam.ZOMBIE, 'ZOMBIE']:
                team_won = (team == RoleTeam.ZOMBIE)
            elif winner in [RoleTeam.SOLO, 'SOLO']:
                team_won = (team == RoleTeam.SOLO and rname not in benign_solo_roles)
            else:
                team_won = (team == winner)

            if p.role and p.role.name == 'AXMOQ' and p.is_alive:
                team_won = True

            p_meta = p.metadata or {}
            hanged_suicide = bool(rname in ['SUIDSID', 'SUITSID'] and p_meta.get('hanged_as_suicide'))

            # In Classic mode, alive players of winning faction win! Also hanged Suidsid wins!
            if (team_won and p.is_alive) or hanged_suicide:
                winners.append(p)
            else:
                others.append(p)

    win_diamonds = await sync_to_async(SettingService.get_int)('victory_reward_diamonds', await sync_to_async(SettingService.get_int)('reward_win_diamonds', 0))
    part_coins = await sync_to_async(SettingService.get_int)('participation_reward_coins', await sync_to_async(SettingService.get_int)('reward_participation_coins', 15))
    part_diamonds = await sync_to_async(SettingService.get_int)('participation_reward_diamonds', await sync_to_async(SettingService.get_int)('reward_participation_diamonds', 0))

    meta_rewards = getattr(game, 'metadata', {}) or {}
    winner_rewards_map = meta_rewards.get('winner_rewards', {})

    part_reward_str = f"+{part_coins} 💶" + (f", +{win_diamonds} 💎" if win_diamonds > 0 else "")

    lines = []
    if getattr(game, 'mode', 'CLASSIC') == 'TEAM':
        if winner == 'TEAM_RED':
            lines.append("🏆 🔴 <b>QIZIL JAMOA G'ALABA QOZONDI!</b>\n")
        elif winner == 'TEAM_BLUE':
            lines.append("🏆 🔵 <b>KO'K JAMOA G'ALABA QOZONDI!</b>\n")
        else:
            lines.append("💀 <b>O'YIN YAKUNLANDI!</b>\n\nBarcha o'yinchilar halok bo'ldi. Hech kim g'alaba qozonmadi.\n")
    else:
        if winner in ['ALL_DEAD', 'DRAW', None] or not winners:
            lines.append("💀 <b>O'YIN YAKUNLANDI!</b>\n\nBarcha o'yinchilar halok bo'ldi. Hech bir jamoa g'alaba qozona olmadi.\n")
        elif winner in [RoleTeam.CIVILIAN, 'CIVILIAN']:
            lines.append("🏆 🟢 <b>TINCH AHOLI G'ALABA QOZONDI!</b>\n\nBarcha xavfli dushmanlar yo'q qilindi.\n")
        elif winner in [RoleTeam.MAFIA, 'MAFIA']:
            lines.append("🏆 🔴 <b>MAFIYA G'ALABA QOZONDI!</b>\n\nShahar butunlay mafiya qo'liga o'tdi.\n")
        elif winner in [RoleTeam.ZOMBIE, 'ZOMBIE']:
            lines.append("🏆 🧟 <b>ZOMBILAR G'ALABA QOZONDI!</b>\n\nBarcha tiriklar zombiga aylandi.\n")
        elif winner in [RoleTeam.SOLO, 'SOLO']:
            lines.append("🏆 🔪 <b>YAKKA QOTIL G'ALABA QOZONDI!</b>\n\nBarcha raqiblarini yo'q qildi.\n")
        else:
            lines.append("🏆 <b>O'yin tugadi!</b>\n")

    winner_places_map = {}
    if winners:
        lines.append("<b>G'oliblar:</b>")
        counter = 1
        for p in winners:
            rname = p.role.name if p.role else "CITIZEN"
            icon = role_icon(rname)
            label = role_label(rname)
            team_badge = _player_team_badge(p)
            mention = f'{team_badge}<a href="tg://user?id={p.telegram_user_id}">{html.escape(p.display_name)}</a>'
            
            p_meta = p.metadata or {}
            p_coins = p_meta.get('reward_coins')
            if not p_coins:
                p_coins = winner_rewards_map.get(str(p.telegram_user_id)) or winner_rewards_map.get(p.telegram_user_id)
            if not p_coins:
                if counter == 1:
                    p_coins = random.randint(70, 100)
                elif counter == 2:
                    p_coins = random.randint(50, 70)
                elif counter == 3:
                    p_coins = random.randint(30, 50)
                else:
                    p_coins = random.randint(20, 30)

            winner_places_map[p.telegram_user_id] = (counter, p_coins)
            dia_str = f", +{win_diamonds} 💎" if win_diamonds > 0 else ""
            lines.append(f" {counter}. {mention} - {icon} {label} (<b>+{p_coins} 💶</b>{dia_str})")
            counter += 1

    if others:
        lines.append(f"\n<b>Qolgan o'yinchilar (+{part_coins} 💶):</b>")
        counter = 1
        for p in others:
            rname = p.role.name if p.role else "CITIZEN"
            icon = role_icon(rname)
            label = role_label(rname)
            team_badge = _player_team_badge(p)
            mention = f'{team_badge}<a href="tg://user?id={p.telegram_user_id}">{html.escape(p.display_name)}</a>'
            lines.append(f" {counter}. {mention} - {icon} {label}")
            counter += 1

    lines.append("\n🎁 <i>Mukofotlar barcha ishtirokchilar hisobiga o'tkazildi!</i>")

    announcement_text = "\n".join(lines)
    await send_dynamic_animation(
        bot=bot,
        chat_id=game.chat_id,
        media_key='gif_victory',
        fallback_url="https://media.giphy.com/media/artj92V8o75VPL7AeQ/giphy.gif",
        caption=announcement_text,
        parse_mode="HTML"
    )

    # Send personal game conclusion PM with updated profile to EVERY player in background task
    from bot_runtime.manager import safe_send_message

    async def _deliver_endgame_profiles():
        from apps.stats.services import StatsService
        from apps.economy.services import EconomyService
        from bot_runtime.handlers.economy import _sync_get_inventory_state, format_custom_profile_text, check_channel_membership_and_apply_bonus
        from bot_runtime.keyboards.inline import build_profile_interactive_keyboard
        from apps.superadmin.services import TextService

        for p in all_players:
            try:
                profile = await sync_to_async(StatsService.get_or_create_profile)(
                    telegram_id=p.telegram_user_id,
                    username=p.username or '',
                    first_name=p.display_name or ''
                )
                stats = await sync_to_async(lambda: getattr(profile, 'stats', None))()
                wallet = await sync_to_async(EconomyService.get_or_create_wallet)(telegram_id=p.telegram_user_id)
                inv_state = await sync_to_async(_sync_get_inventory_state)(p.telegram_user_id)

                is_channel_member = await check_channel_membership_and_apply_bonus(bot, profile, wallet)
                prof_text = format_custom_profile_text(profile, stats, wallet, inv_state, is_channel_member=is_channel_member)
                is_winner = (p in winners)

                if is_winner:
                    place_info, place_coins = winner_places_map.get(p.telegram_user_id, (1, 75))
                    w_reward_str = f"+{place_coins} 💶" + (f", +{win_diamonds} 💎" if win_diamonds > 0 else "")
                    raw_win_hdr = await sync_to_async(TextService.get_text)(
                        'game_finish_payout_winner_format',
                        fallback="🎉 <b>O'yin yakunlandi! Siz {place_info}-o'rin bilan g'alaba qozondingiz!</b> 🥳\n🎁 <b>G'alaba mukofoti:</b> <code>{reward_str}</code> hisobingizga qo'shildi!\n\n"
                    )
                    header = raw_win_hdr.format(place_info=place_info, reward_str=w_reward_str)
                else:
                    raw_lose_hdr = await sync_to_async(TextService.get_text)(
                        'game_finish_payout_loser_format',
                        fallback="💀 <b>O'yin yakunlandi! Siz mag'lub bo'ldingiz.</b>\n🎁 <b>Ishtirok mukofoti:</b> <code>+{reward_coins} 💶</code> hisobingizga qo'shildi!\n\n"
                    )
                    header = raw_lose_hdr.format(reward_coins=part_coins)

                pm_text = header + prof_text
                kb = build_profile_interactive_keyboard(
                    himoya_on=inv_state['himoya']['on'],
                    osish_on=inv_state['osish_himoya']['on'],
                    hujjat_on=inv_state['hujjat']['on'],
                    geroy_himoya_on=inv_state['geroy_himoya']['on'],
                    vaksina_on=inv_state['vaksina']['on'],
                    dori_on=inv_state['dori_himoya']['on'],
                    sirpanish_on=inv_state['sirpanish_himoya']['on'],
                    tg_id=p.telegram_user_id
                )
                await safe_send_message(bot, p.telegram_user_id, pm_text, reply_markup=kb, parse_mode="HTML")
            except Exception as pm_err:
                logger.warning(f"Could not send end-game profile PM to player {p.telegram_user_id}: {pm_err}")

    asyncio.create_task(_deliver_endgame_profiles())


# ---------------------------------------------------------------------------
# Night Action Callbacks (Universal Dispatcher for all 21 Roles)
# ---------------------------------------------------------------------------

@router.callback_query(lambda c: c.data and (c.data.startswith("n_skip:") or (c.data.startswith("n:") and ":skip:" in c.data)))
async def handle_night_skip_callback(callback: CallbackQuery, bot: Bot):
    """
    Handles player skipping their night action.
    Format: n_skip:{short_gid} or n:{game12}:skip:{player12}
    """
    parts = callback.data.split(":")
    short_gid = parts[1]

    try:
        full_gid = await _resolve_game_id(short_gid)
        game = await sync_to_async(Game.objects.select_related('bot').get)(id=full_gid)
        if game.phase != GamePhase.NIGHT:
            await callback.answer("🌙 Tungi bosqich allaqachon yakunlangan.", show_alert=True)
            return

        actor = await sync_to_async(
            lambda: Player.objects.select_related('role').filter(
                game=game, telegram_user_id=callback.from_user.id
            ).first()
        )()

        if not actor or not actor.is_alive:
            await callback.answer("Siz tirik emassiz.", show_alert=True)
            return

        # Submit SKIP action
        await sync_to_async(NightActionService.submit_action)(
            game, actor, None, NightActionType.SKIP
        )

        rname = actor.role.name if actor.role else ''
        r_icon = role_icon(rname)
        r_label = role_label(rname)

        await callback.answer("😴 Dam olishga qaror qildingiz.")
        await callback.message.edit_text(
            f"😴 <b>Siz bu tunda dam olishga qaror qildingiz.</b>\nHech qanday harakat bajarilmadi.",
            reply_markup=build_back_to_group_keyboard(chat_id=game.chat_id),
            parse_mode="HTML"
        )

        # Send group notification: "{roli} bugun dam olishga qaror qildi"
        group_msg = f"{r_icon} <b>{r_label} bugun dam olishga qaror qildi</b>"
        try:
            await bot.send_message(game.chat_id, group_msg, parse_mode="HTML")
        except Exception as g_err:
            logger.warning(f"Could not send night skip info to group: {g_err}")

        # Check if all living active roles have acted -> advance night to day early!
        await _check_and_advance_night_if_ready(game, bot)

    except Exception as e:
        logger.exception("Error in night skip callback:")
        await callback.answer(f"Xatolik: {e}", show_alert=True)


# ---------------------------------------------------------------------------
# Komissar Action Choice (Tekshirish / Otish)
# ---------------------------------------------------------------------------

@router.callback_query(lambda c: c.data and c.data.startswith("km:"))
async def handle_komissar_action_choice(callback: CallbackQuery, bot: Bot):
    """
    Handles Komissar selecting between Tekshirish (inv) and Otish (sht).
    Callback data: km:{short_gid}:{inv|sht}
    """
    parts = callback.data.split(":")
    short_gid = parts[1]
    choice = parts[2]

    try:
        full_gid = await _resolve_game_id(short_gid)
        game = await sync_to_async(Game.objects.select_related('bot').get)(id=full_gid)
        if game.phase != GamePhase.NIGHT:
            await callback.answer("🌙 Tungi bosqich allaqachon yakunlangan.", show_alert=True)
            return

        living_players = await sync_to_async(
            lambda: list(game.players.filter(is_alive=True).select_related('role'))
        )()
        _register_ids(full_gid, living_players)

        actor = await sync_to_async(
            lambda: Player.objects.filter(game=game, telegram_user_id=callback.from_user.id).first()
        )()

        if not actor or not actor.is_alive:
            await callback.answer("Siz tirik emassiz.", show_alert=True)
            return

        if choice == "inv":
            kb = build_night_target_keyboard(full_gid, "inv", living_players, str(actor.id))
            await callback.message.edit_text(
                "🔍 <b>Kimni tekshirmoqchisiz?</b>\nO'yinchini tanlang:",
                reply_markup=kb,
                parse_mode="HTML"
            )
        elif choice == "sht":
            kb = build_night_target_keyboard(full_gid, "sht", living_players, str(actor.id))
            await callback.message.edit_text(
                "🔫 <b>Kimni otmoqchisiz?</b>\nO'yinchini tanlang:",
                reply_markup=kb,
                parse_mode="HTML"
            )
        await callback.answer()
    except Exception as e:
        logger.exception("Error in komissar choice callback:")
        await callback.answer(f"Xatolik: {e}", show_alert=True)


@router.callback_query(lambda c: c.data and c.data.startswith("n:"))
async def handle_night_action_callback(callback: CallbackQuery, bot: Bot):
    """
    Handles night action target selection.
    Format: n:{game12}:{act}:{player12}
    """
    parts = callback.data.split(":")
    short_gid = parts[1]
    act_code = parts[2]
    short_pid = parts[3]

    act_map = {
        "k": ("kill", NightActionType.MAFIA_KILL),
        "p": ("protect", NightActionType.DOCTOR_PROTECT),
        "inv": ("investigate", NightActionType.DETECTIVE_INVESTIGATE),
        "sht": ("shoot", NightActionType.DETECTIVE_SHOOT),
        "qot": ("kill", NightActionType.QOTIL_KILL),
        "kez": ("visit", NightActionType.KEZUVCHI_VISIT),
        "day": ("visit", NightActionType.DAYDI_VISIT),
        "adv": ("protect", NightActionType.ADVOKAT_PROTECT),
        "ubi": ("kill", NightActionType.UBIYTSA_KILL),
        "tuz": ("trap", NightActionType.TUZOQCHI_TRAP),
        "zom": ("bite", NightActionType.ZOMBI_BITE),
        "kim": ("potion", NightActionType.KIMYOGAR_POTION),
        "axm": ("visit", NightActionType.AXMOQ_VISIT),
        "buq": ("morph", NightActionType.BUQALAMUN_MORPH),
        "rai": ("gift", NightActionType.RAIS_GIFT),
        "jk": ("boxes", NightActionType.JOKER_BOXES),
        "afer": ("steal", NightActionType.AFERIST_STEAL),
        "gaz": ("mark", NightActionType.GAZABKOR_MARK),
        "jurn": ("investigate", NightActionType.JURNALIST_INVESTIGATE),
        "sotq": ("check", NightActionType.SOTQIN_CHECK),
        "rob": ("shoot", NightActionType.ROBINGUD_SHOOT),
        "ayg": ("spy", NightActionType.AYGOQCHI_SPY),
        "foto": ("snap", NightActionType.FOTOPARATCHI_SNAP),
        "qar": ("rob", NightActionType.QAROQCHI_ROB),
        "lab": ("action", NightActionType.LABORANT_ACTION),
        "qor": ("gift", NightActionType.QORBOBO_GIFT),
        "osh": ("feed", NightActionType.OSHPAZ_FEED),
        # Legacy full names as fallback
        "qotil": ("kill", NightActionType.QOTIL_KILL),
        "kezuvchi": ("visit", NightActionType.KEZUVCHI_VISIT),
        "daydi": ("visit", NightActionType.DAYDI_VISIT),
        "advokat": ("protect", NightActionType.ADVOKAT_PROTECT),
        "ubiytsa": ("kill", NightActionType.UBIYTSA_KILL),
        "tuzoqchi": ("trap", NightActionType.TUZOQCHI_TRAP),
        "zombi": ("bite", NightActionType.ZOMBI_BITE),
        "kimyogar": ("potion", NightActionType.KIMYOGAR_POTION),
        "axmoq": ("visit", NightActionType.AXMOQ_VISIT),
        "buqalamun": ("morph", NightActionType.BUQALAMUN_MORPH),
        "rais": ("gift", NightActionType.RAIS_GIFT),
        "joker": ("boxes", NightActionType.JOKER_BOXES),
    }

    if act_code not in act_map:
        await callback.answer("Noma'lum amal.", show_alert=True)
        return

    action_type_key, action_type = act_map[act_code]

    try:
        full_gid = await _resolve_game_id(short_gid)
        game = await sync_to_async(Game.objects.select_related('bot').get)(id=full_gid)
        if game.phase != GamePhase.NIGHT:
            await callback.answer("🌙 Tungi bosqich allaqachon yakunlangan.", show_alert=True)
            return

        actor = await sync_to_async(
            lambda: Player.objects.select_related('role').get(
                game=game, telegram_user_id=callback.from_user.id
            )
        )()

        full_pid = await _resolve_player_id(game, short_pid)
        target = await sync_to_async(
            lambda: Player.objects.select_related('role').get(game=game, id=full_pid)
        )()

        # Get metadata if Joker
        extra_meta = {}
        if act_code == 'jk':
            extra_meta['boxes'] = JOKER_TEMP_BOXES.get(str(game.id), {}).get(callback.from_user.id, [1])

        await sync_to_async(NightActionService.submit_action)(
            game, actor, target, action_type, metadata=extra_meta
        )

        target_name = target.display_name or target.username or "O'yinchi"

        # Determine question header matching role theme
        prompt_header = "<b>Kimni tanladingiz?</b>"
        rname = actor.role.name if actor.role else ''
        if rname in ["DON", "MAFIA"]:
            prompt_header = "<b>Kimni o'ldiramiz?</b>"
        elif rname == "UBIYTSA":
            prompt_header = "<b>Suiqasd uchun nishonni tanlang:</b>"
        elif rname in ["DOCTOR", "HAMSHIRA"]:
            prompt_header = "<b>Kimni davolaymiz?</b>"
        elif rname in ["DETECTIVE", "KOMISSAR", "SHERIFF"]:
            prompt_header = "<b>Kimni otamiz?</b>" if act_code == "sht" else "<b>Kimni tekshiramiz?</b>"
        elif rname == "SERJANT":
            prompt_header = "<b>Tungi tekshiruv uchun nishonni tanlang:</b>"
        elif rname == "QOTIL":
            prompt_header = "<b>Qonli qurbonni tanlang:</b>"
        elif rname == "KEZUVCHI":
            prompt_header = "<b>Kimnikiga mehmonga borasiz?</b>"
        elif rname == "DAYDI":
            prompt_header = "<b>Kimnikiga borasiz?</b>"
        elif rname == "ADVOKAT":
            prompt_header = "<b>Kimni himoya qilasiz?</b>"
        elif rname == "TUZOQCHI":
            prompt_header = "<b>Tuzoqni kimga qo'yasiz?</b>"
        elif rname == "ZOMBI":
            prompt_header = "<b>Kimni tishlaysiz?</b>"
        elif rname == "KIMYOGAR":
            prompt_header = "<b>Kimga eliksir ishlatasiz?</b>"
        elif rname == "AXMOQ":
            prompt_header = "<b>Kimnikiga tashrif buyurasiz?</b>"
        elif rname == "BUQALAMUN":
            prompt_header = "<b>Kimning qiyofasiga kirmoqchisiz?</b>"
        elif rname == "RAIS":
            prompt_header = "<b>Kimga dollar ulashmoqchisiz?</b>"
        elif rname == "JOKER":
            prompt_header = "<b>Qaysi o'yinchiga quti yuborasiz?</b>"
        elif rname == "QORBOBO":
            prompt_header = "<b>Kimgadir sovg'a ulashmoqchimisiz?</b>"
        elif rname == "OSHPAZ":
            prompt_header = "<b>Kimga taom tayyorlaysiz?</b>"
        elif rname == "QAROQCHI":
            prompt_header = "<b>Kimni tunamoqchisiz?</b>"
        elif rname == "SOTQIN":
            prompt_header = "<b>Kimni tekshirmoqchisiz?</b>"
        elif rname == "FOTOPARATCHI":
            prompt_header = "<b>Kimni suratga olmoqchisiz?</b>"
        elif rname == "JURNALIST":
            prompt_header = "<b>Kimning xonadonini kuzatmoqchisiz?</b>"
        elif rname == "AYGOQCHI":
            prompt_header = "<b>Kimning rolini aniqlamoqchisiz?</b>"
        elif rname == "ROBINGUD":
            prompt_header = "<b>Kimni nishonga olib otasiz?</b>"
        elif rname == "LABORANT":
            prompt_header = "<b>Kimga zardob ishlatasiz?</b>"
        elif rname == "GAZABKOR":
            prompt_header = "<b>Kimni nishonlab belgilaysiz?</b>"
        elif rname == "SEHRGAR":
            prompt_header = "<b>Kimga sehr ta'sirini o'tkazasiz?</b>"
        elif rname == "AFERIST":
            prompt_header = "<b>Kimning ovozini o'g'irlaysiz?</b>"

        confirm_msg = (
            f"{prompt_header}\n\n"
            f"<b>Sizning tanlov: {html.escape(target_name)} ❗</b>"
        )

        await callback.answer(f"✅ Tanlov: {target_name}")
        await callback.message.edit_text(
            confirm_msg,
            reply_markup=build_back_to_group_keyboard(chat_id=game.chat_id),
            parse_mode="HTML"
        )

        # --- Live Atmospheric Role Action Info in Group Chat ---
        group_action_msg = None
        rname = actor.role.name if actor.role else ''
        if rname == "DON":
            group_action_msg = "🤵🏻 <b>Don o'zining navbatdagi nishonini tanladi...</b>"
        elif rname == "MAFIA":
            group_action_msg = "🤵🏼 <b>Mafiya a'zosi qorong'ulik bag'rida o'ljasini poylamoqda...</b>"
        elif rname in ["DOCTOR", "HAMSHIRA"]:
            group_action_msg = "👨🏼‍⚕️ <b>Shifokor xavf ostidagi fuqaroni qutqarishga shoshildi...</b>"
        elif rname in ["DETECTIVE", "KOMISSAR", "SHERIFF"]:
            if act_code == "sht":
                group_action_msg = "🔫 <b>Komissar qurolini shaylab, nishonga o'q uzishga qaror qildi...</b>"
            else:
                group_action_msg = "🕵🏻‍♂️ <b>Komissar shubhali shaxsni tekshirish uchun uning iziga tushdi...</b>"
        elif rname == "SERJANT":
            group_action_msg = "👮🏼‍♂️ <b>Serjant tungi patrulga chiqib, shahar osoyishtaligini kuzatmoqda...</b>"
        elif rname == "QOTIL":
            group_action_msg = "🔪 <b>Qonxo'r Qotil pichoqlarini charxlab, qurbonini poylamoqda...</b>"
        elif rname == "KEZUVCHI":
            group_action_msg = "💃 <b>Kezuvchi bugun tunni kim bilan o'tkazishni tanladi...</b>"
        elif rname == "DAYDI":
            group_action_msg = "🍾 <b>Daydi qayerdandir ichkilik topish ilinjida mehmonga yo'l oldi...</b>"
        elif rname == "ADVOKAT":
            group_action_msg = "💼 <b>Advokat o'z mijozini himoya qilish choralarini ko'rdi...</b>"
        elif rname == "UBIYTSA":
            group_action_msg = "🥷 <b>Ubiytsa qorong'ulik bag'rida o'ljasini nishonga oldi...</b>"
        elif rname == "TUZOQCHI":
            group_action_msg = "🕸 <b>Tuzoqchi ko'z ilg'amas joyga o'lim tuzog'ini o'rnatdi...</b>"
        elif rname == "ZOMBI":
            group_action_msg = "🧟 <b>Zombi yangi qurbonni o'z safiga qo'shish uchun tishlashga oshiqmoqda...</b>"
        elif rname == "KIMYOGAR":
            group_action_msg = "🧪 <b>Kimyogar maxfiy kolbasidagi sehrli eliksirni ishga soldi...</b>"
        elif rname == "AXMOQ":
            group_action_msg = "🤪 <b>Axmoq ko'chada tentirab yurib, bir eshikni taqillatdi...</b>"
        elif rname == "BUQALAMUN":
            group_action_msg = "🦎 <b>Buqalamun yangi qiyofaga kirish uchun o'z nusxasini tanladi...</b>"
        elif rname == "RAIS":
            group_action_msg = "💰 <b>Saxiy Rais shahar xazinasidan kimnidir mukofotlashga qaror qildi...</b>"
        elif rname == "JOKER":
            group_action_msg = "🃏 <b>Joker o'zining portlovchi xavfli qutilarini hozirladi...</b>"
        elif rname == "QORBOBO":
            group_action_msg = "🎅🏻 <b>Qorbobo kimnidir xursand qilish uchun ajoyib sovg'a qutisini hozirladi...</b>"
        elif rname == "OSHPAZ":
            group_action_msg = "👨🏼‍🍳 <b>Oshpaz oshxonada maxsus sehrli taomini tayyorladi...</b>"
        elif rname == "KONCHI":
            group_action_msg = "⛏ <b>Konchi qorong'u konda qimmatbaho javohirlar qidirishga tushdi...</b>"
        elif rname == "QAROQCHI":
            group_action_msg = "🏴‍☠️ <b>Qaroqchi o'ljasini poylab, uning boyligini o'g'irlashga shaylandi...</b>"
        elif rname == "SOTQIN":
            group_action_msg = "🤓 <b>Sotqin shubhali shaxsning orqasidan pinhona ergashdi...</b>"
        elif rname == "FOTOPARATCHI":
            group_action_msg = "📸 <b>Fotoparatchi kamerasini shaylab, kimnidir poylashga kirishdi...</b>"
        elif rname == "JURNALIST":
            group_action_msg = "👩🏼‍💻 <b>Jurnalist shov-shuvli yangilik topish maqsadida xonadonni kuzatishga kirishdi...</b>"
        elif rname == "AYGOQCHI":
            group_action_msg = "🦇 <b>Ayg'oqchi tungi zulmatda kimningdir maxfiy sirini bilishga uchib ketdi...</b>"
        elif rname == "ROBINGUD":
            group_action_msg = "🏹 <b>Robin Gud o'z kamonidan o'q uzish uchun mo'ljal oldi...</b>"
        elif rname == "LABORANT":
            group_action_msg = "👩‍🔬 <b>Laborant maxsus kimyoviy zardob bilan o'z amalini bajardi...</b>"
        elif rname == "GAZABKOR":
            group_action_msg = "🧌 <b>G'azabkor qasos olish uchun qurboniga o'z nishonini qo'ydi...</b>"
        elif rname == "SEHRGAR":
            group_action_msg = "🧙‍♂️ <b>Sehrgar o'zining sehrli tayoqchasi bilan tanlov qildi...</b>"
        elif rname == "AFERIST":
            group_action_msg = "🤹🏻 <b>Aferist o'zining navbatdagi qalloblik rejasini tuzdi...</b>"

        if group_action_msg:
            try:
                await bot.send_message(game.chat_id, group_action_msg, parse_mode="HTML")
            except Exception as g_err:
                logger.warning(f"Could not send group action info: {g_err}")

        # Notify living Mafia teammates in PM when a Mafia member chooses a target
        is_mafia_actor = (actor.role and (actor.role.team == RoleTeam.MAFIA or actor.role.name in ["DON", "MAFIA", "ADVOKAT", "UBIYTSA", "JURNALIST", "AYGOQCHI", "LABORANT"]))
        if is_mafia_actor:
            mafia_teammates = await sync_to_async(
                lambda: list(
                    Player.objects.filter(
                        game=game, is_alive=True
                    ).filter(
                        Q(role__team=RoleTeam.MAFIA) | Q(role__name__in=["DON", "MAFIA", "ADVOKAT", "UBIYTSA", "JURNALIST", "AYGOQCHI", "LABORANT"])
                    ).exclude(telegram_user_id=callback.from_user.id)
                )
            )()
            if mafia_teammates:
                r_icon = role_icon(actor.role.name)
                r_lbl = role_label(actor.role.name)
                tpl = await sync_to_async(TextService.get_text)(
                    'night_mafia_vote_relay',
                    fallback="🤵🏼 <b>[MAFIYA OV]</b> <b>{actor_name}</b> ({actor_role}) quyidagi o'yinchini nishonga oldi:\n🎯 <b>{target_name}</b>"
                )
                mafia_vote_msg = tpl.format(
                    actor_name=html.escape(actor.display_name or 'Mafiya'),
                    actor_role=f"{r_icon} {r_lbl}",
                    target_name=html.escape(target_name)
                )
                for tm in mafia_teammates:
                    try:
                        await bot.send_message(tm.telegram_user_id, mafia_vote_msg, parse_mode="HTML")
                    except Exception:
                        pass

        # Notify Serjant & Admiral if Komissar acted
        if actor.role and actor.role.name in ['DETECTIVE', 'KOMISSAR', 'SHERIFF']:
            police_subordinates = await sync_to_async(
                lambda: list(Player.objects.filter(game=game, is_alive=True, role__name__in=['SERJANT', 'ADMIRAL']).exclude(telegram_user_id=callback.from_user.id))
            )()
            act_name = "Tekshiruv" if act_code == 'inv' else "Otish"
            for sub in police_subordinates:
                try:
                    await bot.send_message(
                        sub.telegram_user_id,
                        f"🕵🏻‍♂️ <b>Komissar {act_name} harakatini bajardi:</b>\nNishon: <b>{html.escape(target_name)}</b>",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

        # Notify Hamshira if Doctor acted
        if actor.role and actor.role.name in ['DOCTOR', 'SHIFOKOR', 'DOKTOR']:
            hamshiras = await sync_to_async(
                lambda: list(Player.objects.filter(game=game, is_alive=True, role__name='HAMSHIRA').exclude(telegram_user_id=callback.from_user.id))
            )()
            for ham in hamshiras:
                try:
                    await bot.send_message(
                        ham.telegram_user_id,
                        f"👨🏼‍⚕️ <b>Shifokor davolash harakatini bajardi:</b>\nNishon: <b>{html.escape(target_name)}</b>",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass

        # Check if all living active roles have acted -> advance night to day early!
        await _check_and_advance_night_if_ready(game, bot)

    except ActionValidationError as ve:
        await callback.answer(str(ve), show_alert=True)
    except Exception as e:
        logger.exception("Error in night action callback:")
        await callback.answer(f"Xatolik: {str(e)}", show_alert=True)


# ---------------------------------------------------------------------------
# Joker Box Callbacks
# ---------------------------------------------------------------------------

@router.callback_query(lambda c: c.data and c.data.startswith("jk_box:"))
async def handle_joker_box_toggle(callback: CallbackQuery):
    """Joker selects boxes to plant bombs."""
    parts = callback.data.split(":")
    short_gid = parts[1]
    box_num = int(parts[2])

    full_gid = await _resolve_game_id(short_gid)
    uid = callback.from_user.id

    JOKER_TEMP_BOXES.setdefault(full_gid, {}).setdefault(uid, [])
    selected = JOKER_TEMP_BOXES[full_gid][uid]

    if box_num in selected:
        selected.remove(box_num)
    else:
        selected.append(box_num)

    kb = build_joker_boxes_setup_keyboard(full_gid, selected)
    await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer(f"{box_num}-quti belgilandi!")


@router.callback_query(lambda c: c.data and c.data.startswith("jk_send:"))
async def handle_joker_send_boxes(callback: CallbackQuery):
    """Joker proceeds to select victim."""
    short_gid = callback.data.split(":")[1]
    full_gid = await _resolve_game_id(short_gid)

    game = await sync_to_async(Game.objects.get)(id=full_gid)
    living_players = await sync_to_async(
        lambda: list(game.players.filter(is_alive=True))
    )()

    kb = build_night_target_keyboard(
        full_gid, 'jk', living_players, exclude_user_id=callback.from_user.id
    )
    await callback.message.edit_text(
        "🃏 <b>Bombani kimga yuborasiz?</b>\nO'yinchini tanlang:",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("jk_pick:"))
async def handle_joker_victim_pick(callback: CallbackQuery, bot: Bot):
    """Joker victim picks a box."""
    parts = callback.data.split(":")
    short_gid = parts[1]
    box_num = int(parts[2])

    full_gid = await _resolve_game_id(short_gid)
    game = await sync_to_async(Game.objects.select_related('bot').get)(id=full_gid)
    player = await sync_to_async(
        lambda: Player.objects.filter(game=game, telegram_user_id=callback.from_user.id).first()
    )()

    if not player or not player.is_alive:
        await callback.answer("Siz tirik emassiz.", show_alert=True)
        return

    pending_bombs = player.metadata.get('pending_joker_boxes', [1]) if player.metadata else [1]

    if box_num in pending_bombs:
        # Bomb exploded!
        player.is_alive = False
        player.eliminated_reason = 'JOKER_BOMB'
        await sync_to_async(player.save)(update_fields=['is_alive', 'eliminated_reason'])

        await callback.message.edit_text("💥 <b>BOOM! Siz bombani tanladingiz va halok bo'ldingiz!</b>", parse_mode="HTML")
        await callback.answer("💥 Portlash!", show_alert=True)

        try:
            await bot.send_message(
                game.chat_id,
                f"🃏 <b>JOKER bugun xursand ko'rinadi!</b>\n\n"
                f"💀 <b>{html.escape(player.display_name)}</b> Jokerning sovg'asidagi bombani ochib halok bo'ldi!",
                parse_mode="HTML"
            )
        except Exception:
            pass
    else:
        # Survived!
        if player.metadata:
            player.metadata.pop('pending_joker_boxes', None)
            await sync_to_async(player.save)(update_fields=['metadata'])

        await callback.message.edit_text("🎉 <b>Tabriklaymiz! Siz xavfsiz qutini tanladingiz va tirik qoldingiz!</b>", parse_mode="HTML")
        await callback.answer("🎉 Tirik qoldingiz!")

        try:
            await bot.send_message(
                game.chat_id,
                f"🃏 <b>JOKER ni xafa qilishdi...</b>\n"
                f"<b>{html.escape(player.display_name)}</b> to'g'ri qutini tanlab omon qoldi!",
                parse_mode="HTML"
            )
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Vaccine Callbacks
# ---------------------------------------------------------------------------

@router.callback_query(lambda c: c.data and c.data.startswith("vak_use:"))
async def handle_vaccine_use(callback: CallbackQuery):
    """Infected player consumes vaccine."""
    short_gid = callback.data.split(":")[1]
    full_gid = await _resolve_game_id(short_gid)
    game = await sync_to_async(Game.objects.get)(id=full_gid)
    player = await sync_to_async(
        lambda: Player.objects.filter(game=game, telegram_user_id=callback.from_user.id).first()
    )()
async def handle_vaksina_use_callback(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split(":")
    short_gid = parts[1]
    full_gid = await _resolve_game_id(short_gid)

    game = await sync_to_async(Game.objects.get)(id=full_gid)
    player = await sync_to_async(
        lambda: Player.objects.filter(game=game, telegram_user_id=callback.from_user.id).first()
    )()

    if not player:
        await callback.answer("O'yinchi topilmadi.")
        return

    from apps.economy.models import Wallet, CurrencyType
    wallet = await sync_to_async(
        lambda: Wallet.objects.filter(user=player.profile.user if hasattr(player, 'profile') and player.profile else None).first()
    )()

    price = 150
    if not wallet or wallet.get_balance(CurrencyType.COIN) < price:
        await callback.answer("❌ Vaksina sotib olish uchun mablag' yetarli emas (150 💶).", show_alert=True)
        return

    from apps.economy.services import EconomyService
    from apps.economy.models import TransactionType
    await sync_to_async(EconomyService.transfer_funds)(
        from_wallet=wallet, to_wallet=None, currency=CurrencyType.COIN, amount=price,
        tx_type=TransactionType.PURCHASE, description="Zombi vaksinasi xaridi"
    )

    try:
        await callback.message.edit_text("💉 <b>Vaksina qabul qilindi!</b>\nSiz asil rolingizga qaytdingiz.", parse_mode="HTML")
    except Exception:
        pass
    await callback.answer("💉 Vaksina ishlatildi!")


@router.callback_query(lambda c: c.data and c.data.startswith("vak_skip:"))
async def handle_vaksina_skip_callback(callback: CallbackQuery, bot: Bot):
    try:
        await callback.message.edit_text("🧟 Siz Zombi sifatida o'ynashni davom ettirasiz.", parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


# ---------------------------------------------------------------------------
# Private Chat Message Relay (Last words & Mafia / Police PM chat)
# ---------------------------------------------------------------------------

@router.message(F.chat.type == "private", F.text, ~F.text.startswith("/"))
async def handle_private_message_relay(message: Message, bot: Bot):
    """
    1. Handles dying player's Last Words (So'ngi so'z) within 50s.
    2. Relays Mafia PM to living Mafia teammates (Don, Mafia, Advokat, Ubiytsa, Jurnalist, Aygoqchi, Laborant).
    3. Relays Police PM between living Komissar and Serjant.
    """
    user_id = message.from_user.id

    # 1. Last Words Check
    if user_id in LAST_WORDS_PENDING:
        lw = LAST_WORDS_PENDING.pop(user_id, None)
        if lw:
            chat_id = lw['chat_id']
            role_name = lw['role_name']
            name = lw['display_name']
            user_text = message.text.strip()[:150]

            r_icon = role_icon(role_name)
            r_label = role_label(role_name)
            user_mention = f'<a href="tg://user?id={user_id}">{html.escape(name)}</a>'

            last_words_msg = (
                f"🗣 Aholidan kimdir {r_icon} {r_label} {user_mention} o'limidan oldin:\n"
                f'"{html.escape(user_text)}" - deb qichqirganini eshitgan.'
            )
            try:
                await bot.send_message(chat_id, last_words_msg, parse_mode="HTML")
                await message.reply("✅ <b>So'ngi so'zingiz guruhga e'lon qilindi.</b>", parse_mode="HTML")
            except Exception:
                pass
            return

    # 2. Night / Game Chat Relays
    try:
        player = await sync_to_async(
            lambda: Player.objects.select_related('role', 'game')
            .filter(
                telegram_user_id=user_id,
                is_alive=True,
            )
            .exclude(game__phase__in=[GamePhase.FINISHED, GamePhase.CANCELED])
            .exclude(game__status__in=[GamePhase.FINISHED, GamePhase.CANCELED, 'FINISHED', 'CANCELED'])
            .order_by('-game__created_at').first()
        )()

        if not player or not player.role:
            return

        game = player.game
        sender_name = player.display_name or message.from_user.first_name or "O'yinchi"
        r_name = player.role.name
        r_icon = role_icon(r_name)
        r_lbl = role_label(r_name)

        # 1. Mafia Team Relay (Don, Mafia, Advokat, Ubiytsa, Jurnalist, Aygoqchi, Laborant)
        is_mafia = (player.role.team == RoleTeam.MAFIA or r_name in ["DON", "MAFIA", "ADVOKAT", "UBIYTSA", "JURNALIST", "AYGOQCHI", "LABORANT"])
        if is_mafia:
            mafia_teammates = await sync_to_async(
                lambda: list(
                    Player.objects.filter(
                        game=game, is_alive=True
                    ).filter(
                        Q(role__team=RoleTeam.MAFIA) | Q(role__name__in=["DON", "MAFIA", "ADVOKAT", "UBIYTSA", "JURNALIST", "AYGOQCHI", "LABORANT"])
                    ).exclude(telegram_user_id=user_id)
                )
            )()

            if mafia_teammates:
                tpl = await sync_to_async(TextService.get_text)(
                    'night_mafia_chat_relay',
                    fallback="💬 <b>[MAFIYA CHAT]</b> {role_icon} <b>{sender_name} ({role_label}):</b>\n{text}"
                )
                relay_text = tpl.format(
                    role_icon=r_icon,
                    sender_name=html.escape(sender_name),
                    role_label=html.escape(r_lbl),
                    text=html.escape(message.text)
                )
                for tm in mafia_teammates:
                    try:
                        await bot.send_message(tm.telegram_user_id, relay_text, parse_mode="HTML")
                    except Exception:
                        pass
                await message.answer(f"✅ {len(mafia_teammates)} ta mafiya sherigingizga yetkazildi.")
            else:
                await message.answer("📭 Hozirda sizdan boshqa tirik mafiya a'zosi yo'q.")

        # 2. Police Team Relay (Komissar <-> Serjant <-> Admiral)
        elif r_name in ['DETECTIVE', 'KOMISSAR', 'SHERIFF', 'SERJANT', 'ADMIRAL']:
            police_partners = await sync_to_async(
                lambda: list(
                    Player.objects.filter(
                        game=game, is_alive=True, role__name__in=['DETECTIVE', 'KOMISSAR', 'SHERIFF', 'SERJANT', 'ADMIRAL']
                    ).exclude(telegram_user_id=user_id)
                )
            )()

            if police_partners:
                tpl = await sync_to_async(TextService.get_text)(
                    'night_police_chat_relay',
                    fallback="💬 <b>[POLITSIYA CHAT]</b> {role_icon} <b>{sender_name} ({role_label}):</b>\n{text}"
                )
                relay_text = tpl.format(
                    role_icon=r_icon,
                    sender_name=html.escape(sender_name),
                    role_label=html.escape(r_lbl),
                    text=html.escape(message.text)
                )
                for pp in police_partners:
                    try:
                        await bot.send_message(pp.telegram_user_id, relay_text, parse_mode="HTML")
                    except Exception:
                        pass
                await message.answer(f"✅ {len(police_partners)} ta politsiya sherigingizga yetkazildi.")
            else:
                await message.answer("📭 Hozirda sizdan boshqa tirik politsiya xodimi yo'q.")

        # 3. Medical Team Relay (Doctor <-> Hamshira)
        elif r_name in ['DOCTOR', 'SHIFOKOR', 'DOKTOR', 'HAMSHIRA']:
            medical_partners = await sync_to_async(
                lambda: list(
                    Player.objects.filter(
                        game=game, is_alive=True, role__name__in=['DOCTOR', 'SHIFOKOR', 'DOKTOR', 'HAMSHIRA']
                    ).exclude(telegram_user_id=user_id)
                )
            )()

            if medical_partners:
                tpl = await sync_to_async(TextService.get_text)(
                    'night_medical_chat_relay',
                    fallback="💬 <b>[TIBBIYOT CHAT]</b> {role_icon} <b>{sender_name} ({role_label}):</b>\n{text}"
                )
                relay_text = tpl.format(
                    role_icon=r_icon,
                    sender_name=html.escape(sender_name),
                    role_label=html.escape(r_lbl),
                    text=html.escape(message.text)
                )
                for mp in medical_partners:
                    try:
                        await bot.send_message(mp.telegram_user_id, relay_text, parse_mode="HTML")
                    except Exception:
                        pass
                await message.answer(f"✅ {len(medical_partners)} ta tibbiyot sherigingizga yetkazildi.")
            else:
                await message.answer("📭 Hozirda sizdan boshqa tirik shifokor/hamshira yo'q.")

        else:
            await message.answer("ℹ️ Sizning rolingizda maxfiy guruh chati mavjud emas. Kunduzgi umumiy guruhda suhbatlashing.")

    except Exception as e:
        logger.exception("Error in night relay handler:")


# ---------------------------------------------------------------------------
# Sukut Rejimi (Night Silence Guard)
# ---------------------------------------------------------------------------

@router.message(F.chat.type.in_(["group", "supergroup"]))
async def handle_night_silence_guard(message: types.Message, bot: Bot):
    if message.text and message.text.startswith('/'):
        return

    try:
        bot_info = await bot.get_me()
        active_game = await sync_to_async(
            lambda: Game.objects.select_related('bot__configuration').filter(
                bot__telegram_bot_id=bot_info.id,
                chat_id=message.chat.id,
                phase=GamePhase.NIGHT
            ).first()
        )()
        if not active_game:
            return

        cfg = getattr(active_game.bot, 'configuration', None)
        extra = cfg.extra_settings if cfg and cfg.extra_settings else {}
        mode = extra.get('night_silence_mode', 'DELETE_ALL')

        if mode == 'OFF':
            return

        user_id = message.from_user.id
        if user_id == 7782387930:
            return

        is_owner = await sync_to_async(
            lambda: PlayerProfile.objects.filter(telegram_id=user_id, is_platform_owner=True).exists()
        )()
        if is_owner:
            return

        if mode == 'ALLOW_OWNER_AND_ADMINS':
            try:
                member = await bot.get_chat_member(chat_id=message.chat.id, user_id=user_id)
                if member.status in ['administrator', 'creator']:
                    return
            except Exception:
                pass
            await message.delete()
        elif mode == 'ALLOW_ALIVE_PLAYERS':
            is_alive = await sync_to_async(
                lambda: active_game.players.filter(telegram_user_id=user_id, is_alive=True).exists()
            )()
            if is_alive:
                return
            await message.delete()
        else:
            await message.delete()

    except Exception:
        pass


@router.callback_query(lambda c: c.data and c.data.startswith("kn:"))
async def handle_konchi_mine_callback(callback: CallbackQuery, bot: Bot):
    """Handles Konchi mine selection: kn:{short_gid}:{mine_num}"""
    parts = callback.data.split(":")
    short_gid = parts[1]
    mine_num = int(parts[2])

    try:
        full_gid = await _resolve_game_id(short_gid)
        game = await sync_to_async(Game.objects.select_related('bot').get)(id=full_gid)
        if game.phase != GamePhase.NIGHT:
            await callback.answer("🌙 Tungi bosqich allaqachon yakunlangan.", show_alert=True)
            return

        actor = await sync_to_async(
            lambda: Player.objects.select_related('role').get(game=game, telegram_user_id=callback.from_user.id)
        )()

        await sync_to_async(NightActionService.submit_action)(
            game, actor, None, NightActionType.KONCHI_MINE, metadata={'mine_index': mine_num}
        )

        await callback.answer(f"✅ {mine_num}-kon tanlandi!")
        await callback.message.edit_text(
            f"<b>Qaysi konni qazimoqchisiz?</b>\n\n"
            f"<b>Sizning tanlov: ⛏ {mine_num}-kon ❗</b>",
            reply_markup=build_back_to_group_keyboard(chat_id=game.chat_id),
            parse_mode="HTML"
        )

        try:
            await bot.send_message(
                game.chat_id,
                "⛏ <b>Konchi qorong'u konda qimmatbaho javohirlar qidirishga tushdi...</b>",
                parse_mode="HTML"
            )
        except Exception as g_err:
            logger.warning(f"Could not send Konchi group action info: {g_err}")

        await _check_and_advance_night_if_ready(game, bot)
    except Exception as e:
        logger.exception("Error in konchi mine callback:")
        await callback.answer(f"Xatolik: {e}", show_alert=True)
