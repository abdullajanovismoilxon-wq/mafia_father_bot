from django.urls import path
from . import views

urlpatterns = [
    path('profile/', views.profile_webapp_view, name='webapp_profile'),
    path('roles/', views.roles_webapp_view, name='webapp_roles'),
    path('api/get-profile/', views.get_profile_api, name='webapp_get_profile'),
    path('api/get-notifications/', views.get_notifications_api, name='webapp_get_notifications'),
    path('api/toggle-item/', views.toggle_inventory_item_api, name='webapp_toggle_item'),
    path('api/buy-item/', views.buy_inventory_item_api, name='webapp_buy_item'),
    path('api/transfer-funds/', views.transfer_funds_api, name='webapp_transfer_funds'),
    
    # Group Cabinet APIs
    path('api/groups/list/', views.get_user_groups_api, name='webapp_groups_list'),
    path('api/group/login/', views.group_cabinet_login_api, name='webapp_group_login'),
    path('api/group/dashboard/', views.group_cabinet_dashboard_api, name='webapp_group_dashboard'),
    path('api/group/settings/save/', views.group_cabinet_save_settings_api, name='webapp_group_save_settings'),
    # Hero APIs
    path('api/hero/info/', views.hero_info_api, name='webapp_hero_info'),
    path('api/hero/details/', views.hero_info_api, name='webapp_hero_details'),
    path('api/hero/recharge/', views.hero_recharge_api, name='webapp_hero_recharge'),
    path('api/hero/rename/', views.hero_rename_api, name='webapp_hero_rename'),
    path('api/hero/transfer/', views.hero_transfer_api, name='webapp_hero_transfer'),
    path('api/hero/create/', views.hero_create_api, name='webapp_hero_create'),
    path('api/hero/toggle/', views.hero_toggle_api, name='webapp_hero_toggle'),
    path('api/shop/buy/', views.buy_inventory_item_api, name='webapp_shop_buy'),
    # Casino APIs
    path('api/casino/roulette/spin/', views.casino_roulette_spin_api, name='webapp_casino_roulette_spin'),
    path('api/casino/chest/open/', views.casino_chest_open_api, name='webapp_casino_chest_open'),
    path('api/casino/state/', views.casino_state_api, name='webapp_casino_state'),
]
