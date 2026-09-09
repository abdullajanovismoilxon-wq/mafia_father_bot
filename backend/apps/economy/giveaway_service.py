import math
from decimal import Decimal
from typing import Tuple, Optional
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.economy.models import (
    Wallet, CurrencyType, TransactionType,
    GiveawayDrop, GiveawayClaim
)
from apps.economy.services import EconomyService, InsufficientBalanceError


class GiveawayService:
    """Handles creating and claiming giveaway drops in group chats."""

    COMMISSION_PERCENT = 3  # 3% commission

    @classmethod
    def calculate_commission(cls, amount: int, currency: str) -> Decimal:
        """Calculates 3% commission for giveaway drop."""
        if currency == CurrencyType.DIAMONDS:
            # Whole integer diamonds (at least 1 diamond if amount >= 1)
            fee = math.ceil(amount * (cls.COMMISSION_PERCENT / 100.0))
            return Decimal(fee)
        else:
            fee = Decimal(str(amount)) * (Decimal(cls.COMMISSION_PERCENT) / Decimal('100'))
            return fee.quantize(Decimal('0.01'))

    @classmethod
    def create_drop(
        cls,
        chat_id: int,
        sender_telegram_id: int,
        sender_name: str,
        currency: str,
        amount: int
    ) -> Tuple[bool, str, Optional[GiveawayDrop]]:
        """
        Deducts amount + 3% commission from sender's wallet and creates a GiveawayDrop.
        """
        if amount <= 0:
            return False, "❌ Miqdor 0 dan katta bo'lishi kerak!", None

        fee = cls.calculate_commission(amount, currency)
        total_needed = Decimal(str(amount)) + fee

        wallet = EconomyService.get_or_create_wallet(telegram_id=sender_telegram_id)

        curr_icon = "💎" if currency == CurrencyType.DIAMONDS else "💶"
        curr_label = "olmos" if currency == CurrencyType.DIAMONDS else "dollar"

        try:
            with transaction.atomic():
                EconomyService.debit_wallet(
                    wallet=wallet,
                    currency=currency,
                    amount=total_needed,
                    tx_type=TransactionType.GIFT,
                    description=f"Guruhda {amount} {curr_label} ulashish (komissiya: {fee} {curr_icon})"
                )

                drop = GiveawayDrop.objects.create(
                    sender_telegram_id=sender_telegram_id,
                    sender_name=sender_name,
                    chat_id=chat_id,
                    currency=currency,
                    total_amount=amount,
                    claimed_amount=0,
                    commission_amount=fee,
                    is_active=True
                )
                return True, f"✅ {amount} {curr_icon} {curr_label} muvaffaqiyatli ulashildi!", drop

        except InsufficientBalanceError:
            return (
                False,
                f"❌ Mablag' yetarli emas!\nSiz {amount} {curr_icon} ulashmoqchisiz, 3% komissiya bilan hisobingizda jami <b>{total_needed} {curr_icon}</b> bo'lishi kerak.",
                None
            )
        except Exception as e:
            return False, f"❌ Xatolik yuz berdi: {str(e)}", None

    @classmethod
    def claim_drop(
        cls,
        drop_id: str,
        user_telegram_id: int,
        user_name: str
    ) -> Tuple[bool, str, int, int]:
        """
        Atomically allows a user to claim exactly 1 unit from a GiveawayDrop.
        Returns: (success, message, remaining_amount, total_amount)
        """
        try:
            with transaction.atomic():
                drop = GiveawayDrop.objects.select_for_update().filter(id=drop_id).first()
                if not drop:
                    return False, "❌ Bu ulashuv topilmadi!", 0, 0

                if not drop.is_active or drop.remaining_amount <= 0:
                    return False, "❌ Barcha sovg'alar olingan!", 0, drop.total_amount

                # Check if already claimed
                already_claimed = GiveawayClaim.objects.filter(
                    drop=drop, telegram_user_id=user_telegram_id
                ).exists()
                if already_claimed:
                    return False, "❌ Siz bu ulashuvdan allaqachon 1 dona olgansiz!", drop.remaining_amount, drop.total_amount

                # Create claim record
                GiveawayClaim.objects.create(
                    drop=drop,
                    telegram_user_id=user_telegram_id,
                    user_name=user_name
                )

                drop.claimed_amount += 1
                if drop.claimed_amount >= drop.total_amount:
                    drop.is_active = False
                drop.save(update_fields=['claimed_amount', 'is_active', 'updated_at'])

                # Credit 1 unit to user's wallet
                user_wallet = EconomyService.get_or_create_wallet(telegram_id=user_telegram_id)
                curr_icon = "💎" if drop.currency == CurrencyType.DIAMONDS else "💶"
                EconomyService.credit_wallet(
                    wallet=user_wallet,
                    currency=drop.currency,
                    amount=Decimal('1'),
                    tx_type=TransactionType.GIFT,
                    description=f"Guruhdagi ulashuvdan 1 {curr_icon} olindi"
                )

                curr_name = "Olmos" if drop.currency == CurrencyType.DIAMONDS else "Dollar"
                return True, f"🎉 Tabriklaymiz! Sizga 1 {curr_icon} {curr_name} berildi!", drop.remaining_amount, drop.total_amount

        except Exception as e:
            return False, f"❌ Xatolik yuz berdi: {str(e)}", 0, 0
