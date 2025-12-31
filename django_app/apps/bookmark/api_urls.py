from django.urls import path

from . import views

app_name = "bookmark_api"

urlpatterns = [
    path("", views.bookmark_list_api, name="bookmark_list"),
    path("categories/", views.bookmark_category_create_api, name="bookmark_category_create"),
    path("categories/<int:category_sid>/", views.bookmark_category_delete_api, name="bookmark_category_delete"),
    path("bookmarks/", views.bookmark_create_api, name="bookmark_create"),
    path("bookmarks/<int:bookmark_sid>/", views.bookmark_delete_api, name="bookmark_delete"),
]
