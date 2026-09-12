import asyncio
import random
import logging
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from asgiref.sync import sync_to_async

from apps.economy.services import HeroService, EconomyService
from apps.economy.models import Inventory
from apps.games.models import Game, Player, GamePhase, RoleTeam
from apps.users.models import User
from apps.stats.models import PlayerProfile
from apps.superadmin.services import TextService, SettingService
from bot_runtime.keyboards.inline import build_my_hero_keyboard

logger = logging.getLogger(__name__)

router = Router(name="hero")


class HeroFSM(StatesGroup):
    waiting_create_name = State()
    waiting_rename = State()
    waiting_transfer_target = State()


def _get_display_name(user: types.User) -> str:
    """Helper to extract user name safely."""
    if user.first_name:
        return user.first_name
    if user.username:
        return f"@{user.username}"
    return f"User {user.id}"


def _get_target_user_info(message: types.Message) -> tuple[int, str]:
    """Extracts target telegram_id and display_name from reply or sender."""
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
        return target.id, _get_display_name(target)
    sender = message.from_user
    return sender.id, _get_display_name(sender)


# ---------------------------------------------------------------------------
# /geroyinfo (and /hero, /geroy) command handler (Groups & PM)
# ---------------------------------------------------------------------------
@router.message(Command("geroyinfo", "hero", "geroy"))
async def handle_geroyinfo(message: types.Message):
    """
    Displays full rich hero stats or 'Geroy mavjud emas' message.
    Supports replying to another player's message to view their hero.
    """
    target_id, target_name = _get_target_user_info(message)

    hero = await sync_to_async(HeroService.get_hero)(telegram_id=target_id)
    if not hero:
        text = HeroService.format_no_hero_text(target_name)
        await message.answer(text, parse_mode="HTML")
        return

    # Count geroy_himoya items
    def _count_defense_items(tg_id: int) -> int:
        inv = Inventory.objects.filter(telegram_id=tg_id, item__code='geroy_himoya', is_active=True).first()
        return inv.quantity if inv else 0

    geroy_himoya_count = await sync_to_async(_count_defense_items)(target_id)
    text = HeroService.format_hero_card_text(hero, geroy_himoya_count)
    await message.answer(text, parse_mode="HTML")


# ---------------------------------------------------------------------------
# /myhero PM Interactive View
# ---------------------------------------------------------------------------
@router.message(Command("myhero", "mening_geroyim"))
async def handle_myhero_command(message: types.Message):
    """Opens interactive Mening Geroyim dashboard in PM."""
    user_id = message.from_user.id
    hero = await sync_to_async(HeroService.get_hero)(telegram_id=user_id)

    def _count_defense(tg_id: int) -> int:
        inv = Inventory.objects.filter(telegram_id=tg_id, item__code='geroy_himoya', is_active=True).first()
        return inv.quantity if inv else 0

    geroy_himoya_count = await sync_to_async(_count_defense)(user_id)

    if not hero:
        text = (
            "🥷 <b>Mening Geroyim</b>\n\n"
            "Sizda hali shaxsiy Geroy mavjud emas!\n"
            "Geroy orqali o'yinda (Don yoki Komissar bo'lganda) kunduzi ham dushmanlaringizga o'q uzishingiz mumkin.\n\n"
            "Geroy narxi: <b>80 💎</b> olmos."
        )
        kb = build_my_hero_keyboard(hero=None, tg_id=user_id)
    else:
        text = HeroService.format_hero_card_text(hero, geroy_himoya_count)
        kb = build_my_hero_keyboard(hero=hero, recharge_cost=hero.recharge_cost_diamonds, tg_id=user_id)

    await message.reply(text, reply_markup=kb, parse_mode="HTML")


# ---------------------------------------------------------------------------
# Callback handlers for Geroy Menu
# ---------------------------------------------------------------------------
@router.callback_query(F.data == "hero:recharge")
async def handle_hero_recharge(callback: types.CallbackQuery):
    """Recharges hero +10 charges."""
    user_id = callback.from_user.id
    success, msg, charges = await sync_to_async(HeroService.recharge_hero)(telegram_id=user_id)
    await callback.answer(msg, show_alert=True)

    if success:
        hero = await sync_to_async(HeroService.get_hero)(telegram_id=user_id)
        def _count_defense(tg_id: int) -> int:
            inv = Inventory.objects.filter(telegram_id=tg_id, item__code='geroy_himoya', is_active=True).first()
            return inv.quantity if inv else 0
        def_count = await sync_to_async(_count_defense)(user_id)
        text = HeroService.format_hero_card_text(hero, def_count)
        kb = build_my_hero_keyboard(hero=hero, recharge_cost=hero.recharge_cost_diamonds, tg_id=user_id)
        try:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            pass


@router.callback_query(F.data == "hero:toggle")
async def handle_hero_toggle(callback: types.CallbackQuery):
    """Toggles hero active status ON/OFF."""
    user_id = callback.from_user.id
    success, is_active = await sync_to_async(HeroService.toggle_hero)(telegram_id=user_id)
    if not success:
        await callback.answer("Sizda Geroy mavjud emas!", show_alert=True)
        return

    status_str = "🟢 Faol" if is_active else "🔴 O'chirilgan"
    await callback.answer(f"Geroy holati: {status_str}", show_alert=False)

    hero = await sync_to_async(HeroService.get_hero)(telegram_id=user_id)
    def _count_defense(tg_id: int) -> int:
        inv = Inventory.objects.filter(telegram_id=tg_id, item__code='geroy_himoya', is_active=True).first()
        return inv.quantity if inv else 0
    def_count = await sync_to_async(_count_defense)(user_id)
    text = HeroService.format_hero_card_text(hero, def_count)
    kb = build_my_hero_keyboard(hero=hero, recharge_cost=hero.recharge_cost_diamonds, tg_id=user_id)
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass


@router.callback_query(F.data == "hero:create_prompt")
async def handle_hero_create_prompt(callback: types.CallbackQuery, state: FSMContext):
    """Prompts user to enter name for their new hero."""
    await callback.message.reply(
        "🥷 <b>Yangi Geroy Yaratish</b>\n\n"
        "Iltimos, yangi Geroyingiz uchun nom kiriting (Masalan: <i>Qora Qoplon</i>):\n"
        "(Narxi: 80 💎 olmos)",
        parse_mode="HTML"
    )
    await state.set_state(HeroFSM.waiting_create_name)
    await callback.answer()


@router.message(HeroFSM.waiting_create_name)
async def handle_hero_create_submit(message: types.Message, state: FSMContext):
    """Processes new hero creation from user input name."""
    name = message.text.strip()
    user_id = message.from_user.id
    owner_name = _get_display_name(message.from_user)

    success, msg, hero = await sync_to_async(HeroService.create_hero)(
        telegram_id=user_id,
        name=name,
        owner_name=owner_name,
        price_diamonds=80
    )
    await state.clear()
    await message.reply(msg, parse_mode="HTML")

    if success and hero:
        text = HeroService.format_hero_card_text(hero, 0)
        kb = build_my_hero_keyboard(hero=hero, recharge_cost=hero.recharge_cost_diamonds, tg_id=user_id)
        await message.reply(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "hero:rename_prompt")
async def handle_hero_rename_prompt(callback: types.CallbackQuery, state: FSMContext):
    """Prompts user to enter new name for their hero."""
    from apps.superadmin.services import SettingService
    cost = SettingService.get_int('price_hero_rename', 5)
    await callback.message.reply(
        "✏️ <b>Geroy Nomini O'zgartirish</b>\n\n"
        f"Iltimos, yangi nomni yuboring:\n"
        f"(Xizmat narxi: <b>{cost} 💎</b> olmos)",
        parse_mode="HTML"
    )
    await state.set_state(HeroFSM.waiting_rename)
    await callback.answer()


@router.message(HeroFSM.waiting_rename)
async def handle_hero_rename_submit(message: types.Message, state: FSMContext):
    """Processes renaming of player hero."""
    new_name = message.text.strip()
    user_id = message.from_user.id
    success, msg = await sync_to_async(HeroService.rename_hero)(telegram_id=user_id, new_name=new_name)
    await state.clear()
    await message.reply(msg, parse_mode="HTML")

    if success:
        hero = await sync_to_async(HeroService.get_hero)(telegram_id=user_id)
        def _count_defense(tg_id: int) -> int:
            inv = Inventory.objects.filter(telegram_id=tg_id, item__code='geroy_himoya', is_active=True).first()
            return inv.quantity if inv else 0
        def_count = await sync_to_async(_count_defense)(user_id)
        text = HeroService.format_hero_card_text(hero, def_count)
        kb = build_my_hero_keyboard(hero=hero, recharge_cost=hero.recharge_cost_diamonds, tg_id=user_id)
        await message.reply(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "hero:transfer_prompt")
async def handle_hero_transfer_prompt(callback: types.CallbackQuery, state: FSMContext):
    """Prompts user for recipient username or ID to transfer hero."""
    await callback.message.reply(
        "🎁 <b>Geroyni Boshqa O'yinchiga O'tkazish</b>\n\n"
        "Iltimos, Geroyni qabul qiluvchi o'yinchining Telegram ID raqamini yoki @username ini yuboring:",
        parse_mode="HTML"
    )
    await state.set_state(HeroFSM.waiting_transfer_target)
    await callback.answer()


@router.message(HeroFSM.waiting_transfer_target)
async def handle_hero_transfer_submit(message: types.Message, state: FSMContext):
    """Executes hero transfer to another player."""
    raw_input = message.text.strip().replace('@', '')
    sender_id = message.from_user.id

    def _find_recipient(target_str: str):
        if target_str.isdigit():
            tg_id = int(target_str)
            user = User.objects.filter(telegram_id=tg_id).first()
            name = user.first_name if user else f"O'yinchi {tg_id}"
            return tg_id, name
        user = User.objects.filter(username__iexact=target_str).first()
        if user and user.telegram_id:
            return user.telegram_id, user.first_name or f"@{user.username}"
        return None, None

    recip_id, recip_name = await sync_to_async(_find_recipient)(raw_input)
    if not recip_id:
        await message.reply("❌ Bunday foydalanuvchi topilmadi! Iltimos qaytadan tekshirib yuboring.")
        await state.clear()
        return

    success, msg = await sync_to_async(HeroService.transfer_hero)(
        sender_tg_id=sender_id,
        recipient_tg_id=recip_id,
        new_owner_name=recip_name
    )
    await state.clear()
    await message.reply(msg, parse_mode="HTML")


# ---------------------------------------------------------------------------
# In-Game Daytime Hero Shooting (/shoot, /otish, /ot)
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# In-Game Daytime / Dawn Hero Shooting
# ---------------------------------------------------------------------------

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


def _role_icon(name: str) -> str:
    return ROLE_ICONS.get((name or '').upper(), "👤")


async def _resolve_game_and_players(game_id_str: str, shooter_id_str: str, target_id_str: str = None):
    def _db_get():
        g = Game.objects.filter(id__startswith=game_id_str).first()
        if not g:
            return None, None, None
        sp = Player.objects.filter(game=g, id__startswith=shooter_id_str).select_related('role').first()
        tp = None
        if target_id_str:
            tp = Player.objects.filter(game=g, id__startswith=target_id_str).select_related('role').first()
        return g, sp, tp
    return await sync_to_async(_db_get)()


# ---------------------------------------------------------------------------
# Dawn Interactive Hero Callbacks
# ---------------------------------------------------------------------------
@router.callback_query(lambda c: c.data and c.data.startswith("hero_dawn:no:"))
async def handle_hero_dawn_no(callback: types.CallbackQuery):
    """Player declines to use Hero at Dawn."""
    try:
        await callback.message.edit_text("❌ <b>Geroy ishlatilmadi.</b>", parse_mode="HTML")
    except Exception:
        pass
    await callback.answer("Geroy ishlatilmadi.")


@router.callback_query(lambda c: c.data and c.data.startswith("hero_dawn:yes:"))
async def handle_hero_dawn_yes(callback: types.CallbackQuery):
    """Player chooses to use Hero at Dawn -> displays target selection keyboard."""
    parts = callback.data.split(":")
    if len(parts) < 4:
        await callback.answer("Xatolik!")
        return

    gid = parts[2]
    spid = parts[3]

    game, shooter, _ = await _resolve_game_and_players(gid, spid)
    if not game or not shooter or not shooter.is_alive:
        await callback.answer("O'yin yakunlangan yoki siz o'yindan chiqqansiz!", show_alert=True)
        return

    living_players = await sync_to_async(
        lambda: list(game.players.filter(is_alive=True).exclude(id=shooter.id).order_by('id'))
    )()

    if not living_players:
        await callback.answer("Tirik nishonlar mavjud emas!", show_alert=True)
        return

    from bot_runtime.keyboards.inline import build_hero_dawn_targets_keyboard
    kb = build_hero_dawn_targets_keyboard(str(game.id), str(shooter.id), living_players)
    await callback.message.edit_text(
        "🎯 <b>Nishonni tanlang:</b>\n\nQaysi o'yinchiga zarba bermoqchisiz?",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("hero_dawn:target:"))
async def handle_hero_dawn_target(callback: types.CallbackQuery, bot: Bot):
    """Executes the Hero strike at Dawn against the chosen target."""
    parts = callback.data.split(":")
    if len(parts) < 5:
        await callback.answer("Xatolik!")
        return

    gid = parts[2]
    spid = parts[3]
    tpid = parts[4]

    game, shooter, target = await _resolve_game_and_players(gid, spid, tpid)
    if not game or not shooter or not target:
        await callback.answer("O'yin yoki nishon topilmadi!", show_alert=True)
        return

    if not shooter.is_alive:
        await callback.answer("Siz allaqachon o'yindan chiqqansiz!", show_alert=True)
        return
    if not target.is_alive:
        await callback.answer("Nishon allaqachon halok bo'lgan!", show_alert=True)
        return

    res = await sync_to_async(HeroService.execute_hero_strike)(game, shooter, target)
    if not res.get('ok'):
        await callback.answer(res.get('error', "Xatolik yuz berdi!"), show_alert=True)
        return

    hero = res['hero']
    shooter_name = shooter.display_name or shooter.username or f"O'yinchi {shooter.telegram_user_id}"
    target_name = target.display_name or target.username or f"O'yinchi {target.telegram_user_id}"
    r_name = target.role.name if target.role else 'CITIZEN'
    r_icon = _role_icon(r_name)

    if res.get('blocked'):
        # Blocked by 🔰 Geroydan himoya
        try:
            await callback.message.edit_text(
                f"🔰 <b>{target_name}</b> ning <b>Geroydan Himoyasi</b> zarbani qaytardi!\n"
                f"🩸 Qolgan zaryadingiz: {res['charges_left']} ta.",
                parse_mode="HTML"
            )
        except Exception:
            pass

        try:
            await bot.send_message(
                target.telegram_user_id,
                "🔰 <b>Sizga qarshi Geroy zarbasi berildi!</b>\n\n"
                "🛡 Profilingizdagi <b>Geroydan Himoya</b> qalqoni bu zarbani to'liq qaytardi va hayotingizni saqlab qoldi!\n"
                "ℹ️ <i>1 ta himoya qalqoningiz sarflandi.</i>",
                parse_mode="HTML"
            )
        except Exception:
            pass

        tpl = await sync_to_async(TextService.get_text)(
            'hero_group_strike_blocked',
            fallback="💥 Kimdir o'z Geroyidan foydalanib <b>{target_name}</b>ga zarba berdi!\n\n🔰 <b>{target_name}</b> ning <b>Geroydan Himoyasi</b> zarbani to'liq qaytardi va uning hayotini saqlab qoldi!"
        )
        group_msg = tpl.format(target_name=target_name)
        try:
            await bot.send_message(game.chat_id, group_msg, parse_mode="HTML")
        except Exception:
            pass
        await callback.answer("Zarba berildi!")
        return

    # Not blocked
    if res.get('killed'):
        try:
            await callback.message.edit_text(
                f"☠️ <b>{target_name}</b> {res['damage']}% zarba bilan halok qilindi!\n"
                f"⭐ Geroyingizga <b>+150 ball</b> qo'shildi! (Jami: {hero.score} ball, Daraja: {hero.level})\n"
                f"🩸 Qolgan zaryad: {res['charges_left']} ta.",
                parse_mode="HTML"
            )
        except Exception:
            pass

        from bot_runtime.handlers.night import LAST_WORDS_PENDING, _expire_last_words
        try:
            await bot.send_message(
                target.telegram_user_id,
                f"💥 <b>Sizga qarshi Geroy zarbasi berildi!</b>\n\n"
                f"🩸 Yetkazilgan zarar: <b>{res['damage']}%</b>\n"
                f"❤️ Qolgan joningiz: <b>0%</b>\n\n"
                f"☠️ <b>Siz olgan og'ir jarohat tufayli halok bo'ldingiz!</b>\n\n"
                f"🗣 <b>So'ngi so'zingizni aytishingiz uchun 50 sekund vaqt berildi:</b>\n"
                f"<i>Qisqa so'ngi so'zingizni yozing (guruhga e'lon qilinadi):</i>",
                parse_mode="HTML"
            )
            LAST_WORDS_PENDING[target.telegram_user_id] = {
                'game_id': str(game.id),
                'chat_id': game.chat_id,
                'role_name': r_name,
                'display_name': target.display_name,
            }
            asyncio.create_task(_expire_last_words(target.telegram_user_id))
        except Exception:
            pass

        if res.get('leveled_up'):
            try:
                await bot.send_message(
                    shooter.telegram_user_id,
                    f"🎉 <b>Tabriklaymiz!</b>\n"
                    f"Geroyingiz <b>{hero.level}</b>-darajaga ko'tarildi va +10 🖤 Himoyaga ega bo'ldi! (Jami himoya: {hero.current_defense})",
                    parse_mode="HTML"
                )
            except Exception:
                pass

        tpl1 = await sync_to_async(TextService.get_text)(
            'hero_group_strike_kill_part1',
            fallback="💥 Kimdir o'z Geroyidan foydalanib <b>{target_name}</b>ga {damage}% shikast yetkazdi!"
        )
        msg1 = tpl1.format(target_name=target_name, damage=res['damage'])

        tpl2 = await sync_to_async(TextService.get_text)(
            'hero_group_strike_kill_part2',
            fallback="☠️ <b>{target_name}</b> Geroy tomonidan o'ldirildi! (U: {role_icon} <b>{role_name}</b> edi)"
        )
        msg2 = tpl2.format(target_name=target_name, role_icon=r_icon, role_name=r_name)

        try:
            await bot.send_message(game.chat_id, msg1, parse_mode="HTML")
            await asyncio.sleep(0.4)
            await bot.send_message(game.chat_id, msg2, parse_mode="HTML")
        except Exception:
            pass

        # Check win condition
        from apps.games.engine.win_conditions import WinConditionService
        from apps.games.engine.game_service import GameService
        winner = await sync_to_async(WinConditionService.check_win_condition)(game)
        if winner:
            await asyncio.sleep(2.0)
            await sync_to_async(GameService.finish_game)(game, winner)
            from bot_runtime.handlers.night import _announce_game_winner
            await _announce_game_winner(game, winner, bot)
    else:
        try:
            await callback.message.edit_text(
                f"💥 <b>{target_name}</b> ga {res['damage']}% shikast yetkazildi!\n"
                f"🩸 Qolgan joni: <b>{res['remaining_hp']}% ❤️</b>\n"
                f"🩸 Qolgan zaryad: {res['charges_left']} ta.",
                parse_mode="HTML"
            )
        except Exception:
            pass

        try:
            await bot.send_message(
                target.telegram_user_id,
                f"💥 <b>Sizga qarshi Geroy zarbasi berildi!</b>\n\n"
                f"🩸 Yetkazilgan zarar: <b>{res['damage']}%</b>\n"
                f"❤️ Qolgan joningiz: <b>{res['remaining_hp']}%</b>\n\n"
                f"ℹ️ <i>Ehtiyot bo'ling! Guruhdagi o'yinchilar ro'yxatida joningiz holati ({res['remaining_hp']}%) ko'rsatildi.</i>",
                parse_mode="HTML"
            )
        except Exception:
            pass

        tpl = await sync_to_async(TextService.get_text)(
            'hero_group_strike_hit',
            fallback="💥 Kimdir o'z Geroyidan foydalanib <b>{target_name}</b>ga {damage}% shikast yetkazdi!\n🩸 <b>{target_name}</b> ning qolgan joni: <b>{remaining_hp}% ❤️</b>"
        )
        group_msg = tpl.format(target_name=target_name, damage=res['damage'], remaining_hp=res['remaining_hp'])
        try:
            await bot.send_message(game.chat_id, group_msg, parse_mode="HTML")
        except Exception:
            pass

    await callback.answer("Zarba berildi!")


# ---------------------------------------------------------------------------
# /shoot, /otish, /ot Group Command
# ---------------------------------------------------------------------------
@router.message(Command("shoot", "zarba", "kill", "otish", "ot", ignore_case=True))
async def handle_daytime_hero_shoot(message: types.Message, bot: Bot):
    """Allows players with living heroes to strike another player during Daytime/Dawn.
    Usage: /shoot (reply to victim) or /shoot @username / /shoot {player_number}
    Preserves 100% anonymity by deleting the command message and sending errors to PM.
    """
    if message.chat.type in ["private"]:
        await message.reply("Bu buyruq faqat o'yin ketayotgan guruhda ishlaydi!")
        return

    chat_id = message.chat.id
    shooter_tg_id = message.from_user.id
    shooter_name = _get_display_name(message.from_user)

    # Immediately try to delete the shooter's message in the group to keep identity hidden
    try:
        await message.delete()
    except Exception:
        pass

    async def _send_private_error(err_text: str):
        try:
            await bot.send_message(shooter_tg_id, err_text, parse_mode="HTML")
        except Exception:
            pass

    # 1. Find active game in this chat
    def _get_active_game(c_id: int):
        return Game.objects.filter(chat_id=c_id, phase__in=[GamePhase.DAY, GamePhase.DISCUSSION, GamePhase.VOTING]).first()

    game = await sync_to_async(_get_active_game)(chat_id)
    if not game:
        await _send_private_error("⚠️ Hozirda ushbu guruhda kunduzgi bosqichdagi faol o'yin mavjud emas!")
        return

    # 2. Check shooter role and living status
    def _get_shooter_player(g_obj, tg_id):
        return Player.objects.filter(game=g_obj, telegram_user_id=tg_id, is_alive=True).select_related('role').first()

    shooter_player = await sync_to_async(_get_shooter_player)(game, shooter_tg_id)
    if not shooter_player:
        await _send_private_error("⚠️ Siz bu o'yinda qatnashmayapsiz yoki allaqachon o'yindan chiqqansiz!")
        return

    role_code = (shooter_player.role.code.lower() if (shooter_player.role and hasattr(shooter_player.role, 'code')) else '')
    role_name = (shooter_player.role.name or '').upper() if shooter_player.role else ''
    if role_code not in ['don', 'komissar', 'detective'] and role_name not in ['DON', 'KOMISSAR', 'DETECTIVE']:
        await _send_private_error("🥷 Geroy faqatkina o'yindagi rolingiz <b>Don</b> yoki <b>Komissar</b> bo'lsagina o't ocha oladi!")
        return

    # 3. Check shooter hero and charges
    hero = await sync_to_async(HeroService.get_hero)(telegram_id=shooter_tg_id)
    if not hero or not hero.is_active:
        await _send_private_error("⚠️ Sizda faol Geroy mavjud emas!")
        return

    if hero.charges <= 0:
        await _send_private_error(
            "🩸 Geroyingizning zaryadi tugagan (0 ta zaryad)!\n"
            "Lichkada /myhero buyrug'i orqali zaryadlang."
        )
        return

    # 4. Identify victim
    target_tg_id = None
    if message.reply_to_message and message.reply_to_message.from_user:
        target_tg_id = message.reply_to_message.from_user.id
    else:
        args = message.text.split()
        if len(args) > 1:
            arg = args[1].strip()
            if arg.isdigit():
                num = int(arg)
                def _get_by_num(g_obj, p_num):
                    players = list(Player.objects.filter(game=g_obj, is_alive=True).order_by('id'))
                    if 1 <= p_num <= len(players):
                        return players[p_num - 1].telegram_user_id
                    return None
                target_tg_id = await sync_to_async(_get_by_num)(game, num)
            elif arg.startswith('@'):
                u_clean = arg.replace('@', '').strip()
                def _get_by_un(g_obj, u_name):
                    p = Player.objects.filter(game=g_obj, is_alive=True, username__iexact=u_name).first()
                    if p:
                        return p.telegram_user_id
                    from apps.stats.models import PlayerProfile
                    prof = PlayerProfile.objects.filter(telegram_username__iexact=u_name).first()
                    return prof.telegram_id if prof else None
                target_tg_id = await sync_to_async(_get_by_un)(game, u_clean)

    if not target_tg_id or target_tg_id == shooter_tg_id:
        await _send_private_error("⚠️ Iltimos, nishonga olingan o'yinchining xabariga reply qilib yoki <code>/shoot @username</code> yuboring!")
        return

    def _get_victim_player(g_obj, tg_id):
        return Player.objects.filter(game=g_obj, telegram_user_id=tg_id, is_alive=True).select_related('role').first()

    victim_player = await sync_to_async(_get_victim_player)(game, target_tg_id)
    if not victim_player:
        await _send_private_error("⚠️ Nishon o'yinda mavjud emas yoki allaqachon o'lgan!")
        return

    # Execute Strike
    res = await sync_to_async(HeroService.execute_hero_strike)(game, shooter_player, victim_player)
    if not res.get('ok'):
        await _send_private_error(res.get('error', "Xatolik yuz berdi!"))
        return

    victim_name = victim_player.display_name or victim_player.username or f"O'yinchi {target_tg_id}"
    r_name = victim_player.role.name if victim_player.role else 'CITIZEN'
    r_icon = _role_icon(r_name)

    if res.get('blocked'):
        try:
            await bot.send_message(
                shooter_tg_id,
                f"🔰 <b>{victim_name}</b> ning <b>Geroydan Himoyasi</b> zarbani qaytardi!\n"
                f"🩸 Qolgan zaryadingiz: {res['charges_left']} ta.",
                parse_mode="HTML"
            )
        except Exception:
            pass

        try:
            await bot.send_message(
                victim_player.telegram_user_id,
                "🔰 <b>Sizga qarshi Geroy zarbasi berildi!</b>\n\n"
                "🛡 Profilingizdagi <b>Geroydan Himoya</b> qalqoni bu zarbani to'liq qaytardi va hayotingizni saqlab qoldi!\n"
                "ℹ️ <i>1 ta himoya qalqoningiz sarflandi.</i>",
                parse_mode="HTML"
            )
        except Exception:
            pass

        tpl = await sync_to_async(TextService.get_text)(
            'hero_group_strike_blocked',
            fallback="💥 Kimdir o'z Geroyidan foydalanib <b>{target_name}</b>ga zarba berdi!\n\n🔰 <b>{target_name}</b> ning <b>Geroydan Himoyasi</b> zarbani to'liq qaytardi va uning hayotini saqlab qoldi!"
        )
        await bot.send_message(chat_id, tpl.format(target_name=victim_name), parse_mode="HTML")
        return

    if res.get('killed'):
        try:
            await bot.send_message(
                shooter_tg_id,
                f"☠️ <b>{victim_name}</b> {res['damage']}% zarba bilan halok qilindi!\n"
                f"⭐ Geroyingizga <b>+150 ball</b> qo'shildi! (Jami: {hero.score} ball, Daraja: {hero.level})\n"
                f"🩸 Qolgan zaryad: {res['charges_left']} ta.",
                parse_mode="HTML"
            )
        except Exception:
            pass

        from bot_runtime.handlers.night import LAST_WORDS_PENDING, _expire_last_words
        try:
            await bot.send_message(
                victim_player.telegram_user_id,
                f"💥 <b>Sizga qarshi Geroy zarbasi berildi!</b>\n\n"
                f"🩸 Yetkazilgan zarar: <b>{res['damage']}%</b>\n"
                f"❤️ Qolgan joningiz: <b>0%</b>\n\n"
                f"☠️ <b>Siz olgan og'ir jarohat tufayli halok bo'ldingiz!</b>\n\n"
                f"🗣 <b>So'ngi so'zingizni aytishingiz uchun 50 sekund vaqt berildi:</b>\n"
                f"<i>Qisqa so'ngi so'zingizni yozing (guruhga e'lon qilinadi):</i>",
                parse_mode="HTML"
            )
            LAST_WORDS_PENDING[victim_player.telegram_user_id] = {
                'game_id': str(game.id),
                'chat_id': game.chat_id,
                'role_name': r_name,
                'display_name': victim_player.display_name,
            }
            asyncio.create_task(_expire_last_words(victim_player.telegram_user_id))
        except Exception:
            pass

        tpl1 = await sync_to_async(TextService.get_text)(
            'hero_group_strike_kill_part1',
            fallback="💥 Kimdir o'z Geroyidan foydalanib <b>{target_name}</b>ga {damage}% shikast yetkazdi!"
        )
        msg1 = tpl1.format(target_name=victim_name, damage=res['damage'])

        tpl2 = await sync_to_async(TextService.get_text)(
            'hero_group_strike_kill_part2',
            fallback="☠️ <b>{target_name}</b> Geroy tomonidan o'ldirildi! (U: {role_icon} <b>{role_name}</b> edi)"
        )
        msg2 = tpl2.format(target_name=victim_name, role_icon=r_icon, role_name=r_name)

        await bot.send_message(chat_id, msg1, parse_mode="HTML")
        await asyncio.sleep(0.4)
        await bot.send_message(chat_id, msg2, parse_mode="HTML")

        if res.get('leveled_up'):
            try:
                await bot.send_message(
                    shooter_tg_id,
                    f"🎉 <b>Tabriklaymiz!</b>\n"
                    f"Geroyingiz <b>{hero.level}</b>-darajaga ko'tarildi va +10 🖤 Himoyaga ega bo'ldi!",
                    parse_mode="HTML"
                )
            except Exception:
                pass

        # Check win condition
        from apps.games.engine.win_conditions import WinConditionService
        from apps.games.engine.game_service import GameService
        winner = await sync_to_async(WinConditionService.check_win_condition)(game)
        if winner:
            await asyncio.sleep(2.0)
            await sync_to_async(GameService.finish_game)(game, winner)
            from bot_runtime.handlers.night import _announce_game_winner
            await _announce_game_winner(game, winner, bot)
    else:
        try:
            await bot.send_message(
                shooter_tg_id,
                f"💥 <b>{victim_name}</b> ga {res['damage']}% shikast yetkazildi!\n"
                f"🩸 Qolgan joni: <b>{res['remaining_hp']}% ❤️</b>\n"
                f"🩸 Qolgan zaryad: {res['charges_left']} ta.",
                parse_mode="HTML"
            )
        except Exception:
            pass

        try:
            await bot.send_message(
                victim_player.telegram_user_id,
                f"💥 <b>Sizga qarshi Geroy zarbasi berildi!</b>\n\n"
                f"🩸 Yetkazilgan zarar: <b>{res['damage']}%</b>\n"
                f"❤️ Qolgan joningiz: <b>{res['remaining_hp']}%</b>\n\n"
                f"ℹ️ <i>Ehtiyot bo'ling! Guruhdagi o'yinchilar ro'yxatida joningiz holati ({res['remaining_hp']}%) ko'rsatildi.</i>",
                parse_mode="HTML"
            )
        except Exception:
            pass

        tpl = await sync_to_async(TextService.get_text)(
            'hero_group_strike_hit',
            fallback="💥 Kimdir o'z Geroyidan foydalanib <b>{target_name}</b>ga {damage}% shikast yetkazdi!\n🩸 <b>{target_name}</b> ning qolgan joni: <b>{remaining_hp}% ❤️</b>"
        )
        await bot.send_message(chat_id, tpl.format(target_name=victim_name, damage=res['damage'], remaining_hp=res['remaining_hp']), parse_mode="HTML")

