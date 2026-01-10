from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """알림 관리자 페이지 설정"""
    list_display = ('notification_sid', 'user_id', 'title', 'notification_type', 'read_yn', 'created_at')
    list_filter = ('notification_type', 'read_yn', 'created_at')
    search_fields = ('user_id', 'title', 'message')
    readonly_fields = ('notification_sid', 'created_at')
    ordering = ('-created_at',)
    
    fieldsets = (
        ('기본 정보', {
            'fields': ('notification_sid', 'user_id', 'notification_type', 'title', 'message')
        }),
        ('상태', {
            'fields': ('read_yn', 'related_sid')
        }),
        ('타임스탬프', {
            'fields': ('created_at',)
        }),
    )
