from __future__ import annotations

from django.conf import settings
from django.contrib.auth import logout
from django.utils import timezone

from .models import UserActivityLog


class UserActivityLoggingMiddleware:
    """
    인증된 사용자의 요청 중요 정보를 UserActivityLog에 저장한다.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        self._log_request(request)
        return response

    def _log_request(self, request):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return

        path = request.path
        if path.startswith("/static") or path.startswith("/.well-known") or path == "/favicon.ico":
            return

        user_agent = request.META.get("HTTP_USER_AGENT", "")[:512]
        ip_addr = request.META.get("HTTP_X_FORWARDED_FOR") or request.META.get("REMOTE_ADDR")
        if ip_addr and "," in ip_addr:
            ip_addr = ip_addr.split(",")[0].strip()

        UserActivityLog.objects.create(
            user=user,
            path=path,
            method=request.method,
            user_agent=user_agent,
            ip_address=ip_addr,
            created_at=timezone.now(),
        )


class SessionTimeoutMiddleware:
    """
    Keep sessions alive while the user is active, but force logout after long idle time.
    - Every authenticated request bumps the expiry window by SESSION_REFRESH_SECONDS (default: 1 hour)
    - If the user has been idle for SESSION_MAX_IDLE_SECONDS (default: 3 hours), log them out
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.refresh_seconds = getattr(settings, "SESSION_REFRESH_SECONDS", 60 * 60)
        self.max_idle_seconds = getattr(settings, "SESSION_MAX_IDLE_SECONDS", 3 * 60 * 60)

    def __call__(self, request):
        if request.user.is_authenticated:
            now_ts = timezone.now().timestamp()
            last_activity = request.session.get("last_activity")

            if last_activity:
                idle_seconds = now_ts - last_activity
                if idle_seconds >= self.max_idle_seconds:
                    logout(request)
                else:
                    request.session["last_activity"] = now_ts
                    request.session.set_expiry(self.refresh_seconds)
            else:
                # First authenticated request in this session
                request.session["last_activity"] = now_ts
                request.session.set_expiry(self.refresh_seconds)

        response = self.get_response(request)
        return response
