from django.urls import path
from apps.superadmin import views

app_name = 'superadmin'

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    path('bots/', views.bots_view, name='bots'),
    path('groups/', views.groups_view, name='groups'),
    path('groups/<uuid:group_id>/credentials/', views.group_credentials_save_view, name='group_credentials_save'),
    path('groups/<uuid:group_id>/delete/', views.group_delete_view, name='group_delete'),
    path('bots/<uuid:bot_id>/toggle/', views.bot_toggle_view, name='bot_toggle'),
    path('bots/<uuid:bot_id>/delete/', views.bot_delete_view, name='bot_delete'),
    path('bots/<uuid:bot_id>/config/', views.bot_config_save_view, name='bot_config_save'),
    path('bots/<uuid:bot_id>/timings/', views.bot_timing_save_view, name='bot_timing_save'),
    
    path('timings/', views.timings_view, name='timings'),
    path('prices/', views.prices_view, name='prices'),
    path('settings/<uuid:setting_id>/save/', views.setting_save_view, name='setting_save'),
    
    path('gifs/', views.gifs_view, name='gifs'),
    path('texts/', views.texts_view, name='texts'),
    path('texts/<uuid:text_id>/save/', views.text_save_view, name='text_save'),
    
    path('promocodes/', views.promocodes_view, name='promocodes'),
    path('promocodes/create/', views.promocode_create_view, name='promocode_create'),
    path('promocodes/<uuid:promo_id>/delete/', views.promocode_delete_view, name='promocode_delete'),
    
    path('live-games/', views.live_games_view, name='live_games'),
    path('live-games/<uuid:game_id>/force-end/', views.game_force_end_view, name='game_force_end'),
    
    path('leaderboard/', views.leaderboard_view, name='leaderboard'),
    path('leaderboard/<uuid:profile_id>/bonus/', views.give_bonus_view, name='give_bonus'),
    
    path('broadcasts/', views.broadcasts_view, name='broadcasts'),
    path('broadcasts/create/', views.broadcast_create_view, name='broadcast_create'),
    path('broadcasts/<uuid:broadcast_id>/delete/', views.broadcast_delete_view, name='broadcast_delete'),
    path('broadcasts/clear-all/', views.broadcast_clear_all_view, name='broadcast_clear_all'),
    path('feedback/', views.feedback_list_view, name='feedback_list'),
    path('feedback/<uuid:feedback_id>/reply/', views.feedback_reply_view, name='feedback_reply'),
    
    path('users/', views.users_view, name='users'),
    path('users/<uuid:profile_id>/edit-balance/', views.user_balance_edit_view, name='user_balance_edit'),
    path('users/<uuid:profile_id>/reset/', views.user_reset_stats_view, name='user_reset'),
    path('users/<uuid:profile_id>/delete/', views.user_delete_view, name='user_delete'),
    
    path('roles/', views.roles_view, name='roles'),
    path('roles/<uuid:role_id>/save/', views.role_save_view, name='role_save'),
    path('roles/<uuid:role_id>/toggle/', views.role_toggle_view, name='role_toggle'),

    path('audit/', views.audit_view, name='audit'),
    path('audit/clear/', views.audit_clear_view, name='audit_clear'),
]
