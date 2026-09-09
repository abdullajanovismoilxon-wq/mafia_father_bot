import html
import logging
from aiogram import Router, Bot, F, types
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from asgiref.sync import sync_to_async

from apps.economy.models import CurrencyType
from apps.economy.giveaway_service import GiveawayService

logger = logging.getLogger(__name__)
router = Router(name="giveaway_router")


def build_giveaway_keyboard(drop_id: str, currency: str, remaining: int, total: int) -> InlineKeyboardMarkup:
    """Builds inline keyboard for claiming drop."""
    from apps.superadmin.services import TextService
    builder = InlineKeyboardBuilder()
    curr_icon = "💎" if currency == CurrencyType.DIAMONDS else "💶"
    curr_label = "Olmosni" if currency == CurrencyType.DIAMONDS else "Dollarni"

    if remaining <= 0:
        lbl_finished = TextService.get_text(
            'btn_giveaway_finished',
            fallback="✅ Barchasi olindi! (0/{total})"
        ).replace('{total}', str(total))
        builder.button(
            text=lbl_finished,
            callback_data="gw:empty"
        )
    else:
        lbl_claim = TextService.get_text(
            'btn_giveaway_claim',
            fallback="{curr_icon} {curr_label} olish ({remaining}/{total})"
        ).replace('{curr_icon}', curr_icon).replace('{curr_label}', curr_label).replace('{remaining}', str(remaining)).replace('{total}', str(total))
        builder.button(
            text=lbl_claim,
            callback_data=f"gw:cl:{str(drop_id)}"
        )
    builder.adjust(1)
    return builder.as_markup()


def format_giveaway_message(sender_id: int, sender_name: str, currency: str, total: int, remaining: int) -> str:
    """Formats group announcement for giveaway drop."""
    from apps.superadmin.services import TextService
    curr_icon = "💎" if currency == CurrencyType.DIAMONDS else "💶"
    curr_label = "Olmos" if currency == CurrencyType.DIAMONDS else "Dollar"
    sender_mention = f'<a href="tg://user?id={sender_id}">{html.escape(sender_name)}</a>'

    status_line = (
        f"📊 Qolgan: <b>{remaining}/{total}</b> {curr_icon}"
        if remaining > 0 else
        f"🏁 <b>Barcha {total} ta {curr_label.lower()} to'liq olindi!</b>"
    )

    tpl = TextService.get_text(
        'giveaway_drop_msg',
        fallback="🎁 {sender_mention} guruhga <b>{total} {curr_icon} {curr_label}</b> ulashdi!\n\nℹ️ <i>Har bir o'yinchi 1 donadan olishi mumkin!</i>\n\n{status_line}"
    )

    return tpl.format(
        sender_mention=sender_mention,
        total=total,
        curr_icon=curr_icon,
        curr_label=curr_label,
        status_line=status_line
    )


@router.message(Command("changegive", "change", "olmos_ulash", ignore_case=True))
async def cmd_giveaway_diamonds(message: Message, bot: Bot):
    """Drops diamonds in group: /changegive 100 or /change 100."""
    await _handle_giveaway_create(message, bot, currency=CurrencyType.DIAMONDS)


@router.message(Command("changemoney", "changedollar", "pul_ulash", ignore_case=True))
async def cmd_giveaway_money(message: Message, bot: Bot):
    """Drops money/dollars in group: /changemoney 100."""
    await _handle_giveaway_create(message, bot, currency=CurrencyType.MONEY)


async def _handle_giveaway_create(message: Message, bot: Bot, currency: str):
    if message.chat.type in ["private"]:
        await message.reply("⚠️ Ushbu buyruq faqat guruhlarda ishlaydi!")
        return

    parts = message.text.strip().split()
    if len(parts) < 2:
        curr_name = "olmos" if currency == CurrencyType.DIAMONDS else "dollar"
        cmd_example = "/changegive 100" if currency == CurrencyType.DIAMONDS else "/changemoney 100"
        await message.reply(
            f"⚠️ Miqdorni kiriting!\nMasalan: <code>{cmd_example}</code> ({curr_name} ulashish uchun).",
            parse_mode="HTML"
        )
        return

    try:
        amount = int(parts[1])
        if amount <= 0:
            raise ValueError()
    except Exception:
        await message.reply("❌ Iltimos, musbat butun son kiriting! (Masalan: 100)")
        return

    sender_id = message.from_user.id
    sender_name = message.from_user.full_name or message.from_user.first_name or f"Foydalanuvchi {sender_id}"

    success, msg, drop = await sync_to_async(GiveawayService.create_drop)(
        chat_id=message.chat.id,
        sender_telegram_id=sender_id,
        sender_name=sender_name,
        currency=currency,
        amount=amount
    )

    if not success or not drop:
        await message.reply(msg, parse_mode="HTML")
        return

    kb = build_giveaway_keyboard(str(drop.id), currency, drop.remaining_amount, drop.total_amount)
    drop_text = format_giveaway_message(
        sender_id=sender_id,
        sender_name=sender_name,
        currency=currency,
        total=drop.total_amount,
        remaining=drop.remaining_amount
    )

    sent = await message.answer(drop_text, reply_markup=kb, parse_mode="HTML")
    drop.message_id = sent.message_id
    await sync_to_async(drop.save)(update_fields=['message_id'])


@router.callback_query(lambda c: c.data and c.data.startswith("gw:cl:"))
async def handle_giveaway_claim_callback(callback: CallbackQuery, bot: Bot):
    """Processes user claiming 1 unit from giveaway drop."""
    drop_id = callback.data.replace("gw:cl:", "").strip()
    user_id = callback.from_user.id
    user_name = callback.from_user.full_name or callback.from_user.first_name or f"User {user_id}"

    success, msg, remaining, total = await sync_to_async(GiveawayService.claim_drop)(
        drop_id=drop_id,
        user_telegram_id=user_id,
        user_name=user_name
    )

    await callback.answer(msg, show_alert=True)

    if success or remaining == 0:
        # Update message caption or text
        from apps.economy.models import GiveawayDrop
        drop = await sync_to_async(GiveawayDrop.objects.filter(id=drop_id).first)()
        if drop:
            curr = drop.currency
            new_text = format_giveaway_message(
                sender_id=drop.sender_telegram_id,
                sender_name=drop.sender_name,
                currency=curr,
                total=drop.total_amount,
                remaining=drop.remaining_amount
            )
            new_kb = build_giveaway_keyboard(str(drop.id), curr, drop.remaining_amount, drop.total_amount)
            try:
                await callback.message.edit_text(new_text, reply_markup=new_kb, parse_mode="HTML")
            except Exception:
                pass


@router.callback_query(F.data == "gw:empty")
async def handle_giveaway_empty_callback(callback: CallbackQuery):
    await callback.answer("❌ Bu ulashuvdagi barcha sovg'alar olib bo'lingan!", show_alert=True)
