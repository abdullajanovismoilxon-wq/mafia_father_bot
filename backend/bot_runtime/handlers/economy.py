"""
MAFIA BOT FATHER — Telegram Economy, Marketplace, Profile & Roles Handlers
===========================================================================
- Interactive /profile with toggle buttons (ON/OFF for Shield, Hang Shield, Docs, Hero Shield)
- Full Marketplace (Do'kon) with instant purchases for Himoya, Osishdan himoya, Hujjat, Geroy, VIP, Active Roles
- Diamond Exchange for Dollars
- Stars & Card Diamond top-ups
- Roles overview & guide (/roles)
- Language switcher (Uzbek, Russian, English)
- Group reply transfers (/money, /give) with 3% commission or 0% VIP
"""
import logging
from decimal import Decimal
from aiogram import Router, types, F, Bot
from aiogram.filters import Command
from asgiref.sync import sync_to_async

from apps.economy.models import (
    Wallet, CurrencyType, TransactionType, Inventory, MarketplaceItem,
    VIPSubscription, VIPLevel
)
from apps.economy.services import EconomyService, InsufficientBalanceError, HeroService
from apps.stats.models import PlayerProfile, PlayerStats
from apps.stats.services import StatsService
from bot_runtime.keyboards.inline import (
    build_profile_interactive_keyboard,
    build_market_main_keyboard,
    build_active_roles_market_keyboard,
    build_sell_active_roles_keyboard,
    build_buy_diamonds_method_keyboard,
    build_buy_diamonds_stars_keyboard,
    build_buy_dollars_keyboard,
    build_my_hero_keyboard,
    build_star_pay_keyboard,
    build_roles_list_keyboard,
    build_role_detail_back_keyboard,
    build_language_keyboard,
    build_rules_back_keyboard,
    build_child_start_keyboard,
)

logger = logging.getLogger(__name__)
router = Router(name="economy_router")

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



# ---------------------------------------------------------------------------
# Helper: Inventory item lookup & counts
# ---------------------------------------------------------------------------

async def _get_inventory_state(telegram_id: int) -> dict:
    """Returns dict of counts and toggle states for player's inventory items."""
    return await sync_to_async(_sync_get_inventory_state)(telegram_id)


def _sync_get_inventory_state(telegram_id: int) -> dict:
    inv_items = Inventory.objects.filter(telegram_id=telegram_id).select_related('item')
    state = {
        'himoya': {'count': 0, 'on': True},
        'osish_himoya': {'count': 0, 'on': True},
        'hujjat': {'count': 0, 'on': True},
        'geroy_himoya': {'count': 0, 'on': True},
        'geroy': {'count': 0, 'on': False, 'games_left': 0},
        'active_role': None,
    }
    for inv in inv_items:
        code = inv.item.code if inv.item else ''
        if code == 'himoya':
            state['himoya'] = {'count': inv.quantity, 'on': inv.is_active}
        elif code == 'osish_himoya':
            state['osish_himoya'] = {'count': inv.quantity, 'on': inv.is_active}
        elif code == 'hujjat':
            state['hujjat'] = {'count': inv.quantity, 'on': inv.is_active}
        elif code == 'geroy_himoya':
            state['geroy_himoya'] = {'count': inv.quantity, 'on': inv.is_active}
        elif code == 'geroy':
            state['geroy'] = {'count': inv.quantity, 'on': inv.is_active, 'games_left': inv.quantity * 50}
        elif code.startswith('role_') and inv.quantity > 0:
            state['active_role'] = inv.item.name
    return state


from apps.economy.models import (
    Wallet, CurrencyType, TransactionType, Inventory, MarketplaceItem,
    MarketplaceCategory, MarketplaceItemType, VIPSubscription, VIPLevel
)


def _get_default_category() -> MarketplaceCategory:
    cat, _ = MarketplaceCategory.objects.get_or_create(
        code='game_items',
        defaults={'name': "O'yin buyumlari", 'icon': '🎒', 'order': 1}
    )
    return cat


def _sync_toggle_item(telegram_id: int, item_code: str) -> bool:
    """Toggles item active state. Returns new state."""
    cat = _get_default_category()
    item, _ = MarketplaceItem.objects.get_or_create(
        code=item_code,
        defaults={
            'category': cat,
            'name': item_code.title(),
            'item_type': MarketplaceItemType.BONUS,
            'price_diamonds': 1
        }
    )
    inv, created = Inventory.objects.get_or_create(
        telegram_id=telegram_id,
        item=item,
        defaults={'quantity': 0, 'is_active': True}
    )
    if created:
        inv.is_active = False
    else:
        inv.is_active = not inv.is_active
    inv.save(update_fields=['is_active'])
    return inv.is_active


def _sync_purchase_item(telegram_id: int, item_code: str) -> tuple[bool, str]:
    """Processes purchase of item using virtual dollars or diamonds."""
    from apps.superadmin.services import SettingService
    prices = {
        'himoya': ('COINS', SettingService.get_int('price_himoya', 300), '🛡 Himoya'),
        'hujjat': ('COINS', SettingService.get_int('price_hujjat', 200), '📁 Hujjatlar'),
        'vaksina': ('COINS', SettingService.get_int('price_vaksina', 150), '💉 Zombi Vaksinasi'),
        'dori_himoya': ('COINS', SettingService.get_int('price_dori_himoya', 130), '💊 Doridan himoya'),
        'sirpanish_himoya': ('COINS', SettingService.get_int('price_sirpanish_himoya', 150), '⛸ Sirpanishdan himoya'),
        'osish_himoya': ('DIAMONDS', SettingService.get_int('price_osish_himoya', 1), '⚖️ Ovozdan himoya'),
        'geroy': ('DIAMONDS', SettingService.get_int('price_geroy', 80), '🥷 Geroy'),
        'geroy_himoya': ('DIAMONDS', SettingService.get_int('price_geroy_himoya', 3), '🔰 Geroydan himoya'),
        'vip_30': ('DIAMONDS', SettingService.get_int('price_vip_30', 30), '⭐️ VIP 30 kun'),
        'role_don': ('DIAMONDS', SettingService.get_int('price_role_don', 2), '🎭 Aktiv rol: Don'),
        'role_komissar': ('DIAMONDS', SettingService.get_int('price_role_komissar', 2), '🎭 Aktiv rol: Komissar'),
        'role_shifokor': ('COINS', SettingService.get_int('price_role_shifokor', 600), '🎭 Aktiv rol: Shifokor'),
        'role_citizen': ('COINS', SettingService.get_int('price_role_citizen', 100), '🎭 Aktiv rol: Tinch aholi'),
    }

    if item_code not in prices:
        return False, "Noma'lum mahsulot."

    currency, price, title = prices[item_code]
    wallet = EconomyService.get_or_create_wallet(telegram_id=telegram_id)
    profile = PlayerProfile.objects.filter(telegram_id=telegram_id).first()

    is_owner = profile and profile.is_platform_owner

    # Check balance (bypass for platform owner @ismoilo9)
    if not is_owner:
        if currency == 'COINS' and wallet.coins < int(price):
            return False, "Kechirasiz, hisobingizda mablag' yetarli emas."
        elif currency == 'DIAMONDS' and wallet.diamonds < int(price):
            return False, "Kechirasiz, hisobingizda mablag' yetarli emas."

        # Deduct
        if currency == 'COINS':
            wallet.coins -= int(price)
            wallet.save(update_fields=['coins'])
        elif currency == 'DIAMONDS':
            wallet.diamonds -= int(price)
            wallet.save(update_fields=['diamonds'])

    # Handle VIP activation
    if item_code == 'vip_30':
        from django.utils import timezone
        from datetime import timedelta
        now = timezone.now()
        vip, created = VIPSubscription.objects.get_or_create(
            telegram_id=telegram_id,
            defaults={
                'vip_level': VIPLevel.GOLD,
                'starts_at': now,
                'expires_at': now + timedelta(days=30),
                'is_active': True,
            }
        )
        if not created:
            base_date = max(vip.expires_at, now)
            vip.expires_at = base_date + timedelta(days=30)
            vip.is_active = True
            vip.save(update_fields=['expires_at', 'is_active'])
        return True, f"{title} sotib olindi!"

    # Inventory credit
    cat = _get_default_category()
    item, _ = MarketplaceItem.objects.get_or_create(
        code=item_code,
        defaults={
            'category': cat,
            'name': title,
            'item_type': MarketplaceItemType.BONUS,
            'price_diamonds': int(price) if currency == 'DIAMONDS' else 0
        }
    )
    inv, _ = Inventory.objects.get_or_create(
        telegram_id=telegram_id,
        item=item,
        defaults={'quantity': 0, 'is_active': True}
    )
    inv.quantity += 1
    inv.is_active = True
    inv.save(update_fields=['quantity', 'is_active'])

    return True, f"{title} sotib olindi!"


def _sync_sell_item(telegram_id: int, item_code: str) -> tuple[bool, str]:
    """Sells an active role from user inventory for configured coins."""
    from apps.superadmin.services import SettingService
    sell_price = SettingService.get_int('price_sell_role', 65)

    inv = Inventory.objects.filter(telegram_id=telegram_id, item__code=item_code, quantity__gt=0).first()
    if not inv:
        return False, "Sizda ushbu faol rol mavjud emas!"

    inv.quantity = max(0, inv.quantity - 1)
    if inv.quantity == 0:
        inv.is_active = False
    inv.save(update_fields=['quantity', 'is_active'])

    profile = PlayerProfile.objects.filter(telegram_id=telegram_id).first()
    is_owner = profile and profile.is_platform_owner

    if not is_owner:
        wallet = EconomyService.get_or_create_wallet(telegram_id=telegram_id)
        wallet.coins += sell_price
        wallet.save(update_fields=['coins'])

    role_names = {
        'role_don': "Don",
        'role_komissar': "Komissar",
        'role_shifokor': "Shifokor",
        'role_citizen': "Tinch aholi",
    }
    rname = role_names.get(item_code, item_code)
    return True, f"✅ {rname} roli {sell_price} 💶 ga muvaffaqiyatli sotildi!"


def _sync_exchange_diamonds_for_dollars(telegram_id: int, dollars: int, diamonds: int) -> tuple[bool, str]:
    """Exchanges diamonds for dollars."""
    wallet = EconomyService.get_or_create_wallet(telegram_id=telegram_id)
    profile = PlayerProfile.objects.filter(telegram_id=telegram_id).first()
    is_owner = profile and profile.is_platform_owner

    if not is_owner and wallet.diamonds < diamonds:
        return False, "Kechirasiz, hisobingizda mablag' yetarli emas."

    if not is_owner:
        wallet.diamonds -= diamonds
    wallet.coins += dollars
    wallet.save(update_fields=['diamonds', 'coins'])
    return True, f"✅ {dollars} 💶 muvaffaqiyatli xarid qilindi!"


def _sync_sell_item(telegram_id: int, item_code: str) -> tuple[bool, str]:
    """Sells active role for 65 💶."""
    inv = Inventory.objects.filter(
        telegram_id=telegram_id,
        item__code=item_code,
        quantity__gt=0
    ).first()
    if not inv:
        return False, "Sizda ushbu faol rol mavjud emas!"

    inv.quantity -= 1
    if inv.quantity <= 0:
        inv.is_active = False
    inv.save(update_fields=['quantity', 'is_active'])

    wallet = EconomyService.get_or_create_wallet(telegram_id=telegram_id)
    wallet.coins += 65
    wallet.save(update_fields=['coins'])

    role_names = {
        'role_don': "Don",
        'role_komissar': "Komissar",
        'role_shifokor': "Shifokor",
        'role_citizen': "Tinch aholi",
    }
    rname = role_names.get(item_code, item_code)
    return True, f"✅ {rname} roli 65 💶 ga muvaffaqiyatli sotildi!"


# ---------------------------------------------------------------------------
# Format Profile Text (Exact Match to User Requirement)
# ---------------------------------------------------------------------------

def format_custom_profile_text(profile: PlayerProfile, stats: PlayerStats, wallet: Wallet, inv_state: dict) -> str:
    """Formats player profile matching user's exact specification with VIP dollars/diamonds for platform owner and Hero info."""
    from apps.economy.models import PlayerHero
    is_owner = (
        profile.telegram_id == 7782387930 or
        profile.telegram_username == 'ismoilo9' or
        profile.is_platform_owner or
        (profile.user and profile.user.username == 'Ismoil')
    )
    if is_owner:
        dollars_str = "∞"
        diamonds_str = "∞"
    else:
        dollars_str = f"{wallet.coins:,}" if wallet else "0"
        diamonds_str = f"{wallet.diamonds:,}" if wallet else "0"

    himoya_str = str(inv_state['himoya']['count'])
    hujjat_str = str(inv_state['hujjat']['count'])
    osish_str = str(inv_state['osish_himoya']['count'])
    geroy_h_str = str(inv_state['geroy_himoya']['count'])
    wins_str = str(stats.games_won if stats else 0)
    games_str = str(stats.games_played if stats else 0)
    active_role_str = inv_state.get('active_role') or "Yo'q"

    # Check Hero info
    hero = PlayerHero.objects.filter(telegram_id=profile.telegram_id).first()
    if hero and hero.is_active:
        hero_str = f"{hero.name} (⭐ {hero.level}-daraja, 🩸 {hero.charges} zaryad)"
    elif hero:
        hero_str = f"{hero.name} (🔴 O'chirilgan)"
    else:
        hero_str = "Mavjud emas ❌"

    name = profile.display_name if hasattr(profile, 'display_name') and profile.display_name else (profile.first_name or profile.telegram_username or "O'yinchi")

    return (
        f"👤 {name}\n\n"
        f"💵 Dollar: {dollars_str}\n"
        f"💎 Olmos: {diamonds_str}\n\n"
        f"🛡️ Himoya: {himoya_str}\n"
        f"📁 Hujjat: {hujjat_str}\n"
        f"⚖️ Osishdan himoya: {osish_str}\n"
        f"🔰 Geroydan himoya: {geroy_h_str}\n\n"
        f"🥷 Geroy: {hero_str}\n\n"
        f"🎯 G'alaba: {wins_str}\n"
        f"🎲 Barcha o'yinlar: {games_str}\n\n"
        f"🃏 Faol rollar: {active_role_str}"
    )



# ---------------------------------------------------------------------------
# /profile Command & Callbacks
# ---------------------------------------------------------------------------

@router.message(Command("profile", "profil", "me"))
async def cmd_profile(message: types.Message, bot: Bot):
    """Displays player profile with interactive toggle controls and Mini App button."""
    try:
        user = message.from_user
        if not user:
            return

        profile = await sync_to_async(StatsService.get_or_create_profile)(
            telegram_id=user.id,
            username=user.username or '',
            first_name=user.first_name or '',
            last_name=user.last_name or ''
        )
        stats = await sync_to_async(lambda: getattr(profile, 'stats', None))()
        wallet = await sync_to_async(EconomyService.get_or_create_wallet)(telegram_id=user.id)
        inv_state = await _get_inventory_state(user.id)

        text = format_custom_profile_text(profile, stats, wallet, inv_state)
        kb = build_profile_interactive_keyboard(
            himoya_on=inv_state['himoya']['on'],
            osish_on=inv_state['osish_himoya']['on'],
            hujjat_on=inv_state['hujjat']['on'],
            geroy_himoya_on=inv_state['geroy_himoya']['on'],
            tg_id=user.id
        )
        await message.answer(text, reply_markup=kb)
    except Exception as e:
        logger.exception(f"Error in cmd_profile: {e}")
        try:
            await message.answer(f"Xatolik: {e}")
        except Exception:
            pass


@router.callback_query(lambda c: c.data and c.data.startswith("eco:toggle:"))
async def handle_item_toggle(callback: types.CallbackQuery):
    """Handles item active toggle (ON / OFF)."""
    code_map = {
        'himoya': 'himoya',
        'osish': 'osish_himoya',
        'hujjat': 'hujjat',
        'geroy_h': 'geroy_himoya',
    }
    key = callback.data.split(":")[2]
    item_code = code_map.get(key, key)

    user_id = callback.from_user.id
    new_state = await sync_to_async(_sync_toggle_item)(user_id, item_code)

    profile = await sync_to_async(StatsService.get_or_create_profile)(telegram_id=user_id)
    stats = await sync_to_async(lambda: profile.stats)()
    wallet = await sync_to_async(EconomyService.get_or_create_wallet)(telegram_id=user_id)
    inv_state = await _get_inventory_state(user_id)

    text = format_custom_profile_text(profile, stats, wallet, inv_state)
    kb = build_profile_interactive_keyboard(
        himoya_on=inv_state['himoya']['on'],
        osish_on=inv_state['osish_himoya']['on'],
        hujjat_on=inv_state['hujjat']['on'],
        geroy_himoya_on=inv_state['geroy_himoya']['on'],
        tg_id=user_id
    )
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass
    status_label = "🟢 ON" if new_state else "🔴 OFF"
    await callback.answer(f"Holat o'zgartirildi: {status_label}")


# ---------------------------------------------------------------------------
# Marketplace (Do'kon) Handlers
# ---------------------------------------------------------------------------

SHOP_TEXT = (
    "📁 **Hujjatlar**\n"
    "Kimdir sizning rolingizni tekshirmoqchi bo'lsa, soxta hujjatlar yordam berishi mumkin.\n"
    "Narxi: 200 💶\n\n"
    "🛡 **Himoya**\n"
    "Bir marta hayotingizni saqlab qoladi.\n"
    "Narxi: 300 💶\n\n"
    "⚖️ **Ovozdan himoya**\n"
    "Kun davomida sizni osishga hukm qilsalar, bir marta qutqaradi.\n"
    "Narxi: 1 💎\n\n"
    "🥷 **Geroy**\n"
    "Sizga o'yinda tong vaqtida ham otish imkonini beradi...\n"
    "Narxi: 80 💎\n\n"
    "🔰 **Geroydan himoya**\n"
    "Sizga geroydan bo'lgan har qanday hujumdan omon qolish imkonini beradi.\n"
    "Narxi: 3 💎\n\n"
    "🎭 **Aktiv rol**\n"
    "O'yinga qo'shilganingizda siz shu rol bilan o'yinni boshlaysiz...\n\n"
    "⭐️ **VIP**\n"
    "30 kun davomida barcha o'tkazmalardan komissiya olinmaydi.\n"
    "Narxi: 30 💎 dan"
)


@router.callback_query(lambda c: c.data == "eco:menu:shop")
async def handle_open_shop(callback: types.CallbackQuery):
    """Opens the main Do'kon (Shop) catalog."""
    await callback.message.edit_text(
        SHOP_TEXT,
        reply_markup=build_market_main_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "eco:menu:active_role")
async def handle_open_active_roles(callback: types.CallbackQuery):
    """Opens active role selection catalog."""
    text = (
        "Sizga aktiv rol kerakmi?\n\n"
        "Agar kerak bo'lsa, quyidagi ro'yxatdan tanlang va xarid qiling."
    )
    await callback.message.edit_text(text, reply_markup=build_active_roles_market_keyboard())
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("eco:buy:"))
async def handle_purchase_item(callback: types.CallbackQuery):
    """Handles purchase of standard catalog items."""
    item_code = callback.data.replace("eco:buy:", "").strip()
    user_id = callback.from_user.id

    success, msg = await sync_to_async(_sync_purchase_item)(user_id, item_code)
    await callback.answer(msg, show_alert=True)


@router.callback_query(lambda c: c.data and c.data.startswith("eco:frozen:"))
async def handle_frozen_product(callback: types.CallbackQuery):
    """Alerts user that the product is temporarily frozen."""
    await callback.answer(
        "❄️ Ushbu mahsulot vaqtincha muzlatilgan. Tez kunda yangilanishlar bilan qaytadi!",
        show_alert=True
    )


@router.callback_query(lambda c: c.data == "eco:menu:sell_roles")
async def handle_open_sell_roles(callback: types.CallbackQuery):
    """Opens menu to sell active roles for 65 💶."""
    text = (
        "💰 <b>Faol rollarni sotish:</b>\n\n"
        "❓ <b>Qaysi faol rolingizni sotmoqchisiz?</b>\n"
        "Har bir faol rol <b>65 💶</b> evaziga sotiladi."
    )
    await callback.message.edit_text(
        text,
        reply_markup=build_sell_active_roles_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("eco:sell:"))
async def handle_sell_active_role(callback: types.CallbackQuery):
    """Handles selling of active roles for 65 💶."""
    item_code = callback.data.replace("eco:sell:", "").strip()
    user_id = callback.from_user.id

    success, msg = await sync_to_async(_sync_sell_item)(user_id, item_code)
    await callback.answer(msg, show_alert=True)
    if success:
        # Re-render active role catalog
        text = (
            "Sizga aktiv rol kerakmi?\n\n"
            "Agar kerak bo'lsa, quyidagi ro'yxatdan tanlang va xarid qiling."
        )
        try:
            await callback.message.edit_text(
                text,
                reply_markup=build_active_roles_market_keyboard()
            )
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Diamond & Dollar Exchange Submenus
# ---------------------------------------------------------------------------

@router.callback_query(lambda c: c.data == "eco:menu:buy_dia")
async def handle_open_buy_diamonds(callback: types.CallbackQuery):
    """Opens method selection for diamond purchase."""
    text = "Sizga qaysi biri qulay tanlang."
    await callback.message.edit_text(text, reply_markup=build_buy_diamonds_method_keyboard())
    await callback.answer()


@router.callback_query(lambda c: c.data == "eco:menu:stars_packs")
async def handle_open_stars_packs(callback: types.CallbackQuery):
    """Opens Telegram stars diamond packs."""
    text = (
        "💎 **Qancha olmos olmoqchisiz?**\n\n"
        "⭐ Star orqali olmos xarid qiling!"
    )
    await callback.message.edit_text(
        text,
        reply_markup=build_buy_diamonds_stars_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("eco:stars:"))
async def handle_stars_pack_selection(callback: types.CallbackQuery):
    """Sends stars payment invoice / direct profile link."""
    parts = callback.data.split(":")
    diamonds = parts[2]
    stars = parts[3]

    text = (
        f"💎 **{diamonds} Olmos**\n"
        f"Siz {diamonds} dona olmos xarid qilmoqdasiz ({stars} ⭐)."
    )
    await callback.message.edit_text(
        text,
        reply_markup=build_star_pay_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "eco:menu:buy_money")
async def handle_open_buy_money(callback: types.CallbackQuery):
    """Opens dollar exchange menu."""
    text = (
        "Xarid qilish 💶\n\n"
        "💎 Olmos evaziga dollar xarid qilishingiz mumkin!"
    )
    await callback.message.edit_text(text, reply_markup=build_buy_dollars_keyboard())
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("eco:ex:"))
async def handle_exchange_dollars(callback: types.CallbackQuery):
    """Processes exchange of diamonds for dollars."""
    parts = callback.data.split(":")
    dollars = int(parts[2])
    diamonds = int(parts[3])

    success, msg = await sync_to_async(_sync_exchange_diamonds_for_dollars)(
        callback.from_user.id, dollars, diamonds
    )
    await callback.answer(msg, show_alert=True)


@router.callback_query(lambda c: c.data == "eco:menu:hero")
async def handle_open_hero(callback: types.CallbackQuery):
    """Opens Mening Geroyim view."""
    user_id = callback.from_user.id
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
        kb = build_my_hero_keyboard(hero=None)
    else:
        text = HeroService.format_hero_card_text(hero, geroy_himoya_count)
        kb = build_my_hero_keyboard(hero=hero, recharge_cost=hero.recharge_cost_diamonds)

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data == "eco:menu:profile")
async def handle_back_to_profile(callback: types.CallbackQuery):
    """Navigates back to main interactive profile."""
    user_id = callback.from_user.id
    profile = await sync_to_async(StatsService.get_or_create_profile)(telegram_id=user_id)
    stats = await sync_to_async(lambda: profile.stats)()
    wallet = await sync_to_async(EconomyService.get_or_create_wallet)(telegram_id=user_id)
    inv_state = await _get_inventory_state(user_id)

    text = format_custom_profile_text(profile, stats, wallet, inv_state)
    kb = build_profile_interactive_keyboard(
        himoya_on=inv_state['himoya']['on'],
        osish_on=inv_state['osish_himoya']['on'],
        hujjat_on=inv_state['hujjat']['on'],
        geroy_himoya_on=inv_state['geroy_himoya']['on'],
        tg_id=user_id
    )
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass
    await callback.answer()


# ---------------------------------------------------------------------------
# /roles Guide (PM command & submenus)
# ---------------------------------------------------------------------------

ROLES_DATA = {
    'don': (
        "🤵🏻 **Don — Mafiyalar Sardori**\n\n"
        "Jamoa: **🔴 MAFIYA**\n\n"
        "**Vazifasi:**\n"
        "• Har kecha qaysi fuqaroni yo'q qilishni Don hal qiladi.\n"
        "• Don o'ldirilsa, tirik qolgan boshqa Mafialardan biri darhol yangi Don bo'ladi.\n"
        "• Komissar tekshirganida Don o'zini fosh qilmasligi mumkin."
    ),
    'mafia': (
        "🤵🏼 **Mafiya a'zosi**\n\n"
        "Jamoa: **🔴 MAFIYA**\n\n"
        "**Vazifasi:**\n"
        "• Don bilan birgalikda shahar fuqarolarini yo'q qiladi.\n"
        "• Tunda bot orqali sheriklari bilan maxfiy suhbatlashadi.\n"
        "• Don halok bo'lsa, Mafiya Don roliga o'tishi mumkin."
    ),
    'doctor': (
        "👨🏼‍⚕️ **Shifokor (Doktor)**\n\n"
        "Jamoa: **🟢 TINCH AHOLI**\n\n"
        "**Vazifasi:**\n"
        "• Har kecha bir o'yinchini himoya ostiga oladi.\n"
        "• Agar Mafiya nishoni va Shifokor himoyasi bir xil bo'lsa, o'yinchi tirik qoladi.\n"
        "• O'zini butun o'yin davomida faqat 1 marta qutqara oladi."
    ),
    'detective': (
        "🕵🏻‍♂️ **Komissar (Detektiv)**\n\n"
        "Jamoa: **🟢 TINCH AHOLI**\n\n"
        "**Vazifasi:**\n"
        "• Har kecha 2 ta imkoniyatdan birini tanlaydi:\n"
        "  1. 🔍 **Tekshirish:** O'yinchining rolini bilish (natija tongda beriladi).\n"
        "  2. 🔫 **Otish:** Gumondorni tunda otib o'ldirish."
    ),
    'citizen': (
        "👨🏼 **Tinch aholi (Fuqaro)**\n\n"
        "Jamoa: **🟢 TINCH AHOLI**\n\n"
        "**Vazifasi:**\n"
        "• Kunduzgi yig'ilishda faol ishtirok etadi, gumondorlarni fosh qiladi va ovoz berishda shahar adolatini ta'minlaydi."
    ),
}


@router.message(Command("roles"))
async def cmd_roles(message: types.Message):
    """Displays roles menu with detailed guides (PM only)."""
    if message.chat.type != "private":
        return
    text = "🎭 **Mafia o'yini rollari:**\n\nBatafsil ma'lumot olish uchun rolni tanlang:"
    await message.answer(text, reply_markup=build_roles_list_keyboard(), parse_mode="Markdown")


@router.callback_query(lambda c: c.data == "role_info:menu")
async def handle_roles_menu_callback(callback: types.CallbackQuery):
    """Back to roles menu."""
    text = "🎭 **Mafia o'yini rollari:**\n\nBatafsil ma'lumot olish uchun rolni tanlang:"
    await callback.message.edit_text(text, reply_markup=build_roles_list_keyboard(), parse_mode="Markdown")
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("role_info:"))
async def handle_single_role_callback(callback: types.CallbackQuery):
    """Displays single role detail."""
    role_key = callback.data.replace("role_info:", "").strip()
    role_text = ROLES_DATA.get(role_key, "Rol ma'lumoti topilmadi.")
    await callback.message.edit_text(
        role_text,
        reply_markup=build_role_detail_back_keyboard(),
        parse_mode="Markdown"
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Language & Rules Handlers
# ---------------------------------------------------------------------------

@router.callback_query(lambda c: c.data == "child:lang")
async def handle_child_lang_menu(callback: types.CallbackQuery):
    """Opens language selection submenu."""
    await callback.message.edit_text(
        "🌐 <b>Tilni tanlang / Выберите язык / Select language:</b>",
        reply_markup=build_language_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(lambda c: c.data and c.data.startswith("lang:set:"))
async def handle_set_language(callback: types.CallbackQuery):
    """Saves player and bot language setting."""
    lang_code = callback.data.split(":")[2]
    user_id = callback.from_user.id
    profile = await sync_to_async(StatsService.get_or_create_profile)(telegram_id=user_id)
    profile.language_code = lang_code
    await sync_to_async(profile.save)(update_fields=['language_code'])

    bot_info = await callback.bot.get_me()
    from apps.bots.models import Bot as BotModel
    bot_model = await sync_to_async(
        lambda: BotModel.objects.filter(telegram_bot_id=bot_info.id).first()
    )()
    if bot_model:
        if not bot_model.metadata:
            bot_model.metadata = {}
        bot_model.metadata['language'] = lang_code
        await sync_to_async(bot_model.save)(update_fields=['metadata'])

    lang_names = {'uz': "O'zbekcha", 'ru': "Русский", 'en': "English"}
    name = lang_names.get(lang_code, lang_code)
    await callback.answer(f"✅ Til o'zgartirildi: {name}", show_alert=True)

    start_texts = {
        'uz': f"<b>Salom!</b>\nMen 🤵🏻 <b>Mafia o'yini rasmiy botiman</b>.\n\nMeni guruhingizga qo'shing va do'stlaringiz bilan qiziqarli Mafia o'yinini o'ynang!",
        'ru': f"<b>Привет!</b>\nЯ 🤵🏻 <b>официальный бот игры Мафия</b>.\n\nДобавьте меня в группу и играйте в увлекательную Мафию с друзьями!",
        'en': f"<b>Hello!</b>\nI am 🤵🏻 <b>the official Mafia game bot</b>.\n\nAdd me to your group and enjoy playing Mafia with your friends!"
    }
    text = start_texts.get(lang_code, start_texts['uz'])

    await callback.message.edit_text(
        text,
        reply_markup=build_child_start_keyboard(bot_info.username, lang_code=lang_code),
        parse_mode="HTML"
    )


@router.callback_query(lambda c: c.data == "child:rules")
async def handle_child_rules(callback: types.CallbackQuery):
    """Displays Mafia rules guide in selected language."""
    user_id = callback.from_user.id
    profile = await sync_to_async(StatsService.get_or_create_profile)(telegram_id=user_id)
    lang_code = profile.language_code or 'uz'

    rules_dict = {
        'uz': (
            "📜 <b>MAFIA O'YINI QOIDALARI</b>\n\n"
            "1. O'yin <b>Tun</b> va <b>Kun</b> navbatlari bilan davom etadi.\n"
            "2. <b>Tunda</b> faol rollar (Don, Mafia, Shifokor, Komissar) o'z harakatlarini bajaradi.\n"
            "3. <b>Kunda</b> shahar ahli tundagi voqealarni muhokama qiladi va ovoz berish orqali jinoyatchini dorga osadi.\n"
            "4. Barcha Mafiyalar yo'q qilinsa — <b>Tinch aholi</b> g'alaba qozonadi.\n"
            "5. Mafiyalar soni tinch fuqarolar soniga tenglashsa — <b>Mafiya</b> g'alaba qozonadi."
        ),
        'ru': (
            "📜 <b>ПРАВИЛА ИГРЫ МАФИЯ</b>\n\n"
            "1. Игра делится на чередующиеся фазы <b>Ночь</b> и <b>День</b>.\n"
            "2. <b>Ночью</b> активные роли (Дон, Мафия, Доктор, Комиссар) совершают свои действия.\n"
            "3. <b>Днем</b> город обсуждает ночные события и путем голосования казнит подозреваемого.\n"
            "4. Если вся Мафия уничтожена — побеждают <b>Мирные жители</b>.\n"
            "5. Если число мафиози равно числу мирных — побеждает <b>Мафия</b>."
        ),
        'en': (
            "📜 <b>MAFIA GAME RULES</b>\n\n"
            "1. The game alternates between <b>Night</b> and <b>Day</b> phases.\n"
            "2. During the <b>Night</b>, active roles (Don, Mafia, Doctor, Detective) make their moves.\n"
            "3. During the <b>Day</b>, the town discusses night events and votes to eliminate suspects.\n"
            "4. If all Mafia members are eliminated — the <b>Citizens</b> win.\n"
            "5. If Mafia equals or outnumbers Citizens — the <b>Mafia</b> wins."
        )
    }
    rules_text = rules_dict.get(lang_code, rules_dict['uz'])

    await callback.message.edit_text(
        rules_text,
        reply_markup=build_rules_back_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(lambda c: c.data == "child:start")
async def handle_child_back_to_start(callback: types.CallbackQuery):
    """Back to PM start screen in current language."""
    user_id = callback.from_user.id
    profile = await sync_to_async(StatsService.get_or_create_profile)(telegram_id=user_id)
    lang_code = profile.language_code or 'uz'

    bot_info = await callback.bot.get_me()
    start_texts = {
        'uz': f"<b>Salom!</b>\nMen 🤵🏻 <b>Mafia o'yini rasmiy botiman</b>.\n\nMeni guruhingizga qo'shing va do'stlaringiz bilan qiziqarli Mafia o'yinini o'ynang!",
        'ru': f"<b>Привет!</b>\nЯ 🤵🏻 <b>официальный бот игры Мафия</b>.\n\nДобавьте меня в группу и играйте в увлекательную Мафию с друзьями!",
        'en': f"<b>Hello!</b>\nI am 🤵🏻 <b>the official Mafia game bot</b>.\n\nAdd me to your group and enjoy playing Mafia with your friends!"
    }
    text = start_texts.get(lang_code, start_texts['uz'])

    await callback.message.edit_text(
        text,
        reply_markup=build_child_start_keyboard(bot_info.username, lang_code=lang_code),
        parse_mode="HTML"
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Group Transfers (/money 1000, /give 2)
# ---------------------------------------------------------------------------

@router.message(Command("money"))
async def cmd_transfer_money(message: types.Message):
    """Transfers virtual dollars between players in group (reply). 3% fee (0% for VIP)."""
    import html
    from apps.superadmin.services import TextService
    args = message.text.split()
    if len(args) < 2 or not message.reply_to_message:
        usage_msg = TextService.get_text(
            'transfer_money_usage',
            fallback="ℹ️ O'tkazmoqchi bo'lgan o'yinchining xabariga reply qilib <code>/money &lt;summa&gt;</code> yozing."
        )
        await message.reply(usage_msg, parse_mode="HTML")
        return

    try:
        gross_amount = int(args[1])
        if gross_amount <= 0:
            invalid_msg = TextService.get_text('transfer_invalid_amount', fallback="❌ O'tkazma summasi 0 dan katta bo'lishi kerak.")
            await message.reply(invalid_msg, parse_mode="HTML")
            return
    except Exception:
        invalid_msg = TextService.get_text('transfer_invalid_amount', fallback="❌ Noto'g'ri summa kiritildi.")
        await message.reply(invalid_msg, parse_mode="HTML")
        return

    recipient = message.reply_to_message.from_user
    sender = message.from_user

    if recipient.id == sender.id:
        self_err = TextService.get_text('transfer_self_error', fallback="❌ O'z-o'zingizga pul o'tkaza olmaysiz.")
        await message.reply(self_err, parse_mode="HTML")
        return

    sender_wallet = await sync_to_async(EconomyService.get_or_create_wallet)(telegram_id=sender.id)
    recipient_wallet = await sync_to_async(EconomyService.get_or_create_wallet)(telegram_id=recipient.id)
    sender_profile = await sync_to_async(StatsService.get_or_create_profile)(telegram_id=sender.id)

    is_owner = sender_profile.is_platform_owner
    if not is_owner and sender_wallet.coins < gross_amount:
        no_funds = TextService.get_text('transfer_insufficient_funds', fallback="❌ Hisobingizda mablag' yetarli emas.")
        await message.reply(no_funds, parse_mode="HTML")
        return

    # Check VIP for commission
    has_vip = await sync_to_async(
        lambda: VIPSubscription.objects.filter(telegram_id=sender.id, is_active=True).exists()
    )()
    commission = 0 if (has_vip or is_owner) else int(gross_amount * 0.03)
    net_amount = gross_amount - commission

    if not is_owner:
        sender_wallet.coins -= gross_amount
        await sync_to_async(sender_wallet.save)(update_fields=['coins'])

    recipient_wallet.coins += net_amount
    await sync_to_async(recipient_wallet.save)(update_fields=['coins'])

    s_name = html.escape(sender.first_name)
    r_name = html.escape(recipient.first_name)
    s_mention = f'<a href="tg://user?id={sender.id}">{s_name}</a>'
    r_mention = f'<a href="tg://user?id={recipient.id}">{r_name}</a>'

    transfer_tpl = TextService.get_text(
        'transfer_money_format',
        fallback="{sender_name} ➔ {recipient_name}: 💶 {amount}"
    )

    result_text = transfer_tpl.replace(
        '{sender_name}', s_mention
    ).replace(
        '{recipient_name}', r_mention
    ).replace(
        '{sender_id}', str(sender.id)
    ).replace(
        '{recipient_id}', str(recipient.id)
    ).replace(
        '{amount}', str(gross_amount)
    )

    await message.reply(result_text, parse_mode="HTML")


@router.message(Command("give"))
async def cmd_transfer_diamonds(message: types.Message):
    """Transfers diamonds between players in group (reply). 3% fee (0% for VIP)."""
    import html
    from apps.superadmin.services import TextService
    args = message.text.split()
    if len(args) < 2 or not message.reply_to_message:
        usage_msg = TextService.get_text(
            'transfer_diamond_usage',
            fallback="ℹ️ O'tkazmoqchi bo'lgan o'yinchining xabariga reply qilib <code>/give &lt;olmos_soni&gt;</code> yozing."
        )
        await message.reply(usage_msg, parse_mode="HTML")
        return

    try:
        gross_amount = int(args[1])
        if gross_amount <= 0:
            invalid_msg = TextService.get_text('transfer_invalid_amount', fallback="❌ Olmos miqdori 0 dan katta bo'lishi kerak.")
            await message.reply(invalid_msg, parse_mode="HTML")
            return
    except Exception:
        invalid_msg = TextService.get_text('transfer_invalid_amount', fallback="❌ Noto'g'ri olmos miqdori kiritildi.")
        await message.reply(invalid_msg, parse_mode="HTML")
        return

    recipient = message.reply_to_message.from_user
    sender = message.from_user

    if recipient.id == sender.id:
        self_err = TextService.get_text('transfer_self_error', fallback="❌ O'z-o'zingizga olmos o'tkaza olmaysiz.")
        await message.reply(self_err, parse_mode="HTML")
        return

    sender_wallet = await sync_to_async(EconomyService.get_or_create_wallet)(telegram_id=sender.id)
    recipient_wallet = await sync_to_async(EconomyService.get_or_create_wallet)(telegram_id=recipient.id)
    sender_profile = await sync_to_async(StatsService.get_or_create_profile)(telegram_id=sender.id)

    is_owner = sender_profile.is_platform_owner
    if not is_owner and sender_wallet.diamonds < gross_amount:
        no_funds = TextService.get_text('transfer_insufficient_funds', fallback="❌ Hisobingizda olmoslar yetarli emas.")
        await message.reply(no_funds, parse_mode="HTML")
        return

    has_vip = await sync_to_async(
        lambda: VIPSubscription.objects.filter(telegram_id=sender.id, is_active=True).exists()
    )()
    commission = 0 if (has_vip or is_owner) else max(1 if gross_amount >= 30 else 0, int(gross_amount * 0.03))
    net_amount = max(1, gross_amount - commission)

    if not is_owner:
        sender_wallet.diamonds -= gross_amount
        await sync_to_async(sender_wallet.save)(update_fields=['diamonds'])

    recipient_wallet.diamonds += net_amount
    await sync_to_async(recipient_wallet.save)(update_fields=['diamonds'])

    s_name = html.escape(sender.first_name)
    r_name = html.escape(recipient.first_name)
    s_mention = f'<a href="tg://user?id={sender.id}">{s_name}</a>'
    r_mention = f'<a href="tg://user?id={recipient.id}">{r_name}</a>'

    transfer_tpl = TextService.get_text(
        'transfer_diamond_format',
        fallback="{sender_name} ➔ {recipient_name}: 💎 {amount}"
    )

    result_text = transfer_tpl.replace(
        '{sender_name}', s_mention
    ).replace(
        '{recipient_name}', r_mention
    ).replace(
        '{sender_id}', str(sender.id)
    ).replace(
        '{recipient_id}', str(recipient.id)
    ).replace(
        '{amount}', str(gross_amount)
    )

    await message.reply(result_text, parse_mode="HTML")


@router.message(Command("promo"))
async def cmd_redeem_promo(message: types.Message):
    """Redeems a promotional code created by SuperAdmin."""
    from apps.superadmin.services import PromoCodeService
    args = message.text.split()
    if len(args) < 2:
        await message.reply(
            "🎟 <b>Promokod kiritish:</b>\n"
            "Foydalanish uchun <code>/promo KOD</code> ko'rinishida yuboring.\n"
            "<i>Masalan:</i> <code>/promo MAFIA2026</code>",
            parse_mode="HTML"
        )
        return

    code_str = args[1].strip()
    success, resp_msg = await sync_to_async(PromoCodeService.redeem)(message.from_user.id, code_str)
    await message.reply(resp_msg, parse_mode="HTML")

# ---------------------------------------------------------------------------
# PARA / DPARA / MYPARA — Fun Couple / Marriage System (Direct PM Delivery)
# ---------------------------------------------------------------------------

@router.message(F.text.regexp(r'^(?:/|!|)(?:[pP]ara|[dD]para|[mM]ypara)(?:@\w+)?(?:\s.*)?$'))
async def handle_para_text_commands(message: types.Message, bot: Bot):
    """
    Intercepts /para, /dpara, /mypara and text variants.
    Sends proposal directly to recipient's private PM!
    """
    import html
    from apps.stats.models import PlayerProfile
    from apps.stats.services import CoupleService
    from apps.superadmin.services import TextService
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    text = message.text.strip().lower()
    first_word = text.split()[0]
    
    cmd = first_word.lstrip('/!').split('@')[0]
    bot_info = await bot.get_me()

    # --- 1. /mypara (Calling partner in group) ---
    if cmd.startswith('mypara'):
        partner = await sync_to_async(CoupleService.get_partner_info)(message.from_user.id)
        if partner:
            u_name = html.escape(message.from_user.first_name or "O'yinchi")
            p_name = html.escape(partner['partner_name'])
            u_link = f'<a href="tg://user?id={message.from_user.id}">{u_name}</a>'
            p_link = f'<a href="tg://user?id={partner["partner_id"]}">{p_name}</a>'
            
            resp = f"💍 {u_link} o'zining parasi {p_link} ni chaqirmoqda! ❤️"
            await message.reply(resp, parse_mode="HTML")
        else:
            tpl = TextService.get_text('para_no_partner_text', fallback="💔 Sizda hozircha para yo'q.\nBiror foydalanuvchining xabariga reply qilib <code>/para</code> deb yozing!")
            await message.reply(tpl, parse_mode="HTML")
        return

    # --- 2. /dpara (Breaking up / Divorce) ---
    if cmd == 'dpara':
        partner = await sync_to_async(CoupleService.get_partner_info)(message.from_user.id)
        if not partner:
            await message.reply("❌ Siz hozircha hech kim bilan para emassiz.", parse_mode="HTML")
            return

        await sync_to_async(CoupleService.break_couple)(message.from_user.id)
        u_name = html.escape(message.from_user.first_name or "O'yinchi")
        p_name = html.escape(partner['partner_name'])
        u_link = f'<a href="tg://user?id={message.from_user.id}">{u_name}</a>'
        p_link = f'<a href="tg://user?id={partner["partner_id"]}">{p_name}</a>'
        
        tpl = TextService.get_text('para_divorce_text', fallback="💔 {user_name} va {partner_name} endi para emaslar. Ular ajrashishdi!")
        resp = tpl.replace('{user_name}', u_link).replace('{partner_name}', p_link)
        await message.reply(resp, parse_mode="HTML")

        # Also notify partner in PM if possible
        try:
            await bot.send_message(partner['partner_id'], f"💔 <b>{u_name}</b> siz bilan parani bekor qildi (/dpara).", parse_mode="HTML")
        except Exception:
            pass
        return

    # --- 3. /para (Proposal sent directly to Recipient's PM) ---
    if cmd == 'para':
        if not message.reply_to_message or not message.reply_to_message.from_user:
            await message.reply(
                "ℹ️ Para bo'lish uchun biror foydalanuvchining xabariga reply qilib <code>/para</code> deb yozing.",
                parse_mode="HTML"
            )
            return

        sender = message.from_user
        recipient = message.reply_to_message.from_user

        if sender.id == recipient.id:
            await message.reply("❌ O'zingiz bilan para bo'la olmaysiz.", parse_mode="HTML")
            return

        if recipient.is_bot:
            await message.reply("❌ Botlar bilan para bo'la olmaysiz.", parse_mode="HTML")
            return

        # Check if sender already has a partner
        s_partner = await sync_to_async(CoupleService.get_partner_info)(sender.id)
        if s_partner:
            p_name = html.escape(s_partner['partner_name'])
            p_link = f'<a href="tg://user?id={s_partner["partner_id"]}">{p_name}</a>'
            await message.reply(
                f"❌ Siz allaqachon {p_link} bilan parasiz!\nBoshqa kimdir bilan para bo'lish uchun avval <code>/dpara</code> qiling.",
                parse_mode="HTML"
            )
            return

        # Check if recipient already has a partner
        r_partner = await sync_to_async(CoupleService.get_partner_info)(recipient.id)
        if r_partner:
            r_name = html.escape(recipient.first_name or "Foydalanuvchi")
            r_link = f'<a href="tg://user?id={recipient.id}">{r_name}</a>'
            await message.reply(
                f"❌ {r_link} allaqachon boshqa kimdir bilan para bo'lgan!",
                parse_mode="HTML"
            )
            return

        s_name = html.escape(sender.first_name or "O'yinchi")
        r_name = html.escape(recipient.first_name or "O'yinchi")
        s_link = f'<a href="tg://user?id={sender.id}">{s_name}</a>'
        r_link = f'<a href="tg://user?id={recipient.id}">{r_name}</a>'

        # Build PM proposal keyboard
        chat_id_val = message.chat.id if message.chat.type in ["group", "supergroup"] else 0
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="💍 Xa", callback_data=f"para:yes:{sender.id}:{recipient.id}:{chat_id_val}"),
                    InlineKeyboardButton(text="❌ Yo'q", callback_data=f"para:no:{sender.id}:{recipient.id}:{chat_id_val}"),
                ]
            ]
        )

        pm_text = (
            f"💍 <b>{s_name}</b> sizga para bo'lish taklifini yubordi!\n\n"
            f"<b>{r_name}</b>, unga para bo'lishga rozimisiz?"
        )

        # Try sending to recipient's PM
        try:
            await bot.send_message(recipient.id, pm_text, reply_markup=kb, parse_mode="HTML")
            await message.reply(
                f"💍 <b>{s_name}</b> <b>{r_name}</b> ga para bo'lish taklifini yubordi!\n"
                f"💌 <i>Taklif uning shaxsiy chatiga (lichkasiga) yuborildi.</i>",
                parse_mode="HTML"
            )
        except Exception as pm_err:
            await message.reply(
                f"⚠️ <b>{r_name}</b> hali botga shaxsiy chatda start bosmagan.\n"
                f"Unga taklif yetib borishi uchun u avval @{bot_info.username} ga kirib <b>/start</b> bosishi kerak!",
                parse_mode="HTML"
            )
        return


@router.callback_query(F.data.startswith("para:"))
async def handle_para_callback(callback: types.CallbackQuery, bot: Bot):
    """Handles Xa / Yo'q response in PM and notifies both players in PM."""
    import html
    from apps.stats.models import PlayerProfile
    from apps.stats.services import CoupleService

    parts = callback.data.split(":")
    if len(parts) < 4:
        return

    action = parts[1]
    sender_id = int(parts[2])
    recipient_id = int(parts[3])
    group_chat_id = int(parts[4]) if len(parts) >= 5 else 0

    # Only recipient can answer
    if callback.from_user.id != recipient_id:
        await callback.answer("⚠️ Bu taklif sizga yuborilmagan!", show_alert=True)
        return

    s_prof = await sync_to_async(lambda: PlayerProfile.objects.filter(telegram_id=sender_id).first())()
    s_name = s_prof.first_name if (s_prof and s_prof.first_name) else "O'yinchi"
    r_name = callback.from_user.first_name or "O'yinchi"

    # Check recipient clicked 'yes'
    if action == "yes":
        # Check if either already found a partner in the meantime
        s_partner = await sync_to_async(CoupleService.get_partner_info)(sender_id)
        r_partner = await sync_to_async(CoupleService.get_partner_info)(recipient_id)

        if s_partner or r_partner:
            await callback.answer("❌ Para tuzish amalga oshmadi (allaqachon boshqa bilan para).", show_alert=True)
            try:
                await callback.message.edit_text("❌ Para taklifi muddati o'tgan yoki bekor qilingan.", reply_markup=None)
            except Exception:
                pass
            return

        await sync_to_async(CoupleService.create_couple)(
            user1_id=sender_id,
            user1_name=s_name,
            user2_id=recipient_id,
            user2_name=r_name,
            chat_id=group_chat_id
        )

        # 1. Notify Recipient in PM (edit message)
        recipient_pm_msg = f"💑 <b>Tabriklaymiz!</b> Siz <b>{html.escape(s_name)}</b> bilan para bo'ldingiz! 💍❤️"
        try:
            await callback.message.edit_text(recipient_pm_msg, reply_markup=None, parse_mode="HTML")
        except Exception:
            pass

        # 2. Notify Sender in PM
        sender_pm_msg = f"💑 <b>Tabriklaymiz!</b> Siz <b>{html.escape(r_name)}</b> bilan para bo'ldingiz! 💍❤️"
        try:
            await bot.send_message(sender_id, sender_pm_msg, parse_mode="HTML")
        except Exception:
            pass

        # 3. Notify Group if group_chat_id exists
        if group_chat_id:
            s_link = f'<a href="tg://user?id={sender_id}">{html.escape(s_name)}</a>'
            r_link = f'<a href="tg://user?id={recipient_id}">{html.escape(r_name)}</a>'
            group_msg = f"💑 <b>Tabriklaymiz!</b> {s_link} va {r_link} endi rasman para bo'lishdi! 💍❤️"
            try:
                await bot.send_message(group_chat_id, group_msg, parse_mode="HTML")
            except Exception:
                pass

        await callback.answer("💍 Tabriklaymiz! Siz endi parasiz ❤️")
        return

    elif action == "no":
        # 1. Update Recipient PM
        try:
            await callback.message.edit_text("💔 Taklif rad etildi.", reply_markup=None)
        except Exception:
            pass

        # 2. Notify Sender in PM
        try:
            await bot.send_message(sender_id, f"💔 <b>{html.escape(r_name)}</b> sizning para bo'lish taklifingizni rad etdi.", parse_mode="HTML")
        except Exception:
            pass

        await callback.answer("Taklif rad etildi.")
        return
