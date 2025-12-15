from django.urls import path
from . import views

app_name = "notes"

urlpatterns = [
    path("", views.index, name="notes"),
    path("detail/", views.note_detail, name="note_detail"),
    path("editor/", views.note_editor, name="note_editor"),
]
