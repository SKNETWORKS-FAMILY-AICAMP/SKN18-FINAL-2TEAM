from django.urls import path
from . import views

app_name = "chat"
urlpatterns = [
    path("", views.index, name="chat"),
    path("api/recommended-questions/", views.recommended_questions, name="recommended_questions"),
    path("api/chats/", views.chat_list, name="chat_list"),
    path("api/chats/<int:chat_id>/", views.chat_detail, name="chat_detail"),
    path("api/chats/<int:chat_id>/messages/", views.chat_messages, name="chat_messages"),
    path("api/chats/messages/", views.chat_messages, name="chat_messages_create"),  # 새 채팅 생성
    path("api/graph-summary/", views.graph_summary, name="graph_summary"),
    path("api/messages/<int:message_id>/feedback/", views.message_feedback, name="message_feedback"),
    path("api/chats/<int:chat_id>/favorite/", views.toggle_favorite, name="toggle_favorite"),
    path("api/chats/<int:chat_id>/archive/", views.toggle_archive, name="toggle_archive"),
    path("api/chats/<int:chat_id>/delete/", views.delete_chat, name="delete_chat"),
    # 같은 목적: message_concept_graph는 graph_summary와 ChatMessage.concept_graph 생성/조회하는 중복 가능이며 사용되지 않아 삭제함

]
