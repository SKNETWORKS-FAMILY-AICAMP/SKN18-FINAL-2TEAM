from django.urls import path
from . import views

urlpatterns = [
    # 노트 상세 페이지
    path('<int:pk>/', views.note_detail, name='note_detail'),

    # 댓글 추가
    path('<int:pk>/comment/add/', views.add_comment, name='add_comment'),

    # 댓글 스레드 (하이라이트 클릭 시)
    path('comment/thread/<int:comment_id>/', views.comment_thread, name='comment_thread'),
]