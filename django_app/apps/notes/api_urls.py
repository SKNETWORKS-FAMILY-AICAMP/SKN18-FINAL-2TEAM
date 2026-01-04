from django.urls import path
from . import views

app_name = "notes_api"

urlpatterns = [
    path("", views.notes_list_api, name="api_notes_list"),
    path("create/", views.note_create_api, name="api_note_create"),
    path("<int:note_id>/", views.note_detail_api, name="api_note_detail"),
    path("<int:note_id>/update/", views.note_update_api, name="api_note_update"),
    path("<int:note_id>/delete/", views.note_delete_api, name="api_note_delete"),
    # 댓글 API
    path("<int:note_id>/comments/", views.comment_create_api, name="api_comment_create"),
    path("<int:note_id>/comments/<int:comment_id>/", views.comment_update_api, name="api_comment_update"),
    path("<int:note_id>/comments/<int:comment_id>/delete/", views.comment_delete_api, name="api_comment_delete"),
    # 공유 API
    path("<int:note_id>/share/", views.note_share_api, name="api_note_share"),
]
