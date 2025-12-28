from django.urls import path
from . import views

app_name = "notes_api"

urlpatterns = [
    path("", views.notes_list_api, name="api_notes_list"),
]
