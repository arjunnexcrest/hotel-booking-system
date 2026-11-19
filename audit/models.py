from django.db import models
from django.conf import settings
from core.models import TimeStampedModel


class AuditLog(TimeStampedModel):
    """
    Centralized audit logging for administrative actions, hotel approvals,
    status overrides, and security events.
    """
    class ActorType(models.TextChoices):
        USER = 'USER', 'User'
        SYSTEM = 'SYSTEM', 'System Automated'
        AI_SERVICE = 'AI_SERVICE', 'AI Monitoring Service'

    class Action(models.TextChoices):
        CREATE = 'CREATE', 'Created'
        UPDATE = 'UPDATE', 'Updated'
        DELETE = 'DELETE', 'Deleted'
        STATUS_CHANGE = 'STATUS_CHANGE', 'Status Change'
        MANUAL_OVERRIDE = 'MANUAL_OVERRIDE', 'Manual Override'
        APPROVE = 'APPROVE', 'Approved'
        REJECT = 'REJECT', 'Rejected'
        LOGIN = 'LOGIN', 'User Login'
        LOGOUT = 'LOGOUT', 'User Logout'

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    actor_type = models.CharField(
        max_length=30,
        choices=ActorType.choices,
        default=ActorType.USER,
    )
    hotel = models.ForeignKey(
        'hotels.Hotel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    action = models.CharField(max_length=50, choices=Action.choices)
    entity_type = models.CharField(max_length=100)
    entity_id = models.CharField(max_length=100)
    old_values = models.JSONField(default=dict, blank=True)
    new_values = models.JSONField(default=dict, blank=True)
    reason = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    request_id = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = 'audit_logs'
        indexes = [
            models.Index(fields=['entity_type', 'entity_id']),
            models.Index(fields=['hotel', 'action']),
            models.Index(fields=['actor', 'created_at']),
        ]

    def __str__(self):
        return f"[{self.action}] {self.entity_type} #{self.entity_id} by {self.actor or self.actor_type}"
