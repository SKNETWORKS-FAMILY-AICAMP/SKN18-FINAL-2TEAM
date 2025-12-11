# config/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from .views import db_test

urlpatterns = [
    path("admin/", admin.site.urls),

    # 연구 노트 기능
    path("labnote/", include("labnote.urls")),  

    # 기존 앱들
    path("accounts/", include("accounts.urls")), 
    path('ckeditor/', include('ckeditor_uploader.urls')),  # 업로더 필요시 
    # path("notes/", include("notes.urls")),  
    # path("attachments/", include("attachments.urls")),  
    # path("bookmarks/", include("bookmarks.urls")),
    # path("folders/", include("folders.urls")),

    # 테스트
    path("db-test/", db_test),
]

# 개발환경에서 media 파일 접근
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)