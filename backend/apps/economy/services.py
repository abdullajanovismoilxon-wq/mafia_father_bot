import uuid
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.economy.models import (
    Wallet, WalletTransaction, CurrencyType, TransactionType,
    CurrencyRate, MarketplaceCategory, MarketplaceItem, MarketplaceItemType,
    Purchase, Inventory, GiftRecord, VIPLevel, VIPSubscription,
    PaymentOrder, PaymentOrderStatus, PlayerHero
)
from apps.common.models import AdminAuditLog, AdminAuditAction


class InsufficientBalanceError(Exception):
    """Raised when a wallet does not have enough balance for a debit."""
    pass


class EconomyService:
    """Server-authoritative wallet and transaction engine."""

    @classmethod
    def get_or_create_wallet(cls, user=None, telegram_id=None) -> Wallet:
        """Find or create a unique wallet for user or telegram_id."""
        if telegram_id:
            wallet = Wallet.objects.filter(telegram_id=telegram_id).first()
            if wallet:
                if user and user.is_authenticated and not wallet.user:
                    wallet.user = user
                    wallet.save(update_fields=['user'])
                return wallet
        if user and user.is_authenticated:
            wallet = Wallet.objects.filter(user=user).first()
            if wallet:
                if telegram_id and not wallet.telegram_id:
                    wallet.telegram_id = telegram_id
                    wallet.save(update_fields=['telegram_id'])
                return wallet
            wallet, _ = Wallet.objects.get_or_create(user=user, defaults={'telegram_id': telegram_id or user.telegram_id})
            return wallet
        if telegram_id:
            wallet, _ = Wallet.objects.get_or_create(telegram_id=telegram_id)
            return wallet
        raise ValueError("Either user or telegram_id must be provided to get_or_create_wallet.")

    @classmethod
    def get_usd_to_uzs_rate(cls) -> Decimal:
        """Get or initialize default USD to UZS exchange rate."""
        rate_obj, _ = CurrencyRate.objects.get_or_create(
            currency_code='UZS',
            defaults={'rate_to_usd': Decimal('12750.0000'), 'name': "O'zbek so'mi"}
        )
        return rate_obj.rate_to_usd

    @classmethod
    def credit_wallet(
        cls,
        wallet: Wallet,
        currency: str,
        amount: Decimal,
        tx_type: str = TransactionType.DEPOSIT,
        description: str = '',
        reference_id: str = '',
        metadata: dict = None
    ) -> WalletTransaction:
        """Atomically credits money, diamonds, or coins to a wallet."""
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError("Credit amount must be positive.")

        with transaction.atomic():
            locked_wallet = Wallet.objects.select_for_update().get(id=wallet.id)
            if currency == CurrencyType.MONEY:
                locked_wallet.money += amount
                balance_after = locked_wallet.money
            elif currency == CurrencyType.DIAMONDS:
                locked_wallet.diamonds += int(amount)
                balance_after = Decimal(locked_wallet.diamonds)
            elif currency == CurrencyType.COINS:
                locked_wallet.coins += int(amount)
                balance_after = Decimal(locked_wallet.coins)
            else:
                raise ValueError(f"Unknown currency: {currency}")

            locked_wallet.save()

            tx = WalletTransaction.objects.create(
                wallet=locked_wallet,
                tx_type=tx_type,
                currency=currency,
                amount=amount,
                balance_after=balance_after,
                reference_id=reference_id,
                description=description,
                metadata=metadata or {}
            )
            return tx

    @classmethod
    def debit_wallet(
        cls,
        wallet: Wallet,
        currency: str,
        amount: Decimal,
        tx_type: str = TransactionType.PURCHASE,
        description: str = '',
        reference_id: str = '',
        metadata: dict = None
    ) -> WalletTransaction:
        """Atomically debits funds from a wallet with strict balance check."""
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError("Debit amount must be positive.")

        with transaction.atomic():
            locked_wallet = Wallet.objects.select_for_update().get(id=wallet.id)
            if currency == CurrencyType.MONEY:
                if locked_wallet.money < amount:
                    raise InsufficientBalanceError(f"Insufficient funds: available ${locked_wallet.money}, needed ${amount}")
                locked_wallet.money -= amount
                balance_after = locked_wallet.money
            elif currency == CurrencyType.DIAMONDS:
                int_amount = int(amount)
                if locked_wallet.diamonds < int_amount:
                    raise InsufficientBalanceError(f"Insufficient diamonds: available 💎{locked_wallet.diamonds}, needed 💎{int_amount}")
                locked_wallet.diamonds -= int_amount
                balance_after = Decimal(locked_wallet.diamonds)
            elif currency == CurrencyType.COINS:
                int_amount = int(amount)
                if locked_wallet.coins < int_amount:
                    raise InsufficientBalanceError(f"Insufficient coins: available 🪙{locked_wallet.coins}, needed 🪙{int_amount}")
                locked_wallet.coins -= int_amount
                balance_after = Decimal(locked_wallet.coins)
            else:
                raise ValueError(f"Unknown currency: {currency}")

            locked_wallet.save()

            tx = WalletTransaction.objects.create(
                wallet=locked_wallet,
                tx_type=tx_type,
                currency=currency,
                amount=-amount,
                balance_after=balance_after,
                reference_id=reference_id,
                description=description,
                metadata=metadata or {}
            )
            return tx

    @classmethod
    def transfer_money(
        cls,
        sender_wallet: Wallet,
        recipient_wallet: Wallet,
        amount: Decimal,
        description: str = ''
    ) -> tuple[WalletTransaction, WalletTransaction]:
        """Atomically transfers money from one wallet to another."""
        if sender_wallet.id == recipient_wallet.id:
            raise ValueError("Cannot transfer money to your own wallet.")
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError("Transfer amount must be greater than zero.")

        ref_id = f"tx_money_{uuid.uuid4().hex[:12]}"
        with transaction.atomic():
            debit_tx = cls.debit_wallet(
                wallet=sender_wallet,
                currency=CurrencyType.MONEY,
                amount=amount,
                tx_type=TransactionType.TRANSFER,
                description=description or f"Transfer to {recipient_wallet.id}",
                reference_id=ref_id,
                metadata={'recipient_wallet_id': str(recipient_wallet.id)}
            )
            credit_tx = cls.credit_wallet(
                wallet=recipient_wallet,
                currency=CurrencyType.MONEY,
                amount=amount,
                tx_type=TransactionType.TRANSFER,
                description=description or f"Transfer from {sender_wallet.id}",
                reference_id=ref_id,
                metadata={'sender_wallet_id': str(sender_wallet.id)}
            )
            return debit_tx, credit_tx

    @classmethod
    def transfer_diamonds(
        cls,
        sender_wallet: Wallet,
        recipient_wallet: Wallet,
        amount: int,
        description: str = ''
    ) -> tuple[WalletTransaction, WalletTransaction]:
        """Atomically transfers diamonds from one wallet to another."""
        if sender_wallet.id == recipient_wallet.id:
            raise ValueError("Cannot transfer diamonds to your own wallet.")
        if amount <= 0:
            raise ValueError("Transfer amount must be greater than zero.")

        ref_id = f"tx_dia_{uuid.uuid4().hex[:12]}"
        with transaction.atomic():
            debit_tx = cls.debit_wallet(
                wallet=sender_wallet,
                currency=CurrencyType.DIAMONDS,
                amount=Decimal(amount),
                tx_type=TransactionType.TRANSFER,
                description=description or f"Diamond transfer to {recipient_wallet.id}",
                reference_id=ref_id,
                metadata={'recipient_wallet_id': str(recipient_wallet.id)}
            )
            credit_tx = cls.credit_wallet(
                wallet=recipient_wallet,
                currency=CurrencyType.DIAMONDS,
                amount=Decimal(amount),
                tx_type=TransactionType.TRANSFER,
                description=description or f"Diamond transfer from {sender_wallet.id}",
                reference_id=ref_id,
                metadata={'sender_wallet_id': str(sender_wallet.id)}
            )
            return debit_tx, credit_tx


class MarketplaceService:
    """Handles marketplace purchases, VIP activations, and P2P payments."""

    @classmethod
    def get_or_create_default_categories_and_items(cls):
        """Initializes default marketplace categories and standard catalog items."""
        cat_dia, _ = MarketplaceCategory.objects.get_or_create(
            code='DIAMONDS',
            defaults={'name': 'Olmoslar (Diamonds)', 'icon': '💎', 'order': 1}
        )
        cat_vip, _ = MarketplaceCategory.objects.get_or_create(
            code='VIP',
            defaults={'name': 'VIP Aʼzolik', 'icon': '⭐', 'order': 2}
        )
        cat_cosm, _ = MarketplaceCategory.objects.get_or_create(
            code='COSMETICS',
            defaults={'name': 'Kosmetika & Niqoblar', 'icon': '🎭', 'order': 3}
        )

        # Standard Diamond Packages from reference screenshot
        diamond_packs = [
            ('DIA_1', '💎 1 Olmos', Decimal('0.20'), 1),
            ('DIA_5', '💎 5 Olmos', Decimal('0.80'), 5),
            ('DIA_10', '💎 10 Olmos', Decimal('1.36'), 10),
            ('DIA_15', '💎 15 Olmos', Decimal('1.90'), 15),
            ('DIA_30', '💎 30 Olmos', Decimal('3.50'), 30),
            ('DIA_50', '💎 50 Olmos', Decimal('5.50'), 50),
            ('DIA_250', '💎 250 Olmos', Decimal('25.00'), 250),
            ('DIA_1000', '💎 1000 Olmos', Decimal('90.00'), 1000),
        ]
        for code, name, usd_price, count in diamond_packs:
            MarketplaceItem.objects.get_or_create(
                code=code,
                defaults={
                    'category': cat_dia,
                    'name': name,
                    'item_type': MarketplaceItemType.DIAMONDS_PACK,
                    'price_money_usd': usd_price,
                    'price_diamonds': 0,
                    'diamond_amount': count,
                    'icon': '💎',
                    'description': f'{count} ta olmos to\'plami'
                }
            )

        # VIP packs
        vip_packs = [
            ('VIP_BRONZE_30', '🥉 VIP Bronze (30 kun)', 25, Decimal('3.00'), 30),
            ('VIP_GOLD_30', '🥇 VIP Gold (30 kun)', 50, Decimal('6.00'), 30),
            ('VIP_DIAMOND_30', '💎 VIP Diamond (30 kun)', 100, Decimal('12.00'), 30),
        ]
        for code, name, dia_price, usd_price, days in vip_packs:
            MarketplaceItem.objects.update_or_create(
                code=code,
                defaults={
                    'category': cat_vip,
                    'name': name,
                    'item_type': MarketplaceItemType.VIP_PACK,
                    'price_diamonds': dia_price,
                    'price_money_usd': usd_price,
                    'vip_days': days,
                    'icon': '⭐',
                    'description': f'{days} kunlik VIP a\'zolik',
                    'is_active': True
                }
            )

        cat_items, _ = MarketplaceCategory.objects.get_or_create(
            code='GAME_ITEMS',
            defaults={'name': 'O\'yin Ashyolari (Do\'kon)', 'icon': '🎒', 'order': 4}
        )

        # The 10 In-game Items requested by user
        game_shop_items = [
            ('DOCUMENTS', '📁 Hujjatlar', 5, '📁', 'Kimdir sizning rolingizni tekshirmoqchi bo\'lsa, soxta hujjatlar yordam berishi mumkin.'),
            ('SHIELD', '🛡 Himoya', 10, '🛡', 'Bir marta hayotingizni saqlab qoladi.'),
            ('VOTE_SHIELD', '⚖️ Ovozdan himoya', 8, '⚖️', 'Kun davomida sizni osishga hukm qilsalar, bir marta qutqaradi.'),
            ('KILLER_SHIELD', '⛑️ Qotildan himoya', 12, '⛑️', 'Siz bu yordamida 🔪 Qotil va 🥷 Yollanma qotildan himoyalana olasiz. Bitta o\'yinda bir nechta yani cheksiz himoya ishlata olasiz.'),
            ('RIFLE', '🔫 Miltiq', 15, '🔫', 'Bu sizga komissar, don, rollarida otayotgan odamingizda himoya bor bo\'lsa ham o\'ltirish uchun yordam beradi.'),
            ('POISON_SHIELD', '💊 Doridan himoya', 6, '💊', 'Bu sizni kezuvchining dorisidan himoya qiladi!'),
            ('MASK', '🎭 Maska', 7, '🎭', 'Buni olsangiz daydi sizni taniy olmaydi!'),
            ('HERO', '🥷 Geroy', 20, '🥷', 'Sizga o\'yinda tong vaqtida ham otish imkonini beradi...'),
            ('SLIP_SHIELD', '🪤 Sirpanishdan himoya', 6, '🪤', 'Sizni konchi roldialigingizda sirpanib o\'lishdan saqlab qoladi.'),
            ('HERO_SHIELD', '🔰 Geroydan himoya', 14, '🔰', 'Sizga geroydan bo\'lgan har qanday hujumdan omon qolish imkonini beradi.'),
        ]

        for code, name, dia_price, icon, desc in game_shop_items:
            MarketplaceItem.objects.update_or_create(
                code=code,
                defaults={
                    'category': cat_items,
                    'name': name,
                    'item_type': MarketplaceItemType.BONUS,
                    'price_diamonds': dia_price,
                    'price_money_usd': Decimal(str(dia_price * 0.136)).quantize(Decimal('0.01')),
                    'icon': icon,
                    'description': desc,
                    'is_active': True
                }
            )

    @classmethod
    def purchase_item(
        cls,
        item_code: str,
        user=None,
        telegram_id=None,
        currency: str = CurrencyType.DIAMONDS
    ) -> Purchase:
        """Buys a marketplace item using user's wallet."""
        cls.get_or_create_default_categories_and_items()
        item = MarketplaceItem.objects.get(code=item_code, is_active=True)
        wallet = EconomyService.get_or_create_wallet(user=user, telegram_id=telegram_id)

        with transaction.atomic():
            if currency == CurrencyType.DIAMONDS:
                price = Decimal(item.price_diamonds)
                if price <= 0:
                    raise ValueError("Item cannot be bought with diamonds.")
                EconomyService.debit_wallet(
                    wallet=wallet,
                    currency=CurrencyType.DIAMONDS,
                    amount=price,
                    tx_type=TransactionType.PURCHASE,
                    description=f"Purchase: {item.name}",
                    metadata={'item_code': item.code}
                )
            elif currency == CurrencyType.MONEY:
                price = item.price_money_usd
                if price <= 0:
                    raise ValueError("Item cannot be bought with money balance.")
                EconomyService.debit_wallet(
                    wallet=wallet,
                    currency=CurrencyType.MONEY,
                    amount=price,
                    tx_type=TransactionType.PURCHASE,
                    description=f"Purchase: {item.name}",
                    metadata={'item_code': item.code}
                )
            else:
                raise ValueError("Unsupported payment currency.")

            # Process benefits
            if item.item_type == MarketplaceItemType.DIAMONDS_PACK:
                EconomyService.credit_wallet(
                    wallet=wallet,
                    currency=CurrencyType.DIAMONDS,
                    amount=Decimal(item.diamond_amount),
                    tx_type=TransactionType.PURCHASE,
                    description=f"Credited from {item.name}"
                )
            elif item.item_type == MarketplaceItemType.VIP_PACK:
                cls.grant_vip(
                    user=user,
                    telegram_id=telegram_id,
                    vip_level=VIPLevel.GOLD,
                    duration_days=item.vip_days
                )
            else:
                # Add to inventory
                inv, _ = Inventory.objects.get_or_create(
                    user=user if user and user.is_authenticated else None,
                    telegram_id=telegram_id if not (user and user.is_authenticated) else None,
                    item=item,
                    defaults={'quantity': 1}
                )
                if not inv._state.adding:
                    inv.quantity += 1
                    inv.save(update_fields=['quantity'])

            purchase = Purchase.objects.create(
                user=user if user and user.is_authenticated else None,
                telegram_id=telegram_id or (user.telegram_id if user else None),
                item=item,
                amount_paid=price,
                currency_paid=currency,
                status='COMPLETED'
            )
            return purchase

    @classmethod
    def grant_vip(
        cls,
        user=None,
        telegram_id=None,
        vip_level: str = VIPLevel.GOLD,
        duration_days: int = 30,
        admin_user=None
    ) -> VIPSubscription:
        """Activates or extends a player's VIP subscription."""
        now = timezone.now()
        filters = {}
        if user and user.is_authenticated:
            filters['user'] = user
        elif telegram_id:
            filters['telegram_id'] = telegram_id
        else:
            raise ValueError("Must provide user or telegram_id.")

        with transaction.atomic():
            vip_sub, created = VIPSubscription.objects.get_or_create(
                **filters,
                defaults={
                    'vip_level': vip_level,
                    'starts_at': now,
                    'expires_at': now + timezone.timedelta(days=duration_days),
                    'is_active': True
                }
            )
            if not created:
                start_from = max(vip_sub.expires_at, now) if vip_sub.is_active else now
                vip_sub.expires_at = start_from + timezone.timedelta(days=duration_days)
                vip_sub.vip_level = vip_level
                vip_sub.is_active = True
                vip_sub.save(update_fields=['expires_at', 'vip_level', 'is_active'])

            if admin_user:
                AdminAuditLog.objects.create(
                    admin=admin_user,
                    action=AdminAuditAction.GRANT_VIP,
                    target_type='VIP_SUBSCRIPTION',
                    target_id=str(vip_sub.id),
                    metadata={'level': vip_level, 'days': duration_days, 'target': str(user or telegram_id)}
                )

            return vip_sub

    @classmethod
    def create_payment_order(
        cls,
        diamonds: int,
        payment_method: str = 'P2P_CARD',
        user=None,
        telegram_id=None,
        receipt_reference: str = '',
        receipt_ref: str = '',
        receipt_image_url: str = ''
    ) -> PaymentOrder:
        """Creates a manual P2P payment order with calculated USD and UZS amounts."""
        # Standard pricing: 1 Diamond ~= $0.136
        diamonds = int(diamonds)
        if diamonds <= 0:
            raise ValueError("Diamond quantity must be positive.")

        usd_rate_per_diamond = Decimal('0.136')
        amount_usd = (Decimal(diamonds) * usd_rate_per_diamond).quantize(Decimal('0.01'))
        uzs_rate = EconomyService.get_usd_to_uzs_rate()
        amount_uzs = (amount_usd * uzs_rate).quantize(Decimal('0.01'))

        order_id = f"ORD_{uuid.uuid4().hex[:8].upper()}"
        order = PaymentOrder.objects.create(
            user=user if user and user.is_authenticated else None,
            telegram_id=telegram_id or (user.telegram_id if user else None),
            order_id=order_id,
            amount_usd=amount_usd,
            amount_uzs=amount_uzs,
            diamonds_to_credit=diamonds,
            payment_method=payment_method,
            receipt_reference=receipt_reference or receipt_ref,
            receipt_image_url=receipt_image_url,
            status=PaymentOrderStatus.PENDING_REVIEW
        )
        return order

    @classmethod
    def review_payment_order(
        cls,
        order_id: str,
        admin_user,
        approve: bool = True,
        status: str = '',
        admin_notes: str = '',
        notes: str = ''
    ) -> PaymentOrder:
        """Approves or rejects a manual payment order, crediting wallet atomically if approved."""
        is_approved = approve
        if status:
            is_approved = (status == PaymentOrderStatus.APPROVED or status == 'APPROVED')
        final_notes = admin_notes or notes

        with transaction.atomic():
            order = PaymentOrder.objects.select_for_update().get(order_id=order_id)
            if order.status != PaymentOrderStatus.PENDING_REVIEW:
                raise ValueError(f"Order #{order_id} has already been reviewed ({order.status}).")

            if is_approved:
                order.status = PaymentOrderStatus.APPROVED
                wallet = EconomyService.get_or_create_wallet(
                    user=order.user,
                    telegram_id=order.telegram_id
                )
                EconomyService.credit_wallet(
                    wallet=wallet,
                    currency=CurrencyType.DIAMONDS,
                    amount=Decimal(order.diamonds_to_credit),
                    tx_type=TransactionType.DEPOSIT,
                    description=f"P2P Payment approved #{order.order_id}",
                    reference_id=order.order_id
                )
                AdminAuditLog.objects.create(
                    admin=admin_user,
                    action=AdminAuditAction.APPROVE_PAYMENT,
                    target_type='PAYMENT_ORDER',
                    target_id=order.order_id,
                    metadata={'diamonds': order.diamonds_to_credit, 'amount_usd': str(order.amount_usd)}
                )
            else:
                order.status = PaymentOrderStatus.REJECTED
                AdminAuditLog.objects.create(
                    admin=admin_user,
                    action=AdminAuditAction.REJECT_PAYMENT,
                    target_type='PAYMENT_ORDER',
                    target_id=order.order_id,
                    metadata={'notes': final_notes}
                )

            order.reviewed_by = admin_user
            order.reviewed_at = timezone.now()
            order.admin_notes = final_notes
            order.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'admin_notes'])
            return order


class HeroService:
    """Business logic for custom Heroes (Geroy)."""

    @classmethod
    def get_hero(cls, telegram_id: int) -> PlayerHero | None:
        """Fetch hero for a specific player if exists."""
        return PlayerHero.objects.filter(telegram_id=telegram_id).first()

    @classmethod
    def create_hero(cls, telegram_id: int, name: str, owner_name: str = "O'yinchi", price_diamonds: int = 80) -> tuple[bool, str, PlayerHero | None]:
        """Creates or buys a new hero for a player."""
        existing = cls.get_hero(telegram_id)
        if existing:
            return False, "Sizda allaqachon Geroy mavjud!", existing

        wallet = EconomyService.get_or_create_wallet(telegram_id=telegram_id)
        
        # Check platform owner bypass
        from apps.stats.models import PlayerProfile
        profile = PlayerProfile.objects.filter(telegram_id=telegram_id).first()
        is_owner = (telegram_id == 7782387930) or (profile and profile.is_platform_owner)

        if not is_owner and wallet.diamonds < price_diamonds:
            return False, f"Geroy yaratish uchun {price_diamonds} 💎 olmos yetarli emas!", None

        if not is_owner and price_diamonds > 0:
            wallet.diamonds -= price_diamonds
            wallet.save(update_fields=['diamonds'])

        clean_name = name.strip() or "Mening Geroyim"
        clean_owner = owner_name.strip() or "O'yinchi"

        hero = PlayerHero.objects.create(
            telegram_id=telegram_id,
            owner_name=clean_owner,
            name=clean_name,
            level=1,
            score=0,
            charges=10,
            is_active=True
        )
        return True, f"🎉 <b>{clean_name}</b> nomli Geroy muvaffaqiyatli yaratildi!", hero

    @classmethod
    def recharge_hero(cls, telegram_id: int) -> tuple[bool, str, int]:
        """Recharges +1 charge (or setting amount) to the hero deducting diamond cost."""
        hero = cls.get_hero(telegram_id)
        if not hero:
            return False, "Sizda Geroy mavjud emas!", 0

        from apps.superadmin.services import SettingService
        recharge_amount = SettingService.get_int('hero_recharge_amount', 1)
        max_charges = SettingService.get_int('hero_max_charges', 10)

        if hero.charges >= max_charges:
            return False, f"⚠️ Geroyingiz zaryadi allaqachon to'liq ({hero.charges}/{max_charges})!", hero.charges

        cost = hero.recharge_cost_diamonds
        wallet = EconomyService.get_or_create_wallet(telegram_id=telegram_id)

        from apps.stats.models import PlayerProfile
        profile = PlayerProfile.objects.filter(telegram_id=telegram_id).first()
        is_owner = (telegram_id == 7782387930) or (profile and profile.is_platform_owner)

        if not is_owner and wallet.diamonds < cost:
            return False, f"Geroyni zaryadlash uchun hisobingizda <b>{cost} 💎</b> olmos yetarli emas!", hero.charges

        if not is_owner:
            wallet.diamonds -= cost
            wallet.save(update_fields=['diamonds'])

        hero.charges = min(max_charges, hero.charges + recharge_amount)
        hero.save(update_fields=['charges'])

        charge_label = f"+{recharge_amount}" if recharge_amount > 1 else "+1"
        return True, f"🔋 Geroy muvaffaqiyatli zaryadlandi! ({charge_label} zaryad, Jami: {hero.charges}/{max_charges})", hero.charges

    @classmethod
    def rename_hero(cls, telegram_id: int, new_name: str) -> tuple[bool, str]:
        """Renames the player's hero charging 5 diamonds (free for platform owner)."""
        hero = cls.get_hero(telegram_id)
        if not hero:
            return False, "Sizda Geroy mavjud emas!"

        clean_name = new_name.strip()
        if not clean_name or len(clean_name) < 2:
            return False, "Geroy nomi kamida 2 ta belgidan iborat bo'lishi kerak!"

        from apps.superadmin.services import SettingService
        rename_cost = SettingService.get_int('price_hero_rename', 5)

        from apps.stats.models import PlayerProfile
        profile = PlayerProfile.objects.filter(telegram_id=telegram_id).first()
        is_owner = (telegram_id == 7782387930) or (profile and profile.is_platform_owner)

        wallet = EconomyService.get_or_create_wallet(telegram_id=telegram_id)
        if not is_owner:
            if wallet.diamonds < rename_cost:
                return False, f"Geroy nomini o'zgartirish uchun hisobingizda <b>{rename_cost} 💎</b> olmos yetarli emas!"
            wallet.diamonds -= rename_cost
            wallet.save(update_fields=['diamonds'])

        hero.name = clean_name[:50]
        hero.save(update_fields=['name'])
        
        cost_str = f" (-{rename_cost} 💎)" if not is_owner else " (👑 VIP Bepul)"
        return True, f"✅ Geroy nomi muvaffaqiyatli <b>{hero.name}</b> ga o'zgartirildi!{cost_str}"

    @classmethod
    def transfer_hero(cls, sender_tg_id: int, recipient_tg_id: int, new_owner_name: str = "O'yinchi") -> tuple[bool, str]:
        """Transfers ownership of a hero from sender to recipient."""
        if sender_tg_id == recipient_tg_id:
            return False, "O'zingizga o'tkaza olmaysiz!"

        hero = cls.get_hero(sender_tg_id)
        if not hero:
            return False, "Sizda o'tkazish uchun Geroy mavjud emas!"

        recip_hero = cls.get_hero(recipient_tg_id)
        if recip_hero:
            return False, "Qabul qiluvchida allaqachon Geroy mavjud!"

        hero.telegram_id = recipient_tg_id
        hero.owner_name = new_owner_name or "O'yinchi"
        hero.save(update_fields=['telegram_id', 'owner_name'])
        return True, f"🎁 Geroy muvaffaqiyatli {new_owner_name} ga o'tkazildi!"

    @classmethod
    def toggle_hero(cls, telegram_id: int) -> tuple[bool, bool]:
        """Toggles hero active status."""
        hero = cls.get_hero(telegram_id)
        if not hero:
            return False, False
        hero.is_active = not hero.is_active
        hero.save(update_fields=['is_active'])
        return True, hero.is_active

    @classmethod
    def format_hero_card_text(cls, hero: PlayerHero, geroy_himoya_count: int = 0) -> str:
        """Formats rich hero statistics text matching the exact specification."""
        return (
            f"🥷 <b>Geroy:</b> {hero.name}\n"
            f"👤 <b>Kim uchun:</b> {hero.owner_name}\n\n"
            f"⭐ <b>Daraja:</b> {hero.level}\n"
            f"👊 <b>Kuch:</b> {hero.power_min}-{hero.power_max} oralig'ida\n"
            f"🖤 <b>Himoya:</b> {hero.current_defense}\n"
            f"❤️ <b>Max himoya:</b> {hero.max_defense}\n"
            f"🩸 <b>Zaryad miqdori:</b> {hero.charges}\n"
            f"☑️ <b>Jami ballari:</b> {hero.score} ball\n"
            f"🔰 <b>Geroydan himoya:</b> {geroy_himoya_count}\n\n"
            f"⬆️ <b>Keyingi daraja</b> = {hero.level + 1} => {hero.next_level_score} ball"
        )

    @classmethod
    def format_no_hero_text(cls, owner_name: str) -> str:
        """Formats message when player has no hero matching screenshot 2."""
        return f"🥷 <i>{owner_name}</i> da Geroy mavjud emas!"


class CasinoService:
    """Casino logic: Roulette and Mystery Loot Boxes (Sandiqlar)."""

    RED_NUMBERS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
    BLACK_NUMBERS = {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}

    @classmethod
    def play_roulette(cls, telegram_id: int, bet_amount: int, bet_color: str) -> dict:
        """
        Server-authoritative roulette game.
        bet_color: 'red' (x2), 'black' (x2), 'green' (x14)
        """
        import random
        if bet_amount <= 0:
            return {'ok': False, 'error': "Tikish miqdori 0 dan katta bo'lishi kerak!"}

        clean_color = bet_color.lower().strip()
        if clean_color not in ['red', 'black', 'green']:
            return {'ok': False, 'error': "Noto'g'ri rang tanlandi (qizil, qora yoki yashil)!"}

        wallet = EconomyService.get_or_create_wallet(telegram_id=telegram_id)
        from apps.stats.models import PlayerProfile
        profile = PlayerProfile.objects.filter(telegram_id=telegram_id).first()
        is_owner = (telegram_id == 7782387930) or (profile and profile.is_platform_owner)

        cur_money = max(wallet.coins, int(wallet.money))
        if not is_owner and cur_money < bet_amount:
            return {'ok': False, 'error': f"Hisobingizda mablag' yetarli emas! (Mavjud: {cur_money} 💶)"}

        # Deduct bet
        if not is_owner:
            wallet.coins = max(0, wallet.coins - bet_amount)
            wallet.money = max(Decimal('0.00'), wallet.money - Decimal(str(bet_amount)))
            wallet.save(update_fields=['coins', 'money'])

        # Roll number (0-36)
        num = random.randint(0, 36)
        if num == 0:
            res_color = 'green'
        elif num in cls.RED_NUMBERS:
            res_color = 'red'
        else:
            res_color = 'black'

        won = False
        multiplier = 0
        if clean_color == 'green' and num == 0:
            won = True
            multiplier = 14
        elif clean_color == 'red' and res_color == 'red':
            won = True
            multiplier = 2
        elif clean_color == 'black' and res_color == 'black':
            won = True
            multiplier = 2

        payout = 0
        if won:
            payout = bet_amount * multiplier
            wallet.coins += payout
            wallet.money += Decimal(str(payout))
            wallet.save(update_fields=['coins', 'money'])

        new_money = max(wallet.coins, int(wallet.money))

        color_name_uz = {'red': 'Qizil', 'black': 'Qora', 'green': 'Yashil 0'}[res_color]
        if won:
            msg = f"🎉 G'alaba! Tushgan raqam: {num} ({color_name_uz}). Siz +{payout:,} 💶 yutib oldingiz!".replace(",", " ")
        else:
            msg = f"Imkoniyat boy berildi. Tushgan raqam: {num} ({color_name_uz})."

        return {
            'ok': True,
            'won': won,
            'payout': payout,
            'number': num,
            'color': res_color,
            'multiplier': multiplier,
            'new_money': f"{new_money:,}".replace(",", " "),
            'new_diamonds': wallet.diamonds,
            'message': msg
        }

    @classmethod
    def open_chest(cls, telegram_id: int, chest_type: int) -> dict:
        """
        Opens a mystery loot box chest (1, 2, or 3).
        Chest 1 = 20,000 $
        Chest 2 = 15 💎
        Chest 3 = 20 💎 (Every 3rd open guarantees a HERO!)
        """
        import random
        from apps.stats.models import PlayerProfile
        from apps.economy.models import MarketplaceCategory, MarketplaceItem, MarketplaceItemType, Inventory, VIPSubscription, VIPLevel
        from django.utils import timezone
        from datetime import timedelta

        wallet = EconomyService.get_or_create_wallet(telegram_id=telegram_id)
        profile = PlayerProfile.objects.filter(telegram_id=telegram_id).first()
        is_owner = (telegram_id == 7782387930) or (profile and profile.is_platform_owner)

        cur_money = max(wallet.coins, int(wallet.money))

        # -------------------------------------------------------------
        # CHEST 1: 20 000 $
        # -------------------------------------------------------------
        if chest_type == 1:
            cost = 20000
            if not is_owner and cur_money < cost:
                return {'ok': False, 'error': f"1-Sandiqni ochish uchun 20 000 💶 yetarli emas!"}

            if not is_owner:
                wallet.coins = max(0, wallet.coins - cost)
                wallet.money = max(Decimal('0.00'), wallet.money - Decimal(str(cost)))
                wallet.save(update_fields=['coins', 'money'])

            roll = random.random()
            if roll < 0.35:
                # Big Money Prize (25k - 60k $)
                win_m = random.choice([25000, 30000, 40000, 50000, 60000])
                wallet.coins += win_m
                wallet.money += Decimal(str(win_m))
                wallet.save(update_fields=['coins', 'money'])
                prize = {'type': 'MONEY', 'title': f"{win_m:,} 💶 Dollar".replace(",", " "), 'icon': '💶', 'desc': 'Katta dollar mukofoti!'}
            elif roll < 0.60:
                # Diamonds Prize (1 - 5 💎)
                win_d = random.randint(1, 5)
                wallet.diamonds += win_d
                wallet.save(update_fields=['diamonds'])
                prize = {'type': 'DIAMONDS', 'title': f"{win_d} 💎 Olmos", 'icon': '💎', 'desc': 'Qimmatbaho olmoslar!'}
            elif roll < 0.85:
                # Defense Item
                item_code = random.choice(['himoya', 'hujjat', 'dori_himoya', 'osish_himoya', 'sirpanish_himoya'])
                item_names = {
                    'himoya': '🛡 Asosiy Himoya',
                    'hujjat': '📁 Soxta Hujjat',
                    'dori_himoya': '💊 Doridan Himoya',
                    'osish_himoya': '⚖️ Ovozdan Himoya',
                    'sirpanish_himoya': '🥷 Sirpanishdan Himoya'
                }
                cat, _ = MarketplaceCategory.objects.get_or_create(code='items', defaults={'name': 'Himoyalar'})
                item, _ = MarketplaceItem.objects.get_or_create(code=item_code, defaults={'name': item_names[item_code], 'category': cat, 'item_type': MarketplaceItemType.BONUS})
                inv, _ = Inventory.objects.get_or_create(telegram_id=telegram_id, item=item, defaults={'quantity': 0, 'is_active': True})
                inv.quantity += 1
                inv.save(update_fields=['quantity'])
                prize = {'type': 'ITEM', 'title': item_names[item_code], 'icon': '🛡', 'desc': 'Himoya inventaringizga qo\'shildi!'}
            else:
                # Minor Cashback (10k - 18k $)
                win_m = random.choice([10000, 12000, 15000, 18000])
                wallet.coins += win_m
                wallet.money += Decimal(str(win_m))
                wallet.save(update_fields=['coins', 'money'])
                prize = {'type': 'MONEY', 'title': f"{win_m:,} 💶 Dollar".replace(",", " "), 'icon': '💶', 'desc': 'Qisman keshbek!'}

            new_money = max(wallet.coins, int(wallet.money))
            return {
                'ok': True,
                'chest_type': 1,
                'prize': prize,
                'new_money': f"{new_money:,}".replace(",", " "),
                'new_diamonds': wallet.diamonds,
                'message': f"🎁 Sandiqdan chiqdi: {prize['title']}!"
            }

        # -------------------------------------------------------------
        # CHEST 2: 15 💎
        # -------------------------------------------------------------
        elif chest_type == 2:
            cost = 15
            if not is_owner and wallet.diamonds < cost:
                return {'ok': False, 'error': f"2-Sandiqni ochish uchun 15 💎 olmos yetarli emas!"}

            if not is_owner:
                wallet.diamonds -= cost
                wallet.save(update_fields=['diamonds'])

            roll = random.random()
            if roll < 0.35:
                # Win Diamonds (20 - 45 💎)
                win_d = random.choice([20, 25, 30, 40, 45])
                wallet.diamonds += win_d
                wallet.save(update_fields=['diamonds'])
                prize = {'type': 'DIAMONDS', 'title': f"{win_d} 💎 Olmos", 'icon': '💎', 'desc': 'Foydali olmos yutug\'i!'}
            elif roll < 0.60:
                # Big Money (150k - 500k $)
                win_m = random.choice([150000, 250000, 350000, 500000])
                wallet.coins += win_m
                wallet.money += Decimal(str(win_m))
                wallet.save(update_fields=['coins', 'money'])
                prize = {'type': 'MONEY', 'title': f"{win_m:,} 💶 Dollar".replace(",", " "), 'icon': '💰', 'desc': 'Ulkan dollar yutug\'i!'}
            elif roll < 0.85:
                # Role or Hero Shield
                role_code = random.choice(['role_doctor', 'role_don', 'role_komissar', 'role_qotil', 'geroy_himoya'])
                role_names = {
                    'role_doctor': '👨🏼‍⚕️ Shifokor Roli',
                    'role_don': '🤵🏻 Don Roli',
                    'role_komissar': '🕵🏻‍♂️ Komissar Roli',
                    'role_qotil': '🔪 Qotil Roli',
                    'geroy_himoya': '🔰 Geroydan Himoya (x2)'
                }
                cat, _ = MarketplaceCategory.objects.get_or_create(code='special', defaults={'name': 'Maxsus'})
                item, _ = MarketplaceItem.objects.get_or_create(code=role_code, defaults={'name': role_names[role_code], 'category': cat, 'item_type': MarketplaceItemType.ROLE})
                inv, _ = Inventory.objects.get_or_create(telegram_id=telegram_id, item=item, defaults={'quantity': 0, 'is_active': True})
                qty = 2 if role_code == 'geroy_himoya' else 1
                inv.quantity += qty
                inv.save(update_fields=['quantity'])
                prize = {'type': 'ROLE', 'title': role_names[role_code], 'icon': '🎭', 'desc': 'Noyob rol / himoya hisobingizga qo\'shildi!'}
            else:
                # VIP 7 kun
                now = timezone.now()
                vip, created = VIPSubscription.objects.get_or_create(telegram_id=telegram_id, defaults={'vip_level': VIPLevel.GOLD, 'starts_at': now, 'expires_at': now + timedelta(days=7), 'is_active': True})
                if not created:
                    vip.expires_at = max(vip.expires_at, now) + timedelta(days=7)
                    vip.is_active = True
                    vip.save(update_fields=['expires_at', 'is_active'])
                prize = {'type': 'VIP', 'title': '⭐️ VIP Obuna (7 kun)', 'icon': '⭐️', 'desc': '7 kunlik VIP status aktivlashtirildi!'}

            new_money = max(wallet.coins, int(wallet.money))
            return {
                'ok': True,
                'chest_type': 2,
                'prize': prize,
                'new_money': f"{new_money:,}".replace(",", " "),
                'new_diamonds': wallet.diamonds,
                'message': f"🎁 Sandiqdan chiqdi: {prize['title']}!"
            }

        # -------------------------------------------------------------
        # CHEST 3: 20 💎 (AFSONAVIY SANDIQ)
        # -------------------------------------------------------------
        elif chest_type == 3:
            cost = 20
            if not is_owner and wallet.diamonds < cost:
                return {'ok': False, 'error': f"3-Sandiqni ochish uchun 20 💎 olmos yetarli emas!"}

            if not is_owner:
                wallet.diamonds -= cost
                wallet.save(update_fields=['diamonds'])

            roll = random.random()

            if roll < 0.03:
                # 🌟 Rare Lucky Jackpot: GEROY (3% chance)
                hero = HeroService.get_hero(telegram_id)
                owner_name = profile.full_name or profile.first_name if profile else "O'yinchi"
                if not hero:
                    _, _, hero = HeroService.create_hero(telegram_id, name="Afsonaviy Geroy", owner_name=owner_name, price_diamonds=0)
                    prize = {
                        'type': 'HERO',
                        'title': '🥷 AFSONAVIY GEROY!',
                        'icon': '🥷',
                        'desc': 'Omadli jekpot! Sizga shaxsiy GEROY berildi! 🎉'
                    }
                else:
                    hero.charges += 15
                    hero.add_kill_score(200)
                    prize = {
                        'type': 'HERO_UPGRADE',
                        'title': '🥷 GEROY ZARYADI!',
                        'icon': '⚡️',
                        'desc': f'Geroyingizga +15 zaryad va +200 ball qo\'shildi! (Jami: {hero.charges} zaryad)'
                    }
            elif roll < 0.38:
                # 12 - 18 💎 (partial diamond return)
                win_d = random.randint(12, 18)
                wallet.diamonds += win_d
                wallet.save(update_fields=['diamonds'])
                prize = {'type': 'DIAMONDS', 'title': f"{win_d} 💎 Olmos", 'icon': '💎', 'desc': 'Olmoslar keshbeki!'}
            elif roll < 0.63:
                # 200k - 450k $
                win_m = random.choice([200000, 300000, 450000])
                wallet.coins += win_m
                wallet.money += Decimal(str(win_m))
                wallet.save(update_fields=['coins', 'money'])
                prize = {'type': 'MONEY', 'title': f"{win_m:,} 💶 Dollar".replace(",", " "), 'icon': '💰', 'desc': 'Katta dollar mukofoti!'}
            elif roll < 0.78:
                # 25 - 40 💎 (profit)
                win_d = random.choice([25, 30, 40])
                wallet.diamonds += win_d
                wallet.save(update_fields=['diamonds'])
                prize = {'type': 'DIAMONDS', 'title': f"{win_d} 💎 Olmos", 'icon': '💎', 'desc': 'Yutuqli olmoslar!'}
            elif roll < 0.90:
                # 2x Geroydan Himoya
                cat, _ = MarketplaceCategory.objects.get_or_create(code='items', defaults={'name': 'Himoyalar'})
                item, _ = MarketplaceItem.objects.get_or_create(code='geroy_himoya', defaults={'name': '🔰 Geroydan Himoya', 'category': cat, 'item_type': MarketplaceItemType.BONUS})
                inv, _ = Inventory.objects.get_or_create(telegram_id=telegram_id, item=item, defaults={'quantity': 0, 'is_active': True})
                inv.quantity += 2
                inv.save(update_fields=['quantity'])
                prize = {'type': 'ITEM', 'title': '🔰 2x Geroydan Himoya', 'icon': '🔰', 'desc': '2 dona Geroydan himoya inventaringizga qo\'shildi!'}
            else:
                # VIP 7 - 15 kun
                now = timezone.now()
                vip, created = VIPSubscription.objects.get_or_create(telegram_id=telegram_id, defaults={'vip_level': VIPLevel.GOLD, 'starts_at': now, 'expires_at': now + timedelta(days=7), 'is_active': True})
                if not created:
                    vip.expires_at = max(vip.expires_at, now) + timedelta(days=7)
                    vip.is_active = True
                    vip.save(update_fields=['expires_at', 'is_active'])
                prize = {'type': 'VIP', 'title': '⭐️ VIP Obuna (7 kun)', 'icon': '👑', 'desc': 'VIP a\'zolik aktivlashtirildi!'}

            new_money = max(wallet.coins, int(wallet.money))
            return {
                'ok': True,
                'chest_type': 3,
                'prize': prize,
                'new_money': f"{new_money:,}".replace(",", " "),
                'new_diamonds': wallet.diamonds,
                'message': f"🎁 Sandiqdan chiqdi: {prize['title']}!"
            }

        return {'ok': False, 'error': "Noma'lum sandiq turi"}

    @classmethod
    def get_casino_state(cls, telegram_id: int) -> dict:
        """Returns player's casino state and wallet."""
        wallet = EconomyService.get_or_create_wallet(telegram_id=telegram_id)
        cur_money = max(wallet.coins, int(wallet.money))
        return {
            'ok': True,
            'money': f"{cur_money:,}".replace(",", " "),
            'diamonds': wallet.diamonds,
        }


