from django.urls import re_path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import RegisterView, LogoutView, UserProfileView, CoAdminListCreateView, CoAdminDeleteView

urlpatterns = [
    re_path(r'^register/?$', RegisterView.as_view(), name='auth_register'),
    re_path(r'^login/?$', TokenObtainPairView.as_view(), name='auth_login'),
    re_path(r'^refresh/?$', TokenRefreshView.as_view(), name='auth_refresh'),
    re_path(r'^logout/?$', LogoutView.as_view(), name='auth_logout'),
    re_path(r'^me/?$', UserProfileView.as_view(), name='auth_me'),
    re_path(r'^co-admins/?$', CoAdminListCreateView.as_view(), name='co_admins_list_create'),
    re_path(r'^co-admins/(?P<pk>[^/]+)/?$', CoAdminDeleteView.as_view(), name='co_admins_delete'),
]
