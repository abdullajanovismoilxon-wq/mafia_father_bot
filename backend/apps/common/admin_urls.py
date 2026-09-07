from django.urls import path
from apps.common.views.admin_views import (
    AdminOverviewView, AdminBotViewSet, AdminGameViewSet,
    AdminUserViewSet, AdminPaymentOrderViewSet, AdminMarketplaceViewSet,
    AdminAuditLogViewSet
)

urlpatterns = [
    path('overview/', AdminOverviewView.as_view(), name='admin_overview'),
    path('bots/', AdminBotViewSet.as_view({'get': 'list'}), name='admin_bots_list'),
    path('bots/<uuid:pk>/suspend/', AdminBotViewSet.as_view({'post': 'suspend'}), name='admin_bot_suspend'),
    path('bots/<uuid:pk>/resume/', AdminBotViewSet.as_view({'post': 'resume'}), name='admin_bot_resume'),
    path('bots/<uuid:pk>/restart/', AdminBotViewSet.as_view({'post': 'restart'}), name='admin_bot_restart'),
    path('bots/<uuid:pk>/stop/', AdminBotViewSet.as_view({'post': 'stop'}), name='admin_bot_stop'),
    path('games/', AdminGameViewSet.as_view({'get': 'list'}), name='admin_games_list'),
    path('users/', AdminUserViewSet.as_view({'get': 'list'}), name='admin_users_list'),
    path('users/<uuid:pk>/suspend/', AdminUserViewSet.as_view({'post': 'suspend'}), name='admin_user_suspend'),
    path('users/<uuid:pk>/activate/', AdminUserViewSet.as_view({'post': 'activate'}), name='admin_user_activate'),
    path('users/<uuid:pk>/grant_vip/', AdminUserViewSet.as_view({'post': 'grant_vip'}), name='admin_user_grant_vip'),
    path('users/<uuid:pk>/adjust_balance/', AdminUserViewSet.as_view({'post': 'adjust_balance'}), name='admin_user_adjust_balance'),
    path('payment-orders/', AdminPaymentOrderViewSet.as_view({'get': 'list'}), name='admin_payment_orders_list'),
    path('payment-orders/<str:pk>/review/', AdminPaymentOrderViewSet.as_view({'post': 'review'}), name='admin_payment_order_review'),
    path('marketplace/', AdminMarketplaceViewSet.as_view({'get': 'list', 'post': 'create'}), name='admin_marketplace_list'),
    path('marketplace/<uuid:pk>/', AdminMarketplaceViewSet.as_view({'get': 'retrieve', 'patch': 'partial_update', 'delete': 'destroy'}), name='admin_marketplace_detail'),
    path('audit-logs/', AdminAuditLogViewSet.as_view({'get': 'list'}), name='admin_audit_logs_list'),
]
