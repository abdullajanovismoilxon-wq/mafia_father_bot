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

ROLE_ICONS = {
    "DON": "🤵🏻",
    "MAFIA": "🤵🏼",
    "DOCTOR": "👨🏼‍⚕️",
    "DETECTIVE": "🕵🏻‍♂️",
    "CITIZEN": "👨🏼",
    "QOTIL": "🔪",
    "KEZUVCHI": "💃",
    "SERJANT": "👮🏼‍♂️",
    "DAYDI": "🍾",
    "ADVOKAT": "💼",
    "SUIDSID": "🤡",
    "UBIYTSA": "🥷",
    "AFSUNGAR": "🧙🏼",
    "TUZOQCHI": "🕸",
    "ZOMBI": "🧟",
    "KIMYOGAR": "🧪",
    "AXMOQ": "🤪",
    "BUQALAMUN": "🦎",
    "RAIS": "🏛",
    "HAMSHIRA": "👩🏼‍⚕️",
    "JOKER": "🃏",
}

ROLE_LABELS = {
    "DON": "Don",
    "MAFIA": "Mafia",
    "DOCTOR": "Shifokor",
    "DETECTIVE": "Komissar",
    "CITIZEN": "Tinch aholi",
    "QOTIL": "Qotil",
    "KEZUVCHI": "Kezuvchi",
    "SERJANT": "Serjant",
    "DAYDI": "Daydi",
    "ADVOKAT": "Advokat",
    "SUIDSID": "Suidsid",
    "UBIYTSA": "Ubiytsa",
    "AFSUNGAR": "Afsungar",
    "TUZOQCHI": "Tuzoqchi",
    "ZOMBI": "Zombi",
    "KIMYOGAR": "Kimyogar",
    "AXMOQ": "Axmoq",
    "BUQALAMUN": "Buqalamun",
    "RAIS": "Rais",
    "HAMSHIRA": "Hamshira",
    "JOKER": "Joker",
}


def role_icon(name: str) -> str:
    return ROLE_ICONS.get(name, "👤")


def role_label(name: str) -> str:
    return ROLE_LABELS.get(name, name)


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
    """Waits night_duration seconds then advances Night → Dawn."""
    try:
        if not isinstance(night_duration, (int, float)):
            try:
                night_duration = int(night_duration)
            except Exception:
                night_duration = 60

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
        task.cancel()

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


PASSIVE_NIGHT_ROLES = {
    'CITIZEN', 'OMADLI', 'JANOB', 'BORI', 'SEHRGAR', 'ADMIRAL', 'HAMSHIRA', 'SUIDSID'
}


async def _check_and_advance_night_if_ready(game: Game, bot: Bot):
    """
    Checks if all living players with active night actions have submitted their action
    for the current round. If so, cancels the night timer and advances to Day/Dawn immediately.
    """
    try:
        from apps.games.models import NightAction
        game_id = str(game.id)
        current_game = await sync_to_async(Game.objects.select_related('bot').get)(id=game_id)
        if current_game.phase != GamePhase.NIGHT:
            return

        living_players = await sync_to_async(
            lambda: list(current_game.players.filter(is_alive=True).select_related('role'))
        )()

        # Collect living players with active night roles
        active_actors = [
            p for p in living_players
            if p.role and p.role.name not in PASSIVE_NIGHT_ROLES
        ]

        if not active_actors:
            # If no active night roles exist, advance immediately
            logger.info(f"No active night roles living in game {game_id}. Advancing to Dawn.")
            cancel_night_timer(game_id)
            await advance_night_to_day(current_game, bot)
            return

        # Check submitted actions for this round
        submitted_actor_ids = await sync_to_async(
            lambda: set(NightAction.objects.filter(
                game=current_game,
                round=current_game.round_number
            ).values_list('actor_id', flat=True))
        )()

        all_acted = True
        for actor in active_actors:
            # If actor is MAFIA and DON is alive, if DON has acted or MAFIA has acted, team decision is satisfied
            if actor.role and actor.role.name == 'MAFIA':
                don_alive = any(p.role and p.role.name == 'DON' for p in living_players)
                if don_alive:
                    don_actor = next((p for p in living_players if p.role and p.role.name == 'DON'), None)
                    if don_actor and don_actor.id in submitted_actor_ids:
                        continue
            if actor.id not in submitted_actor_ids:
                all_acted = False
                break

        if all_acted:
            logger.info(f"All {len(active_actors)} active night roles have submitted actions in game {game_id}. Advancing early!")
            cancel_night_timer(game_id)
            await advance_night_to_day(current_game, bot)

    except Exception as e:
        logger.warning(f"Error checking early night advance in game {game.id}: {e}")


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
                async with session.get(media_val, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        content_bytes = await resp.read()
                        os.makedirs(os.path.dirname(local_gif_path), exist_ok=True)
                        with open(local_gif_path, 'wb') as f:
                            f.write(content_bytes)
                        target = types.FSInputFile(local_gif_path)
                        return await bot.send_animation(chat_id=chat_id, animation=target, caption=caption, reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception as dl_err:
            logger.warning(f"Download for {media_key} failed: {dl_err}")

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
    try:
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

        death_lines = []
        for el in eliminated_list:
            p = el['player'] if isinstance(el, dict) else el
            rname = el['role_name'] if isinstance(el, dict) else (p.role.name if p.role else 'CITIZEN')
            ktype = el.get('killer_type', 'mafia') if isinstance(el, dict) else 'mafia'
            icon = role_icon(rname)
            label = role_label(rname)
            target_mention = f'<a href="tg://user?id={p.telegram_user_id}">{html.escape(p.display_name)}</a>'

            if ktype == 'tuzoqchi':
                death_lines.append(f"🕸 {target_mention} tuzoqqa ilinib halok bo'ldi! (U: {icon} {label} edi)")
            elif ktype == 'afsungar':
                death_lines.append(f"🧙🏼 Afsungarga hujum qilgan {target_mention} o'z la'nati qurboni bo'ldi! (U: {icon} {label} edi)")
            elif ktype == 'komissar_retaliate':
                death_lines.append(f"🥷 Komissarga suiqasd qilmoqchi bo'lgan Ubiytsa {target_mention} otib o'ldirildi! (U: {icon} {label} edi)")
            elif ktype == 'kimyogar_poison':
                death_lines.append(f"🧪 {target_mention} Kimyogarning zaharli eliksiridan halok bo'ldi! (U: {icon} {label} edi)")
            elif ktype == 'axmoq_headbutt':
                death_lines.append(f"🤪 {target_mention} Axmoqning kalla zarbasidan halok bo'ldi! (U: {icon} {label} edi)")
            elif ktype == 'qotil':
                death_lines.append(f"🔪 {target_mention} shafqatsiz Qotil tomonidan o'ldirildi. (U: {icon} {label} edi)")
            elif ktype == 'komissar':
                death_lines.append(f"🔫 {target_mention} Komissar tomonidan otib o'ldirildi. (U: {icon} {label} edi)")
            else:
                death_lines.append(f"🩸 {target_mention} Mafiyalar tomonidan vahshiylarcha o'ldirildi. (U: {icon} {label} edi)")

        # 3. Check for Win Condition
        winner = await sync_to_async(WinConditionService.check_win_condition)(game)
        if winner:
            await sync_to_async(GameService.end_game)(game, winner)
            await _announce_game_winner(game, winner, bot, story_lines=death_lines)
            return

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

        await asyncio.sleep(2)

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

        # --- Rais Gift Delivery ---
        rais_gifts = night_result.get('rais_gifts', [])
        for rg in rais_gifts:
            try:
                dia_text = f" va <b>{rg['diamonds']} 💎 Olmos</b>" if rg['diamonds'] > 0 else ""
                await bot.send_message(
                    rg['target_user_id'],
                    f"🏛 <b>Rais sizga sovg'a ulashdi!</b>\nHisobingizga <b>{rg['coins']} 💶 Dollar</b>{dia_text} o'tkazildi!",
                    parse_mode="HTML"
                )
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

        # --- Prompt Last Words (50s) to killed players ---
        for el in eliminated_list:
            p = el['player'] if isinstance(el, dict) else el
            rname = el['role_name'] if isinstance(el, dict) else (p.role.name if p.role else 'CITIZEN')
            try:
                await bot.send_message(
                    p.telegram_user_id,
                    "🩸 <b>Tunda siz halok bo'ldingiz.</b>\n\n"
                    "🗣 <b>So'ngi so'zingizni aytishingiz uchun 50 sekund vaqt berildi:</b>\n"
                    "<i>Qisqa so'ngi so'zingizni yozing (guruhga e'lon qilinadi):</i>",
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

        await asyncio.sleep(2)

        # --- Dawn Announcement Msg 3: Living Players List ---
        living_players = await sync_to_async(
            lambda: list(game.players.filter(is_alive=True).select_related('role'))
        )()
        _register_ids(game_id, living_players)

        living_lines = "\n".join([
            f'• {_player_team_badge(p)}<a href="tg://user?id={p.telegram_user_id}">{html.escape(p.display_name)}</a>'
            for p in living_players
        ])

        bot_username = "mafia_bot"
        try:
            bot_info = await bot.get_me()
            bot_username = bot_info.username
        except Exception:
            pass

        dawn_template = await sync_to_async(TextService.get_text)(
            'dawn_living_players_format',
            fallback="👥 <b>Tirik o'yinchilar: ({count} ta)</b>\n{players_list}\n\nOvoz berishgacha ⏳ <b>20 sekund</b> qoldi"
        )
        dawn_msg3 = (
            dawn_template.replace('{count}', str(len(living_players)))
            .replace('{players_list}', living_lines)
            .replace('{seconds}', '20')
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

        # --- Send Detective Investigation Results ---
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

                faction = "🔴 MAFIA" if inv.get('is_mafia') else "🟢 Tinch aholi"
                if det_uid:
                    await bot.send_message(
                        det_uid,
                        f"🕵🏻‍♂️ <b>Tekshiruv natijasi:</b>\n\n"
                        f"Tekshirilgan: <b>{html.escape(target_name)}</b>\n"
                        f"Jamoa: <b>{faction}</b>",
                        parse_mode="HTML"
                    )
            except Exception as inv_err:
                logger.warning(f"Investigation result delivery error: {inv_err}")

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
        bot_id_str = str(game.bot.id) if game.bot else ''
        dawn_wait = await sync_to_async(SettingService.get_bot_timing)(bot_id_str, 'dawn_wait_duration', 15)
        await asyncio.sleep(dawn_wait)

        # Refresh game state after dawn wait
        game = await sync_to_async(Game.objects.select_related('bot').get)(id=game_id)
        if game.phase != GamePhase.DAY or game.status in [GamePhase.FINISHED, 'FINISHED', GamePhase.CANCELED, 'CANCELED']:
            logger.info(f"Game {game_id} is no longer in DAY phase ({game.phase}/{game.status}). Skipping voting transition.")
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

        voting_duration = await sync_to_async(SettingService.get_bot_timing)(bot_id_str, 'voting_duration', 20)
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

        # Send PM voting keyboards
        for player in living_players:
            # If player was blocked by Kezuvchi, inform them
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

        # Auto-close voting task (non-blocking background task)
        async def _voting_countdown():
            await asyncio.sleep(voting_duration)
            from bot_runtime.handlers.voting import auto_close_voting
            try:
                g = await sync_to_async(Game.objects.select_related('bot').get)(id=game_id)
                if g.phase == GamePhase.VOTING:
                    await auto_close_voting(g, bot)
            except Exception as v_err:
                logger.warning(f"Voting auto-close error: {v_err}")

        asyncio.create_task(_voting_countdown())

    except Exception as e:
        logger.exception(f"Error in advance_night_to_day for game {game_id}: {e}")


# ---------------------------------------------------------------------------
# Winner Announcement
# ---------------------------------------------------------------------------

async def _announce_game_winner(game: Game, winner: str, bot: Bot, story_lines: list = None):
    # 1. Send "So'ngi voqealar:" as a separate message first
    if story_lines:
        story_text = "📖 <b>So'ngi voqealar:</b>\n" + "\n".join(story_lines)
        try:
            await bot.send_message(game.chat_id, story_text, parse_mode="HTML")
            await asyncio.sleep(1.5)
        except Exception:
            pass

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
            team_won = (team == winner or
                        (winner in [RoleTeam.CIVILIAN, 'CIVILIAN'] and team == RoleTeam.CIVILIAN) or
                        (winner in [RoleTeam.MAFIA, 'MAFIA'] and team == RoleTeam.MAFIA) or
                        (winner in [RoleTeam.ZOMBIE, 'ZOMBIE'] and team == RoleTeam.ZOMBIE) or
                        (winner in [RoleTeam.SOLO, 'SOLO'] and team == RoleTeam.SOLO))
            if p.role and p.role.name == 'AXMOQ' and p.is_alive:
                team_won = True

            # In Classic mode, only ALIVE players of winning faction win! Dead players do NOT win.
            if team_won and p.is_alive:
                winners.append(p)
            else:
                others.append(p)

    from apps.superadmin.services import SettingService
    from bot_runtime.keyboards.inline import _player_team_badge
    win_coins = await sync_to_async(SettingService.get_int)('victory_reward_coins', await sync_to_async(SettingService.get_int)('reward_win_coins', 50))
    win_diamonds = await sync_to_async(SettingService.get_int)('victory_reward_diamonds', await sync_to_async(SettingService.get_int)('reward_win_diamonds', 0))
    part_coins = await sync_to_async(SettingService.get_int)('participation_reward_coins', await sync_to_async(SettingService.get_int)('reward_participation_coins', 15))
    part_diamonds = await sync_to_async(SettingService.get_int)('participation_reward_diamonds', await sync_to_async(SettingService.get_int)('reward_participation_diamonds', 0))

    win_reward_str = f"+{win_coins} 💶" + (f", +{win_diamonds} 💎" if win_diamonds > 0 else "")
    part_reward_str = f"+{part_coins} 💶" + (f", +{part_diamonds} 💎" if part_diamonds > 0 else "")

    if getattr(game, 'mode', 'CLASSIC') == 'TEAM':
        if winner == 'TEAM_RED':
            lines = ["🏆 🔴 <b>QIZIL JAMOA G'ALABA QOZONDI!</b>\n"]
        elif winner == 'TEAM_BLUE':
            lines = ["🏆 🔵 <b>KO'K JAMOA G'ALABA QOZONDI!</b>\n"]
        else:
            lines = ["🏆 <b>O'yin tugadi!</b>\n"]
    else:
        lines = ["🏆 <b>O'yin tugadi!</b>\n"]

    if winners:
        lines.append(f"<b>G'oliblar ({win_reward_str}):</b>")
        counter = 1
        for p in winners:
            rname = p.role.name if p.role else "CITIZEN"
            icon = role_icon(rname)
            label = role_label(rname)
            team_badge = _player_team_badge(p)
            mention = f'{team_badge}<a href="tg://user?id={p.telegram_user_id}">{html.escape(p.display_name)}</a>'
            lines.append(f" {counter}. {mention} - {icon} {label}")
            counter += 1

    if others:
        lines.append(f"\n<b>Qolgan o'yinchilar ({part_reward_str}):</b>")
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

    # Send personal game conclusion PM with updated profile to EVERY player
    from apps.stats.services import StatsService
    from apps.economy.services import EconomyService
    from bot_runtime.handlers.economy import _sync_get_inventory_state, format_custom_profile_text
    from bot_runtime.keyboards.inline import build_profile_interactive_keyboard

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

            prof_text = format_custom_profile_text(profile, stats, wallet, inv_state)
            is_winner = (p in winners)

            if is_winner:
                header = (
                    "🎉 <b>O'yin yakunlandi! Siz g'alaba qozondingiz!</b> 🥳\n"
                    f"🎁 <b>G'alaba mukofoti:</b> <code>{win_reward_str}</code> hisobingizga qo'shildi!\n\n"
                )
            else:
                header = (
                    "💀 <b>O'yin yakunlandi! Siz mag'lub bo'ldingiz.</b>\n"
                    f"🎁 <b>Ishtirok mukofoti:</b> <code>{part_reward_str}</code> hisobingizga qo'shildi!\n\n"
                )

            pm_text = header + prof_text
            kb = build_profile_interactive_keyboard(
                himoya_on=inv_state['himoya']['on'],
                osish_on=inv_state['osish_himoya']['on'],
                hujjat_on=inv_state['hujjat']['on'],
                geroy_himoya_on=inv_state['geroy_himoya']['on']
            )
            await bot.send_message(p.telegram_user_id, pm_text, reply_markup=kb, parse_mode="HTML")
        except Exception as pm_err:
            logger.warning(f"Could not send end-game profile PM to player {p.telegram_user_id}: {pm_err}")


# ---------------------------------------------------------------------------
# Night Action Callbacks (Universal Dispatcher for all 21 Roles)
# ---------------------------------------------------------------------------

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

        # Determine question header matching Image 1
        prompt_header = "<b>Kimni tanladingiz?</b>"
        rname = actor.role.name if actor.role else ''
        if rname in ["DON", "MAFIA", "UBIYTSA"]:
            prompt_header = "<b>Kimni o'ldiramiz?</b>"
        elif rname in ["DOCTOR", "HAMSHIRA"]:
            prompt_header = "<b>Kimni davolaymiz?</b>"
        elif rname in ["DETECTIVE", "KOMISSAR", "SHERIFF"]:
            prompt_header = "<b>Kimni otamiz?</b>" if act_code == "sht" else "<b>Kimni tekshiramiz?</b>"
        elif rname == "QOTIL":
            prompt_header = "<b>Qurbonni tanlang:</b>"
        elif rname == "KEZUVCHI":
            prompt_header = "<b>Kimnikiga mehmonga borasiz?</b>"
        elif rname == "DAYDI":
            prompt_header = "<b>Kimnikiga borasiz?</b>"
        elif rname == "TUZOQCHI":
            prompt_header = "<b>Tuzoqni kimga qo'yasiz?</b>"
        elif rname == "ZOMBI":
            prompt_header = "<b>Kimni tishlaysiz?</b>"

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
            group_action_msg = "🤵🏻 <b>Don o'ljasini tanladi...</b>"
        elif rname in ["DOCTOR", "HAMSHIRA"]:
            group_action_msg = "👨🏼‍⚕️ <b>Shifokor kimnidir davolashga yo'l oldi...</b>"
        elif rname in ["DETECTIVE", "KOMISSAR", "SHERIFF"]:
            if act_code == "sht":
                group_action_msg = "🔫 <b>Komissar qurolini shaylab, nishonni tanladi...</b>"
            else:
                group_action_msg = "🕵🏻‍♂️ <b>Komissar shubhali shaxsni tekshirishga kirishdi...</b>"
        elif rname == "QOTIL":
            group_action_msg = "🔪 <b>Qotil o'zining qonli o'ljasini belgiladi...</b>"
        elif rname == "KEZUVCHI":
            group_action_msg = "💃 <b>Kezuvchi bugun tunni kim bilan o'tkazishni tanladi...</b>"
        elif rname == "DAYDI":
            group_action_msg = "🍾 <b>Daydi kimnikigadir mehmonga ketdi...</b>"
        elif rname == "ADVOKAT":
            group_action_msg = "💼 <b>Advokat o'z himoyasidagi shaxsni tanladi...</b>"
        elif rname == "UBIYTSA":
            group_action_msg = "🥷 <b>Ubiytsa pinhona qadamlar bilan nishon tomon yo'l oldi...</b>"
        elif rname == "TUZOQCHI":
            group_action_msg = "🕸 <b>Tuzoqchi o'z tuzog'ini joylashtirdi...</b>"
        elif rname == "ZOMBI":
            group_action_msg = "🧟 <b>Zombi navbatdagi qurbonini tishlashga oshiqmoqda...</b>"
        elif rname == "KIMYOGAR":
            group_action_msg = "🧪 <b>Kimyogar maxfiy eliksirini tayyorlab, nishonni tanladi...</b>"
        elif rname == "AXMOQ":
            group_action_msg = "🤪 <b>Axmoq ko'chada tentirab yurib, bir eshikni taqillatdi...</b>"
        elif rname == "BUQALAMUN":
            group_action_msg = "🦎 <b>Buqalamun o'z yangi qiyofasini tanladi...</b>"
        elif rname == "RAIS":
            group_action_msg = "🏛 <b>Rais shahar xazinasidan kimnidir mukofotlashga qaror qildi...</b>"
        elif rname == "JOKER":
            group_action_msg = "🃏 <b>Joker o'zining portlovchi sovg'asini tayyorladi...</b>"

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

        # Notify Serjant if Komissar acted
        if actor.role and actor.role.name in ['DETECTIVE', 'KOMISSAR', 'SHERIFF']:
            serjant = await sync_to_async(
                lambda: Player.objects.filter(game=game, is_alive=True, role__name='SERJANT').first()
            )()
            if serjant:
                act_name = "Tekshiruv" if act_code == 'inv' else "Otish"
                try:
                    await bot.send_message(
                        serjant.telegram_user_id,
                        f"🕵🏻‍♂️ <b>Komissar {act_name} harakatini bajardi:</b>\nNishon: <b>{html.escape(target_name)}</b>",
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

    # 2. Night Chat Relays
    try:
        player = await sync_to_async(
            lambda: Player.objects.select_related('role', 'game')
            .filter(
                telegram_user_id=user_id,
                is_alive=True,
                game__phase=GamePhase.NIGHT,
            ).first()
        )()

        if not player or not player.role:
            return

        game = player.game
        sender_name = player.display_name or message.from_user.first_name or "O'yinchi"
        r_name = player.role.name
        r_icon = role_icon(r_name)
        r_lbl = role_label(r_name)

        # Mafia Team Relay (Don, Mafia, Advokat, Ubiytsa, Jurnalist, Aygoqchi, Laborant)
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

        # Police Team Relay (Komissar <-> Serjant)
        elif r_name in ['DETECTIVE', 'KOMISSAR', 'SHERIFF', 'SERJANT']:
            police_partners = await sync_to_async(
                lambda: list(
                    Player.objects.filter(
                        game=game, is_alive=True, role__name__in=['DETECTIVE', 'KOMISSAR', 'SHERIFF', 'SERJANT']
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
                await message.answer("✅ Politsiya xabari yetkazildi.")

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

        await _check_and_advance_night_if_ready(game, bot)
    except Exception as e:
        logger.exception("Error in konchi mine callback:")
        await callback.answer(f"Xatolik: {e}", show_alert=True)
