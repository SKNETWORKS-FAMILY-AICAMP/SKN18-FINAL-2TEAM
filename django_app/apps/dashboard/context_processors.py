"""
Context processors for dashboard app.
Provides header_user context to all templates.
"""
from django.contrib.auth.models import AnonymousUser
from .models import Notification


def header_user(request):
    """Return display information for the header profile section."""
    default_name = "사용자"
    default_email = "이메일"
    default_org = None
    default_avatar = (
        "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=100&h=100&fit=crop"
    )

    user = getattr(request, "user", AnonymousUser())
    
    # Anonymous user인 경우 기본값 반환
    if not user.is_authenticated:
        return {
            "name": default_name,
            "email": default_email,
            "organization": default_org,
            "avatar": default_avatar,
        }
    
    profile = getattr(user, "profile", None)

    # 이름 후보들
    name_candidates = []
    full_name_fn = getattr(user, "get_full_name", None)
    if callable(full_name_fn):
        full_name = full_name_fn()
        if full_name:
            name_candidates.append(full_name)
    
    username = getattr(user, "get_username", lambda: "")()
    if username:
        name_candidates.append(username)

    name = next((candidate for candidate in name_candidates if candidate), default_name)
    email = getattr(user, "email", "") or default_email
    
    # 프로필에서 organization 가져오기
    organization = None
    if profile:
        organization = getattr(profile, "organization", None)
    
    # 프로필에서 avatar 가져오기
    avatar = default_avatar
    if profile:
        avatar_obj = getattr(profile, "avatar", None)
        if avatar_obj:
            try:
                avatar = avatar_obj.url
            except (AttributeError, ValueError):
                avatar = default_avatar

    # 알림 정보 추가 (헤더에서 사용)
    unread_notifications_count = 0
    notifications = []
    if user.is_authenticated:
        user_id = getattr(user, 'user_id', None)
        if user_id:
            # 미읽음 알림 개수
            unread_notifications_count = Notification.objects.filter(
                user_id=user_id,
                read_yn='N'
            ).count()
            
            # 최근 알림 5건 (헤더 드롭다운용)
            recent_notifications = Notification.objects.filter(
                user_id=user_id
            ).order_by('-created_at')[:5]
            
            notifications = [
                {
                    "id": notif.notification_sid,
                    "title": notif.title,
                    "message": notif.message,
                    "time": notif.time,
                    "unread": notif.unread,
                }
                for notif in recent_notifications
            ]

    return {
        "name": name,
        "email": email,
        "organization": organization,
        "avatar": avatar,
        "unread_notifications_count": unread_notifications_count,
        "notifications": notifications,
    }
