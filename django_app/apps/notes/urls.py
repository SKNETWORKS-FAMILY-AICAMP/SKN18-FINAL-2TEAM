from django.urls import path
from . import views

app_name = "notes"

urlpatterns = [
    path("", views.index, name="notes"),
    path("api/list/", views.api_notes_list, name="api_notes_list"),
    path("api/create/", views.api_note_create, name="api_note_create"),
    path("api/detail/", views.api_note_detail, name="api_note_detail"),
    path("api/comments/", views.api_note_comments, name="api_note_comments"),
    path("api/add_comment/", views.api_note_add_comment, name="api_note_add_comment"),
    path("detail/", views.note_detail, name="note_detail"),
    path("editor/", views.note_editor, name="note_editor"),
]
