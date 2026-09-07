from decimal import Decimal
from rest_framework import permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from apps.economy.models import (
    Wallet, WalletTransaction, CurrencyType, MarketplaceItem,
    MarketplaceCategory, Purchase, Inventory, PaymentOrder
)
from apps.economy.services import EconomyService, MarketplaceService, InsufficientBalanceError
from django.contrib.auth import get_user_model

User = get_user_model()


class MyWalletView(APIView):
    """Retrieve the authenticated user's wallet balances and currency rates."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        wallet = EconomyService.get_or_create_wallet(user=request.user)
        uzs_rate = EconomyService.get_usd_to_uzs_rate()
        money_uzs = (wallet.money * uzs_rate).quantize(Decimal('0.01'))

        return Response({
            'wallet_id': str(wallet.id),
            'money_usd': str(wallet.money),
            'money_uzs': str(money_uzs),
            'diamonds': wallet.diamonds,
            'coins': wallet.coins,
            'usd_to_uzs_rate': str(uzs_rate),
        })


class MyTransactionsView(APIView):
    """Retrieve the authenticated user's immutable wallet transaction history."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        wallet = EconomyService.get_or_create_wallet(user=request.user)
        txs = WalletTransaction.objects.filter(wallet=wallet).order_by('-created_at')[:50]

        results = []
        for tx in txs:
            results.append({
                'id': str(tx.id),
                'tx_type': tx.tx_type,
                'currency': tx.currency,
                'amount': str(tx.amount),
                'balance_after': str(tx.balance_after),
                'description': tx.description,
                'reference_id': tx.reference_id,
                'created_at': tx.created_at.isoformat(),
            })
        return Response(results)


class TransferFundsView(APIView):
    """Transfer money or diamonds to another user via email or telegram_id."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        recipient_email = request.data.get('recipient_email')
        recipient_telegram_id = request.data.get('recipient_telegram_id')
        currency = request.data.get('currency', CurrencyType.DIAMONDS)
        amount = request.data.get('amount')
        description = request.data.get('description', '')

        if not amount:
            return Response({'detail': 'Amount is required.'}, status=status.HTTP_400_BAD_REQUEST)

        sender_wallet = EconomyService.get_or_create_wallet(user=request.user)
        recipient_wallet = None

        if recipient_email:
            try:
                rec_user = User.objects.get(email=recipient_email)
                recipient_wallet = EconomyService.get_or_create_wallet(user=rec_user)
            except User.DoesNotExist:
                return Response({'detail': f'User with email {recipient_email} not found.'}, status=status.HTTP_404_NOT_FOUND)
        elif recipient_telegram_id:
            recipient_wallet = EconomyService.get_or_create_wallet(telegram_id=int(recipient_telegram_id))
        else:
            return Response({'detail': 'Must provide recipient_email or recipient_telegram_id.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if currency == CurrencyType.MONEY:
                debit_tx, credit_tx = EconomyService.transfer_money(
                    sender_wallet=sender_wallet,
                    recipient_wallet=recipient_wallet,
                    amount=Decimal(str(amount)),
                    description=description
                )
            elif currency == CurrencyType.DIAMONDS:
                debit_tx, credit_tx = EconomyService.transfer_diamonds(
                    sender_wallet=sender_wallet,
                    recipient_wallet=recipient_wallet,
                    amount=int(amount),
                    description=description
                )
            else:
                return Response({'detail': 'Invalid currency for transfer.'}, status=status.HTTP_400_BAD_REQUEST)

            return Response({
                'status': 'success',
                'tx_id': str(debit_tx.id),
                'amount': str(amount),
                'currency': currency,
                'new_balance': str(debit_tx.balance_after)
            }, status=status.HTTP_200_OK)

        except InsufficientBalanceError as e:
            return Response({'code': 'INSUFFICIENT_BALANCE', 'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class MarketplaceCatalogView(APIView):
    """Retrieve all available marketplace items and packages."""
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        MarketplaceService.get_or_create_default_categories_and_items()
        categories = MarketplaceCategory.objects.filter(is_active=True).prefetch_related('items')
        uzs_rate = EconomyService.get_usd_to_uzs_rate()

        results = []
        for cat in categories:
            items_data = []
            for it in cat.items.filter(is_active=True):
                price_uzs = (it.price_money_usd * uzs_rate).quantize(Decimal('0.01'))
                items_data.append({
                    'id': str(it.id),
                    'code': it.code,
                    'name': it.name,
                    'description': it.description,
                    'icon': it.icon,
                    'item_type': it.item_type,
                    'price_diamonds': it.price_diamonds,
                    'price_money_usd': str(it.price_money_usd),
                    'price_money_uzs': str(price_uzs),
                    'diamond_amount': it.diamond_amount,
                    'vip_days': it.vip_days,
                })
            results.append({
                'category_name': cat.name,
                'category_code': cat.code,
                'icon': cat.icon,
                'items': items_data
            })
        return Response(results)


class PurchaseItemView(APIView):
    """Purchase a marketplace item using user wallet balance."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        item_code = request.data.get('item_code')
        currency = request.data.get('currency', CurrencyType.DIAMONDS)

        if not item_code:
            return Response({'detail': 'item_code is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            purchase = MarketplaceService.purchase_item(
                item_code=item_code,
                user=request.user,
                currency=currency
            )
            return Response({
                'status': 'purchased',
                'purchase_id': str(purchase.id),
                'item_name': purchase.item.name,
                'amount_paid': str(purchase.amount_paid),
                'currency': purchase.currency_paid,
            }, status=status.HTTP_200_OK)
        except InsufficientBalanceError as e:
            return Response({'code': 'INSUFFICIENT_BALANCE', 'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class CreatePaymentOrderView(APIView):
    """Create a manual P2P payment order to buy diamonds."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        diamonds = request.data.get('diamonds')
        payment_method = request.data.get('payment_method', 'P2P_CARD')

        if not diamonds:
            return Response({'detail': 'diamonds is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            order = MarketplaceService.create_payment_order(
                diamonds=int(diamonds),
                payment_method=payment_method,
                user=request.user
            )
            return Response({
                'order_id': order.order_id,
                'amount_usd': str(order.amount_usd),
                'amount_uzs': str(order.amount_uzs),
                'diamonds': order.diamonds_to_credit,
                'payment_method': order.payment_method,
                'status': order.status,
                'payment_instructions': "To'lovni amalga oshirib, chek rasmini yoki tranzaksiya ID sini taqdim eting."
            }, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
