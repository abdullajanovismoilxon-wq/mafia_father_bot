import random
import logging
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from asgiref.sync import sync_to_async

from apps.economy.services import HeroService, EconomyService
from apps.economy.models import Inventory
from apps.games.models import Game, Player, GamePhase, RoleTeam
from apps.users.models import User
from apps.stats.models import PlayerProfile
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
        await message.reply(text, parse_mode="HTML")
        return

    # Count geroy_himoya items
    def _count_defense_items(tg_id: int) -> int:
        inv = Inventory.objects.filter(telegram_id=tg_id, item__code='geroy_himoya', is_active=True).first()
        return inv.quantity if inv else 0

    geroy_himoya_count = await sync_to_async(_count_defense_items)(target_id)
    text = HeroService.format_hero_card_text(hero, geroy_himoya_count)
    await message.reply(text, parse_mode="HTML")


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
@router.message(Command("shoot", "otish", "ot"))
async def handle_daytime_hero_shoot(message: types.Message):
    """
    Daytime Hero shooting by Don or Komissar.
    Usage: /shoot (reply to victim) or /shoot @username / /shoot {player_number}
    """
    if message.chat.type in ["private"]:
        await message.reply("Bu buyruq faqat o'yin ketayotgan guruhda ishlaydi!")
        return

    chat_id = message.chat.id
    shooter_tg_id = message.from_user.id
    shooter_name = _get_display_name(message.from_user)

    # 1. Find active game in this chat
    def _get_active_game(c_id: int):
        return Game.objects.filter(chat_id=c_id, phase__in=[GamePhase.DAY, GamePhase.DISCUSSION, GamePhase.VOTING]).first()

    game = await sync_to_async(_get_active_game)(chat_id)
    if not game:
        await message.reply("Hozirda ushbu guruhda kunduzgi bosqichdagi faol o'yin mavjud emas!")
        return

    # 2. Check shooter role and living status
    def _get_shooter_player(g_obj, tg_id):
        return Player.objects.filter(game=g_obj, telegram_id=tg_id, is_alive=True).select_related('role').first()

    shooter_player = await sync_to_async(_get_shooter_player)(game, shooter_tg_id)
    if not shooter_player:
        await message.reply("Siz bu o'yinda qatnashmayapsiz yoki allaqachon o'yindan chiqqansiz!")
        return

    role_code = (shooter_player.role.code.lower() if shooter_player.role else '')
    if role_code not in ['don', 'komissar', 'detective']:
        await message.reply("🥷 Geroy faqatkina o'yindagi rolingiz <b>Don</b> yoki <b>Komissar</b> bo'lsagina o't ocha oladi!", parse_mode="HTML")
        return

    # 3. Check shooter hero and charges
    hero = await sync_to_async(HeroService.get_hero)(telegram_id=shooter_tg_id)
    if not hero or not hero.is_active:
        await message.reply("Sizda faol Geroy mavjud emas!")
        return

    if hero.charges <= 0:
        await message.reply(
            "🩸 Geroyingizning zaryadi tugagan (0 ta zaryad)!\n"
            "Lichkada /myhero buyrug'i orqali zaryadlang.",
            parse_mode="HTML"
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
                        return players[p_num - 1].telegram_id
                    return None
                target_tg_id = await sync_to_async(_get_by_num)(game, num)
            elif arg.startswith('@'):
                u_clean = arg.replace('@', '')
                def _get_by_un(u_name):
                    u = User.objects.filter(username__iexact=u_name).first()
                    return u.telegram_id if u else None
                target_tg_id = await sync_to_async(_get_by_un)(u_clean)

    if not target_tg_id or target_tg_id == shooter_tg_id:
        await message.reply(
            "Iltimos, nishonga olingan o'yinchining xabariga reply qilib yoki <code>/shoot @username</code> yuboring!",
            parse_mode="HTML"
        )
        return

    # 5. Check victim living in game
    def _get_victim_player(g_obj, tg_id):
        return Player.objects.filter(game=g_obj, telegram_id=tg_id, is_alive=True).first()

    victim_player = await sync_to_async(_get_victim_player)(game, target_tg_id)
    if not victim_player:
        await message.reply("Nishon o'yinda mavjud emas yoki allaqachon o'lgan!")
        return

    # 6. Execute Shot
    hero.charges -= 1
    await sync_to_async(hero.save)(update_fields=['charges'])

    victim_name = victim_player.full_name if hasattr(victim_player, 'full_name') else f"O'yinchi {target_tg_id}"
    dmg_percent = random.randint(hero.power_min, hero.power_max)

    # Check geroy_himoya defense item on victim
    def _consume_geroy_himoya(tg_id: int) -> bool:
        inv = Inventory.objects.filter(telegram_id=tg_id, item__code='geroy_himoya', is_active=True, quantity__gt=0).first()
        if inv:
            inv.quantity -= 1
            if inv.quantity == 0:
                inv.is_active = False
            inv.save(update_fields=['quantity', 'is_active'])
            return True
        return False

    has_shield = await sync_to_async(_consume_geroy_himoya)(target_tg_id)

    if has_shield:
        res_text = (
            f"🥷 <b>{shooter_name}</b> o'z Geroyi (<b>{hero.name}</b>) bilan <b>{victim_name}</b> ga o'q uzdi!\n\n"
            f"🔰 <b>{victim_name}</b> ning <b>Geroydan Himoyasi</b> zarbani to'liq qaytardi va uning hayotini saqlab qoldi!\n"
            f"🩸 Geroydan 1 ta zaryad sarflandi (Qoldi: {hero.charges})."
        )
        await message.reply(res_text, parse_mode="HTML")
        return

    # Lethal strike if damage >= 50%
    victim_killed = dmg_percent >= 50

    if victim_killed:
        def _kill_victim(p):
            p.is_alive = False
            p.save(update_fields=['is_alive'])
        await sync_to_async(_kill_victim)(victim_player)

        # Add kill score to hero (+150 ball)
        await sync_to_async(hero.add_kill_score)(150)

        res_text = (
            f"💥 <b>{shooter_name}</b> o'z Geroyi (<b>{hero.name}</b>) bilan <b>{victim_name}</b> ga nishon olib o't ochdi!\n\n"
            f"☠️ <b>{victim_name}</b> {dmg_percent}% halokatli zarba oqibatida yer tishladi va halok bo'ldi!\n\n"
            f"⭐ Geroyga <b>+150 ball</b> qo'shildi! (Jami: {hero.score} ball, Daraja: {hero.level})\n"
            f"🩸 Qolgan zaryad: {hero.charges} ta."
        )
    else:
        res_text = (
            f"💥 <b>{shooter_name}</b> o'z Geroyi (<b>{hero.name}</b>) bilan <b>{victim_name}</b> ga o'q uzdi!\n"
            f"🩸 <b>{victim_name}</b> {dmg_percent}% jarohat oldi!\n"
            f"🩸 Qolgan zaryad: {hero.charges} ta."
        )

    await message.reply(res_text, parse_mode="HTML")
