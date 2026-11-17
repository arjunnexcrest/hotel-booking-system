from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('action', 'entity_type', 'entity_id', 'actor', 'actor_type', 'hotel', 'created_at')
    list_filter = ('action', 'actor_type', 'entity_type', 'created_at')
    search_fields = ('entity_id', 'reason', 'actor__username', 'ip_address')
    readonly_fields = (
        'actor',
        'actor_type',
        'hotel',
        'action',
        'entity_type',
        'entity_id',
        'old_values',
        'new_values',
        'reason',
        'ip_address',
        'user_agent',
        'request_id',
        'created_at',
        'updated_at',
    )
