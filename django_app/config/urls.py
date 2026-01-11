"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from pathlib import Path
from apps.account.views import index as root_index, settings_api
from apps.schedule import views as schedule_views
from apps.dashboard import views as dashboard_views
from apps.notification import views as notification_views
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)


def health_check(request):
    """
    ALB 헬스체크용 간단한 엔드포인트
    DB 연결 없이 빠르게 응답하여 헬스체크 성능 최적화
    """
    return JsonResponse({"status": "healthy", "service": "django-app"})


def google_site_verification(request):
    """
    Google Search Console 사이트 검증용 파일 서빙
    """
    # 프로젝트 루트 디렉토리 (BASE_DIR의 부모 디렉토리)
    project_root = Path(settings.BASE_DIR).parent
    verification_file = project_root / "google52edda1c03988302.html"
    
    try:
        with open(verification_file, 'r', encoding='utf-8') as f:
            content = f.read()
        return HttpResponse(content, content_type='text/html')
    except FileNotFoundError:
        # 파일이 없으면 기본 검증 텍스트 반환
        return HttpResponse(
            "google-site-verification: google52edda1c03988302.html",
            content_type='text/plain'
        )


urlpatterns = [
    # 헬스체크 엔드포인트 (ALB용, 인증 불필요)
    path("health", health_check, name="health"),
    
    # Google 사이트 검증 파일 (인증 불필요)
    path("google52edda1c03988302.html", google_site_verification, name="google_site_verification"),
    
    # 루트 URL - 인증 상태에 따라 리디렉트
    path("", root_index, name="root"),
    
    # 인증 (accounts namespace)
    path("accounts/", include("apps.account.urls")),
    
    # 앱 URL
    path("dashboard/", include("apps.dashboard.urls")),
    path("chat/", include("apps.chat.urls")),
    path("schedule/", include("apps.schedule.urls")),
    path("experiments/", include("apps.experiments.urls")),
    path("notes/", include("apps.notes.urls")),
    
    # API endpoints
    path("api/experiments/", include("apps.experiments.api_urls")),
    path("api/notes/", include("apps.notes.api_urls")),
    path("api/bookmarks/", include("apps.bookmark.api_urls")),
    path("api/feedback/", include("apps.feedback.api_urls")),
    path("api/profile/", include("apps.account.api_urls")),
    path("api/settings/", settings_api, name="api_settings"),
    path("api/notifications/", notification_views.notification_list_api, name="api_notification_list"),
    path("api/notifications/<int:notification_id>/read/", notification_views.notification_read_api, name="api_notification_read"),
    path("api/organization/", include("apps.organization.urls")),
    path("api/calendars/", schedule_views.user_calendars_api, name="user_calendars_api"),
    path("api/calendars/<int:calendar_id>/", schedule_views.user_calendar_detail, name="user_calendar_detail"),
    
    # Swagger/OpenAPI (인증 없이 접근 가능)
    path("api/schema/", csrf_exempt(SpectacularAPIView.as_view()), name="schema"),
    path("api/docs/", csrf_exempt(SpectacularSwaggerView.as_view(url_name="schema")), name="swagger-ui"),
    path("api/redoc/", csrf_exempt(SpectacularRedocView.as_view(url_name="schema")), name="redoc"),
    
    # 관리자
    path("admin/", admin.site.urls),
]

# WhiteNoise가 정적 파일을 자동으로 서빙하므로 별도 설정 불필요
