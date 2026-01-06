from django.contrib import admin
from .models import Organization, OrganizationMember, OrganizationInvitation


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('organization_sid', 'organization_name', 'created_by_user_id', 'created_at', 'member_count')
    list_filter = ('created_at',)
    search_fields = ('organization_name', 'created_by_user_id')
    readonly_fields = ('organization_sid', 'created_at', 'updated_at')

    def member_count(self, obj):
        return obj.member_count
    member_count.short_description = '멤버 수'


@admin.register(OrganizationMember)
class OrganizationMemberAdmin(admin.ModelAdmin):
    list_display = ('organization', 'user_id', 'role', 'joined_at')
    list_filter = ('role', 'joined_at')
    search_fields = ('organization__organization_name', 'user_id')
    readonly_fields = ('joined_at',)


@admin.register(OrganizationInvitation)
class OrganizationInvitationAdmin(admin.ModelAdmin):
    list_display = ('organization', 'email', 'status', 'invited_by_user_id', 'invited_at', 'expires_at')
    list_filter = ('status', 'invited_at')
    search_fields = ('organization__organization_name', 'email', 'invited_by_user_id')
    readonly_fields = ('id', 'invited_at', 'accepted_at')
