from django.contrib import admin
from apps.superadmin.models import BotSystemText, AuditLog


@admin.register(BotSystemText)
class BotSystemTextAdmin(admin.ModelAdmin):
    list_display = ('title', 'key', 'category', 'is_active', 'updated_at')
    list_filter = ('category', 'is_active')
    search_fields = ('key', 'title', 'content_uz', 'content_ru', 'content_en')
    list_editable = ('is_active',)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'action', 'actor', 'target', 'ip_address')
    list_filter = ('action',)
    search_fields = ('action', 'actor', 'target', 'details')
    readonly_fields = ('action', 'actor', 'target', 'details', 'ip_address', 'created_at')
