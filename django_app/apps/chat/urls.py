from django.urls import path
from . import views

app_name = "chat"
urlpatterns = [
    path("", views.index, name="chat"),
    path("api/recommended-questions/", views.recommended_questions, name="recommended_questions"),
    path("api/chats/", views.chat_list, name="chat_list"),
    path("api/chats/<int:chat_id>/", views.chat_detail, name="chat_detail"),
    path("api/graph-summary/", views.graph_summary, name="graph_summary"),
    path("api/messages/<int:message_id>/feedback/", views.message_feedback, name="message_feedback"),
    # 주석처리: message_concept_graph는 graph_summary와 중복 기능이며 사용되지 않아 주석처리함
    # path("api/messages/<int:message_id>/concept-graph/", views.message_concept_graph, name="message_concept_graph"),
]
