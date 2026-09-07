from django.urls import path
from apps.economy.views import (
    MyWalletView, MyTransactionsView, TransferFundsView,
    MarketplaceCatalogView, PurchaseItemView, CreatePaymentOrderView
)

urlpatterns = [
    path('wallet/', MyWalletView.as_view(), name='my_wallet'),
    path('transactions/', MyTransactionsView.as_view(), name='my_transactions'),
    path('transfer/', TransferFundsView.as_view(), name='transfer_funds'),
    path('marketplace/', MarketplaceCatalogView.as_view(), name='marketplace_catalog'),
    path('purchase/', PurchaseItemView.as_view(), name='purchase_item'),
    path('payment-orders/', CreatePaymentOrderView.as_view(), name='create_payment_order'),
]
