from django.urls import path
from . import views

app_name = "account_api"

urlpatterns = [
    # /api/profile/ -> apps.account.views.profile_api
    path("", views.profile_api, name="api_profile"),
    # /api/profile/avatar/ -> apps.account.views.profile_avatar_api
    path("avatar/", views.profile_avatar_api, name="api_profile_avatar"),
    # /api/profile/linked-accounts/ -> apps.account.views.linked_accounts_api
    path("linked-accounts/", views.linked_accounts_api, name="api_linked_accounts"),
]

