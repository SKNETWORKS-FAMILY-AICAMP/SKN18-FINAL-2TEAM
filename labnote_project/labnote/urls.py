from django.urls import path
from . import views

app_name = "labnote"

urlpatterns = [
    path("", views.research_note_list, name="note_list"),
    path("create/", views.research_note_create, name="note_create"),
    path('<int:note_id>/', views.note_detail, name='note_detail'),
    path("<int:note_id>/edit/", views.research_note_update, name="note_update"),
]