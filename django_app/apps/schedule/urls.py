# schedule/urls.py
from django.urls import path
from . import views
from . import service

app_name = "schedule"

urlpatterns = [
    # 페이지
    path("", views.index, name="schedule"),

    # 기존 HelixOps 일정 API
    path("api/schedules/", views.schedule_list, name="schedule_list"),
    path("api/schedules/<int:schedule_id>/", views.schedule_detail, name="schedule_detail"),
    path("api/schedules/<int:schedule_id>/shared/", views.schedule_shared_users, name="schedule_shared_users"),

    # Google OAuth
    path("google/login/", service.google_login, name="google_login"),
    path("google/logout/", service.google_logout, name="google_logout"),
    path("google/oauth2/callback/", service.google_callback, name="google_callback"),

    # Google Calendar 연동 설정(캘린더 선택/색상)
    path("google/settings/", service.calendar_settings, name="calendar_settings"),

    # FullCalendar/프론트가 읽는 구글 이벤트
    path("api/google-events/", service.google_events_api, name="google_events_api"),

    # 이벤트 CRUD
    path("api/google-events/create/", service.google_event_create, name="google_event_create"),
    path("api/google-events/update/", service.google_event_update, name="google_event_update"),
    path("api/google-events/delete/", service.google_event_delete, name="google_event_delete"),

    # ✅ 구글 상태/캘린더 API
    path("api/google-calendar/status/", service.google_calendar_status, name="google_calendar_status"),
    path("api/google-calendar/calendars/", service.google_calendar_calendars_api, name="google_calendar_calendars_api"),
]
