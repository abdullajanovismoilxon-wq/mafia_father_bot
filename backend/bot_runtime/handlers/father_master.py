"""
MAFIA BOT FATHER — Dedicated Master Father Bot Handlers
This router powers @MafiasFather_bot exclusively:
- Tariff Selection Menu (Standard, Super, Mega Mafia Bot).
- Bot Creation & Token Validation from @BotFather.
- Role Package & Template Selection.
- Entitlement Limit Enforcement (MAX_BOTS per plan).
- Multi-Bot Docker / Worker Pool Spawning.
- Wallet, VIP Plans, and Multilingual Guide.
"""
import re
import html
import secrets
import logging
from decimal import Decimal
from aiogram import Router, types, Bot, F
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.utils.keyboard import InlineKeyboardBuilder
from asgiref.sync import sync_to_async

from django.conf import settings
from apps.users.models import User
from apps.bots.models import Bot as BotModel, BotCredential, BotStatus, RuntimeStatus, BotType
from apps.games.models import GameConfiguration, Role, RoleTeam
from apps.templates.models import GameTemplate
from apps.subscriptions.services import EntitlementService, EntitlementLimitExceededError
from apps.subscriptions.models import FeatureCode
from apps.stats.models import PlayerProfile
from apps.stats.services import StatsService
from apps.economy.models import Wallet, CurrencyType
from apps.economy.services import EconomyService, MarketplaceService
from bot_runtime.keyboards.inline import build_profile_keyboard

logger = logging.getLogger(__name__)
router = Router(name="father_master_router")


def _sync_get_platform_owner_telegram_id() -> int:
    """Returns platform owner Telegram ID dynamically."""
    owner_profile = PlayerProfile.objects.filter(is_platform_owner=True).exclude(telegram_id=999999999).first()
    if owner_profile:
        return owner_profile.telegram_id
    owner_by_uname = PlayerProfile.objects.filter(telegram_username__iexact='ismoilo9').first()
    if owner_by_uname:
        return owner_by_uname.telegram_id
    return 7782387930


def build_master_home_keyboard() -> types.InlineKeyboardMarkup:
    """Builds home navigation keyboard for Master Mafia Father Bot."""
    from apps.superadmin.services import TextService
    b_create = TextService.get_text('btn_father_create_bot', fallback="➕ Mafia Bot Yaratish")
    b_mybots = TextService.get_text('btn_father_my_bots', fallback="🤖 Mening Botlarim")
    b_pay = TextService.get_text('btn_father_pay', fallback="💳 To'lov qilish ↗")
    b_guide = TextService.get_text('btn_father_about', fallback="📖 Bot Yaratish Qo'llanmasi")
    b_lang = TextService.get_text('btn_father_lang', fallback="🌐 Til (O'zbek / Русский / English)")

    builder = InlineKeyboardBuilder()
    builder.button(text=b_create, callback_data="fmaster:create")
    builder.button(text=b_mybots, callback_data="fmaster:mybots")
    builder.button(text=b_pay, url="https://t.me/ismoilo9")
    builder.button(text=b_guide, callback_data="fmaster:guide")
    builder.button(text="📩 Savol va taklif", callback_data="start:feedback")
    builder.button(text=b_lang, callback_data="fmaster:lang")
    builder.adjust(1, 2, 1, 1, 1)
    return builder.as_markup()


@router.message(CommandStart())
async def handle_master_start(message: types.Message, command: CommandObject, bot: Bot):
    """Start command for Master Mafia Father Bot."""
    user = message.from_user
    profile = await sync_to_async(StatsService.get_or_create_profile)(
        telegram_id=user.id,
        username=user.username or '',
        first_name=user.first_name or '',
        last_name=user.last_name or ''
    )

    owner_badge = "👑 PLATFORMA EGASI" if profile.is_platform_owner else "⭐ Foydalanuvchi"

    text = (
        f"👑 <b>MAFIA BOT FATHER — PLATFORMASIGA XUSH KELIBSIZ!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"Assalomu alaykum, <b>{html.escape(user.first_name)}</b>! ({owner_badge})\n\n"
        f"Ushbu bot orqali siz 1 daqiqada oʻzingizning shaxsiy <b>Telegram Mafia oʻyin botingizni</b> yaratishingiz va doʻstlaringiz bilan guruhlarda oʻynashingiz mumkin.\n\n"
        f"🎮 <b>Botingizdagi asosiy rollar:</b>\n"
        f"• 🤵🏻 <b>Don</b> — Mafialar yetakchisi (tunda qotillikni belgilaydi)\n"
        f"• 🤵🏼 <b>Mafia</b> — Don bilan birgalikda shahar fuqarolariga hujum qiladi\n"
        f"• 🕵🏻‍♂️ <b>Komissar</b> — Tunda gumondorlarni tekshirib, mafiyani fosh etadi\n"
        f"• 👨🏼‍⚕️ <b>Doktor</b> — Tunda fuqaroni davolab, oʻlimdan qutqaradi\n"
        f"• 👨🏼 <b>Tinch aholi</b> — Kunduzgi muhokama va ovoz berishda qatnashadi\n\n"
        f"💬 <i>Savol va takliflaringiz bo'lsa @ismoilo9 ga murojaat qiling.</i>\n\n"
        f"👇 <i>Boshlash uchun quyidagi tugmalardan birini tanlang:</i>"
    )
    await message.answer(text, reply_markup=build_master_home_keyboard(), parse_mode="HTML")


@router.message(Command("create_bot", "newbot", "yaratish"))
async def cmd_master_create_guide(message: types.Message):
    """Sends Direct Bot Creation Instructions."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🤖 @BotFather ga o'tish ↗", url="https://t.me/BotFather")
    builder.button(text="⬅️ Bosh Menyu", callback_data="fmaster:home")
    builder.adjust(1)

    text = (
        "🤖 <b>YANGI MAFIA BOT YARATISH:</b>\n"
        "━━━━━━━━━━━━━━━━━━━\n\n"
        "1️⃣ Telegramda @BotFather ga kiring.\n"
        "2️⃣ <code>/newbot</code> buyrugʻini yuboring.\n"
        "3️⃣ Botingiz uchun nom tanlang (Masalan: <i>Bloody Mafia</i>).\n"
        "4️⃣ Botingiz uchun username tanlang (oxiri <code>bot</code> bilan tugashi kerak, masalan: <i>my_mafia_bot</i>).\n"
        "5️⃣ @BotFather sizga bergan <b>HTTP API Tokini</b> nusxalab oling.\n\n"
        "👇 <b>Olingan tokenni to'g'ridan-to'g'ri shu yerga (chatga) yuboring:</b>"
    )
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.message(F.text.regexp(r'\d{8,12}:[A-Za-z0-9_-]{35,}'))
async def handle_master_token_input(message: types.Message, bot: Bot):
    """Validates Telegram token, creates pending child bot, and sends approval request to platform owner."""
    raw_token = message.text.strip()
    match = re.search(r'\d{8,12}:[A-Za-z0-9_-]{35,}', raw_token)
    if match:
        raw_token = match.group(0)

    status_msg = await message.reply("⏳ <b>Token Telegram serverlarida tekshirilmoqda...</b>", parse_mode="HTML")

    # ── Step 1: Validate token via Telegram API ──────────────────────────────
    try:
        temp_bot = Bot(token=raw_token)
        bot_user = await temp_bot.get_me()
        await temp_bot.session.close()
    except Exception as e:
        logger.warning(f"Invalid Telegram token submitted: {e}")
        await status_msg.edit_text(
            "❌ <b>Notoʻgʻri token!</b>\n\n"
            "Telegram ushbu tokenni qabul qilmadi. Iltimos, @BotFather dan toʻgʻri tokenni nusxalab qayta yuboring.",
            parse_mode="HTML"
        )
        return

    # ── Step 2: Get or create Django User record for this Telegram user ──────
    profile = await sync_to_async(StatsService.get_or_create_profile)(
        telegram_id=message.from_user.id,
        username=message.from_user.username or '',
        first_name=message.from_user.first_name or '',
        last_name=message.from_user.last_name or ''
    )
    user = await sync_to_async(
        lambda: User.objects.filter(telegram_id=message.from_user.id).first()
    )()
    if not user:
        random_password = secrets.token_urlsafe(32)
        user = await sync_to_async(User.objects.create_user)(
            username=f"tg_{message.from_user.id}",
            email=f"tg_{message.from_user.id}@mafiabotfather.uz",
            password=random_password,
            telegram_id=message.from_user.id,
            is_platform_owner=profile.is_platform_owner
        )
    
    def _link_profile(u):
        profile.user = u
        profile.save(update_fields=['user'])
    await sync_to_async(_link_profile)(user)

    # ── Step 3: Save/update BotModel with INACTIVE (pending approval) status ──
    existing_bot = await sync_to_async(
        lambda: BotModel.objects.filter(telegram_bot_id=bot_user.id).first()
    )()

    bot_obj = existing_bot
    if not bot_obj:
        bot_obj = await sync_to_async(BotModel.objects.create)(
            owner=user,
            name=bot_user.first_name,
            telegram_username=bot_user.username,
            telegram_bot_id=bot_user.id,
            bot_type=BotType.STANDARD,
            status=BotStatus.PENDING,
            runtime_status=RuntimeStatus.OFFLINE
        )
    else:
        bot_obj.owner = user
        bot_obj.name = bot_user.first_name
        bot_obj.telegram_username = bot_user.username
        bot_obj.telegram_bot_id = bot_user.id
        bot_obj.status = BotStatus.PENDING
        bot_obj.runtime_status = RuntimeStatus.OFFLINE
        await sync_to_async(bot_obj.save)()

    # ── Step 4: Save credentials ──────────────────────────────────────────────
    cred = await sync_to_async(
        lambda: BotCredential.objects.filter(bot=bot_obj).first()
    )()
    if not cred:
        cred = BotCredential(bot=bot_obj)
    cred.set_token(raw_token)
    await sync_to_async(cred.save)()

    # ── Step 5: Create default game configuration ──────────────────────────────
    def _create_config():
        config, _ = GameConfiguration.objects.get_or_create(
            bot=bot_obj,
            defaults={
                'owner': user,
                'name': f"{bot_user.first_name} Mafia Qoidalari",
                'minimum_players': 4,
                'maximum_players': 20,
                'night_duration': 60,
                'discussion_duration': 30,
                'voting_duration': 20,
            }
        )
        return config

    await sync_to_async(_create_config)()

    # ── Step 6: Confirmation to User ──────────────────────────────────────────
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 To'lov qilish (@ismoilo9) ↗", url="https://t.me/ismoilo9")
    builder.button(text="⬅️ Bosh Menyu", callback_data="fmaster:home")
    builder.adjust(1)

    pending_text = (
        f"⏳ <b>Botingiz ma'lumotlari qabul qilindi va ma'muriyatga tasdiqlash uchun yuborildi!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 <b>Bot nomi:</b> {html.escape(bot_user.first_name)}\n"
        f"🆔 <b>Username:</b> @{bot_user.username}\n\n"
        f"💡 Botingizni tezkor tasdiqlash va to'lov qilish uchun @ismoilo9 ga murojaat qiling.\n"
        f"Ma'muriyat tasdiqlashi bilan botingiz avtomatik ishga tushadi va sizga xabar yuboriladi!"
    )
    await status_msg.edit_text(pending_text, reply_markup=builder.as_markup(), parse_mode="HTML")

    # ── Step 7: Send Approval Request to Platform Owner (@ismoilo9) ───────────
    owner_tg_id = await sync_to_async(_sync_get_platform_owner_telegram_id)()
    admin_kb = InlineKeyboardBuilder()
    admin_kb.button(text="✅ Xa (Tasdiqlash)", callback_data=f"fadmin:approve:{bot_obj.id}")
    admin_kb.button(text="❌ Yo'q (Rad etish)", callback_data=f"fadmin:reject:{bot_obj.id}")
    admin_kb.adjust(2)

    user_mention = f'<a href="tg://user?id={message.from_user.id}">{html.escape(message.from_user.full_name)}</a>'
    user_uname = f"(@{message.from_user.username})" if message.from_user.username else ""

    admin_msg = (
        f"🔔 <b>YANGI BOTNI TASDIQLASH SO'ROVI:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Foydalanuvchi:</b> {user_mention} {user_uname} [Chat ID: <code>{message.from_user.id}</code>]\n"
        f"🤖 <b>Bot:</b> @{bot_user.username} ({html.escape(bot_user.first_name)}) [ID: <code>{bot_user.id}</code>]\n\n"
        f"<b>Ushbu botni tasdiqlaysizmi?</b>"
    )

    try:
        await bot.send_message(owner_tg_id, admin_msg, reply_markup=admin_kb.as_markup(), parse_mode="HTML")
        logger.info(f"✅ Sent approval request to owner {owner_tg_id} for bot @{bot_user.username}")
    except Exception as e:
        logger.error(f"❌ Could not send approval request to owner {owner_tg_id}: {e}")


# ─── Admin Approval Callbacks ────────────────────────────────────────────────

@router.callback_query(F.data.startswith("fadmin:approve:"))
async def handle_admin_approve_bot(call: types.CallbackQuery, bot: Bot):
    """Platform owner approves child bot creation."""
    bot_id = call.data.split(":")[2]
    bot_obj = await sync_to_async(
        lambda: BotModel.objects.select_related('owner').filter(id=bot_id).first()
    )()
    if not bot_obj:
        await call.answer("❌ Bot topilmadi.", show_alert=True)
        return

    bot_obj.status = BotStatus.ACTIVE
    bot_obj.runtime_status = RuntimeStatus.RUNNING
    await sync_to_async(bot_obj.save)(update_fields=['status', 'runtime_status'])

    # Start child bot polling
    from bot_runtime.manager import BotRuntimeManager
    await BotRuntimeManager.start_bot_polling(str(bot_obj.id))

    await call.message.edit_text(
        f"✅ <b>Bot @{bot_obj.telegram_username} muvaffaqiyatli tasdiqlandi va ishga tushirildi!</b>",
        parse_mode="HTML"
    )
    await call.answer("✅ Bot tasdiqlandi va ishga tushirildi!")

    # Notify bot owner
    if bot_obj.owner and bot_obj.owner.telegram_id:
        user_builder = InlineKeyboardBuilder()
        user_builder.button(text="➕ Guruhga qo'shish ↗", url=f"https://t.me/{bot_obj.telegram_username}?startgroup=true")
        user_builder.button(text=f"🤖 @{bot_obj.telegram_username} ga o'tish ↗", url=f"https://t.me/{bot_obj.telegram_username}")
        user_builder.adjust(1)
        try:
            await bot.send_message(
                bot_obj.owner.telegram_id,
                f"🎉 <b>TABRIKLAYMIZ! BOTINGIZ TASDIQLANDI!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"🤖 <b>Bot:</b> @{bot_obj.telegram_username}\n"
                f"⚡ <b>Server holati:</b> 🟢 ISHGA TUSHDI (LIVE)\n\n"
                f"Endi botingizni o'yin guruhingizga qo'shib, <code>/game</code> buyrug'i orqali o'yinlarni boshlashingiz mumkin!",
                reply_markup=user_builder.as_markup(),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Could not notify bot owner: {e}")


@router.callback_query(F.data.startswith("fadmin:reject:"))
async def handle_admin_reject_bot(call: types.CallbackQuery, bot: Bot):
    """Platform owner rejects child bot creation."""
    bot_id = call.data.split(":")[2]
    bot_obj = await sync_to_async(
        lambda: BotModel.objects.select_related('owner').filter(id=bot_id).first()
    )()
    if not bot_obj:
        await call.answer("❌ Bot topilmadi.", show_alert=True)
        return

    uname = bot_obj.telegram_username
    owner_tid = bot_obj.owner.telegram_id if bot_obj.owner else None

    # Delete or deactivate bot
    await sync_to_async(lambda: BotModel.objects.filter(id=bot_id).delete())()

    await call.message.edit_text(
        f"❌ <b>Bot @{uname} rad etildi.</b>",
        parse_mode="HTML"
    )
    await call.answer("❌ Bot rad etildi.")

    # Notify user
    if owner_tid:
        user_builder = InlineKeyboardBuilder()
        user_builder.button(text="💳 To'lov qilish (@ismoilo9) ↗", url="https://t.me/ismoilo9")
        user_builder.button(text="➕ Qayta so'rov yuborish", callback_data="fmaster:create")
        user_builder.adjust(1)
        try:
            await bot.send_message(
                owner_tid,
                f"❌ <b>Botingiz (@{uname}) ma'muriyat tomonidan rad etildi.</b>\n\n"
                f"To'lov qilish yoki ma'lumot olish uchun @ismoilo9 ga murojaat qiling.\n"
                f"Qayta so'rov yuborishingiz mumkin.",
                reply_markup=user_builder.as_markup(),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.warning(f"Could not notify user: {e}")


# ─── Navigation Callbacks ────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("fmaster:"))
async def handle_master_callbacks(call: types.CallbackQuery):
    """Processes master bot interactive callbacks."""
    parts = call.data.split(":")
    action = parts[1]

    if action == "home":
        user = call.from_user
        profile = await sync_to_async(StatsService.get_or_create_profile)(
            telegram_id=user.id,
            username=user.username or '',
            first_name=user.first_name or '',
            last_name=user.last_name or ''
        )
        owner_badge = "👑 PLATFORMA EGASI" if profile.is_platform_owner else "⭐ Foydalanuvchi"
        text = (
            f"👑 <b>MAFIA BOT FATHER — PLATFORMASIGA XUSH KELIBSIZ!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"Assalomu alaykum, <b>{html.escape(user.first_name)}</b>! ({owner_badge})\n\n"
            f"Boshqaruv menyusi:"
        )
        await call.message.edit_text(text, reply_markup=build_master_home_keyboard(), parse_mode="HTML")
        await call.answer()

    elif action == "create":
        builder = InlineKeyboardBuilder()
        builder.button(text="🤖 @BotFather ga o'tish ↗", url="https://t.me/BotFather")
        builder.button(text="⬅️ Bosh Menyu", callback_data="fmaster:home")
        builder.adjust(1)

        text = (
            "🤖 <b>YANGI MAFIA BOT YARATISH:</b>\n"
            "━━━━━━━━━━━━━━━━━━━\n\n"
            "1️⃣ Telegramda @BotFather ga kiring.\n"
            "2️⃣ <code>/newbot</code> buyrugʻini yuboring.\n"
            "3️⃣ Botingiz uchun nom tanlang (Masalan: <i>Bloody Mafia</i>).\n"
            "4️⃣ Botingiz uchun username tanlang (oxiri <code>bot</code> bilan tugashi kerak, masalan: <i>my_mafia_bot</i>).\n"
            "5️⃣ @BotFather sizga bergan <b>HTTP API Tokini</b> nusxalab oling.\n\n"
            "👇 <b>Olingan tokenni to'g'ridan-to'g'ri shu yerga (chatga) yuboring:</b>"
        )
        await call.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await call.answer()

    elif action == "mybots":
        user = call.from_user
        profile = await sync_to_async(
            lambda: PlayerProfile.objects.filter(telegram_id=user.id).select_related('user').first()
        )()
        bots = []
        if profile and profile.user:
            bots = await sync_to_async(
                lambda: list(BotModel.objects.filter(owner=profile.user).exclude(status=BotStatus.DELETED))
            )()

        builder = InlineKeyboardBuilder()
        if not bots:
            text = (
                "🤖 <b>Sizda hali yaratilgan Mafia botlari yoʻq.</b>\n\n"
                "Birinchi botingizni yaratish uchun <code>➕ Mafia Bot Yaratish</code> tugmasini bosing!"
            )
            builder.button(text="➕ Mafia Bot Yaratish", callback_data="fmaster:create")
        else:
            lines = ["🤖 <b>SIZNING MAFIA BOTLARINGIZ:</b>\n━━━━━━━━━━━━━━━━━━━"]
            for b in bots:
                status_icon = "🟢 Faol" if b.runtime_status == RuntimeStatus.RUNNING else "🟡 Kutilmoqda / To'xtatilgan"
                lines.append(f"• <b>{html.escape(b.name)}</b> (@{b.telegram_username}) — {status_icon}")
                builder.button(text=f"🤖 @{b.telegram_username} ga o'tish ↗", url=f"https://t.me/{b.telegram_username}")
            builder.button(text="➕ Yangi Bot Qo'shish", callback_data="fmaster:create")
            text = "\n".join(lines)

        builder.button(text="⬅️ Bosh Menyu", callback_data="fmaster:home")
        builder.adjust(1)
        await call.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await call.answer()

    elif action == "guide":
        builder = InlineKeyboardBuilder()
        builder.button(text="➕ Mafia Bot Yaratish", callback_data="fmaster:create")
        builder.button(text="⬅️ Bosh Menyu", callback_data="fmaster:home")
        builder.adjust(1)

        text = (
            "📖 <b>MAFIA BOT FATHER PLATFORMASI QOʻLLANMASI:</b>\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "1. Telegramda @BotFather ga kirib, <code>/newbot</code> orqali yangi bot oching.\n"
            "2. Olingan tokenni ushbu botga yuboring.\n"
            "3. Botingiz ma'muriyat tomonidan tasdiqlanishi bilan darhol ishga tushadi.\n"
            "4. Yangi yaratilgan botingizni guruhingizga qoʻshib, admin huquqini bering.\n"
            "5. Guruhda <code>/game</code> buyrugʻini yozib oʻyinni boshlang!"
        )
        await call.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await call.answer()

    elif action == "lang":
        builder = InlineKeyboardBuilder()
        builder.button(text="🇺🇿 O'zbekcha (Standart)", callback_data="fmaster:setlang:uz")
        builder.button(text="🇷🇺 Русский", callback_data="fmaster:setlang:ru")
        builder.button(text="🇬🇧 English", callback_data="fmaster:setlang:en")
        builder.button(text="⬅️ Bosh Menyu", callback_data="fmaster:home")
        builder.adjust(1)

        text = "🌐 <b>Tilni tanlang / Выберите язык / Select Language:</b>"
        await call.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await call.answer()

    elif action == "setlang":
        lang = call.data.split(":")[2]
        lang_names = {'uz': "O'zbek tili", 'ru': "Русский язык", 'en': "English"}
        await call.answer(f"✅ {lang_names.get(lang, 'Oʻzbek tili')} tanlandi!", show_alert=True)
        # Re-render home with updated language
        user = call.from_user
        profile = await sync_to_async(StatsService.get_or_create_profile)(telegram_id=user.id)
        profile.language_code = lang
        await sync_to_async(profile.save)(update_fields=['language_code'])
        owner_badge = "👑 PLATFORMA EGASI" if profile.is_platform_owner else "⭐ Foydalanuvchi"
        text = (
            f"👑 <b>MAFIA BOT FATHER — PLATFORMASIGA XUSH KELIBSIZ!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"Assalomu alaykum, <b>{html.escape(user.first_name)}</b>! ({owner_badge})\n\n"
            f"Boshqaruv menyusi:"
        )
        await call.message.edit_text(text, reply_markup=build_master_home_keyboard(), parse_mode="HTML")


@router.message(Command("profile", "profil", "me"))
async def cmd_master_profile(message: types.Message, bot: Bot):
    """Handles /profile directly in Master Father Bot."""
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
        from bot_runtime.handlers.economy import _get_inventory_state, format_custom_profile_text, check_channel_membership_and_apply_bonus
        from bot_runtime.keyboards.inline import build_profile_interactive_keyboard
        inv_state = await _get_inventory_state(user.id)
        is_member = await check_channel_membership_and_apply_bonus(bot, profile, wallet)
        text = format_custom_profile_text(profile, stats, wallet, inv_state, is_channel_member=is_member)
        kb = build_profile_interactive_keyboard(
            himoya_on=inv_state['himoya']['on'],
            osish_on=inv_state['osish_himoya']['on'],
            hujjat_on=inv_state['hujjat']['on'],
            geroy_himoya_on=inv_state['geroy_himoya']['on'],
            tg_id=user.id
        )
        await message.answer(text, reply_markup=kb)
    except Exception as e:
        logger.exception(f"Error in master profile: {e}")
        await message.answer(f"Xatolik: {e}")



# Global waiting state for user feedback: {telegram_id: True}
FEEDBACK_WAITING_USERS: dict = {}


@router.callback_query(lambda c: c.data == "start:feedback")
async def handle_feedback_button_click(callback: types.CallbackQuery):
    """Prompts user to type their question or suggestion."""
    user_id = callback.from_user.id
    FEEDBACK_WAITING_USERS[user_id] = True
    await callback.answer()
    await callback.message.answer(
        "✍️ <b>Savol yoki taklifingizni yozib qoldiring:</b>\n\n"
        "Sizning murojaatingiz to'g'ridan-to'g'ri platforma administratoriga (@ismoilo9) yetkaziladi.\n"
        "Iltimos, xabaringizni shu yerga yozib yuboring:",
        parse_mode="HTML"
    )


@router.message(lambda msg: msg.chat.type == "private" and not (msg.text and msg.text.startswith("/")) and msg.from_user and msg.from_user.id in FEEDBACK_WAITING_USERS)
async def handle_user_feedback_message(message: types.Message, bot: Bot):
    """Processes user's feedback text, saves in DB, and notifies admin."""
    user = message.from_user
    FEEDBACK_WAITING_USERS.pop(user.id, None)

    feedback_text = message.text or "[Fayl yoki media yuborildi]"
    user_name = user.full_name or user.first_name
    username = user.username or ''

    # 1. Save in Database (SuperAdmin panel)
    from apps.superadmin.models import FeedbackMessage
    await sync_to_async(FeedbackMessage.objects.create)(
        telegram_id=user.id,
        telegram_username=username,
        user_display_name=user_name,
        message_text=feedback_text
    )

    # 2. Forward / Notify Admin (@ismoilo9)
    admin_id = _sync_get_platform_owner_telegram_id()
    admin_alert = (
        f"📩 <b>Yangi Savol / Taklif Keldi!</b>\n\n"
        f"👤 <b>Yuboruvchi:</b> {html.escape(user_name)} (@{username if username else 'yoʻq'})\n"
        f"🆔 <b>Telegram ID:</b> <code>{user.id}</code>\n\n"
        f"💬 <b>Murojaat matni:</b>\n"
        f"<i>{html.escape(feedback_text)}</i>"
    )

    try:
        await bot.send_message(admin_id, admin_alert, parse_mode="HTML")
    except Exception as e:
        logger.warning(f"Could not forward feedback to admin {admin_id}: {e}")

    # 3. Confirm to User
    await message.answer(
        "✅ <b>Murojaatingiz muvaffaqiyatli qabul qilindi!</b>\n\n"
        "Administrator (@ismoilo9) tez orada ko'rib chiqadi va sizga javob yuboradi.",
        parse_mode="HTML"
    )
