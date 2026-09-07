from django.urls import re_path
from apps.stats.views import MyProfileView, LeaderboardView, GroupTop20PlayersView

urlpatterns = [
    re_path(r'^profile/?$', MyProfileView.as_view(), name='my_profile'),
    re_path(r'^leaderboard/?$', LeaderboardView.as_view(), name='leaderboard'),
    re_path(r'^group-top20/?$', GroupTop20PlayersView.as_view(), name='group_top20'),
]
