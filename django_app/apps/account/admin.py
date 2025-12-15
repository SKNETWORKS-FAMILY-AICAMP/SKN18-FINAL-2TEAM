from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import CustomUser, UserSettings, LinkedAccount


class UserSettingsInline(admin.StackedInline):
    """사용자 설정 인라인"""
    model = UserSettings
    can_delete = False
    verbose_name = '사용자 설정'
    verbose_name_plural = '사용자 설정'


class LinkedAccountInline(admin.TabularInline):
    """연동 계정 인라인"""
    model = LinkedAccount
    extra = 0
    readonly_fields = ('provider', 'provider_user_id', 'created_at', 'updated_at')
    can_delete = True
    verbose_name = '연동 계정'
    verbose_name_plural = '연동 계정'


@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    """사용자 관리자 설정"""
    
    list_display = (
        'email', 'full_name', 'company', 'status', 
        'is_staff', 'is_active', 'join_date'
    )
    list_filter = ('status', 'is_staff', 'is_active', 'join_date')
    search_fields = ('email', 'full_name', 'company', 'phone_number')
    ordering = ('-created_at',)
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('프로필 정보', {'fields': ('full_name', 'phone_number', 'company', 'img_url')}),
        ('상태', {'fields': ('status', 'is_active', 'is_staff', 'is_superuser')}),
        ('권한', {'fields': ('groups', 'user_permissions')}),
        ('일시', {'fields': ('join_date', 'last_login', 'created_at', 'updated_at')}),
    )
    readonly_fields = ('user_id', 'join_date', 'last_login', 'created_at', 'updated_at')
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'full_name', 'company'),
        }),
    )
    
    inlines = [UserSettingsInline, LinkedAccountInline]


@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    """사용자 설정 관리자"""
    
    list_display = ('user', 'notifications', 'email_alerts', 'dark_mode', 'language', 'updated_at')
    list_filter = ('notifications', 'email_alerts', 'dark_mode', 'language')
    search_fields = ('user__email', 'user__full_name')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(LinkedAccount)
class LinkedAccountAdmin(admin.ModelAdmin):
    """연동 계정 관리자"""
    
    list_display = ('user', 'provider', 'provider_user_id', 'token_expires_at', 'created_at')
    list_filter = ('provider', 'created_at')
    search_fields = ('user__email', 'provider_user_id')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (None, {'fields': ('user', 'provider', 'provider_user_id')}),
        ('토큰 정보', {'fields': ('access_token', 'refresh_token', 'token_expires_at')}),
        ('일시', {'fields': ('created_at', 'updated_at')}),
    )
