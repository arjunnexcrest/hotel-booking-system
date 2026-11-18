from audit.models import AuditLog


def log_audit_event(
    action,
    entity_type,
    entity_id,
    actor=None,
    actor_type='USER',
    hotel=None,
    old_values=None,
    new_values=None,
    reason='',
    request=None
):
    """
    Central helper function to create audit log entries.
    """
    ip_address = None
    user_agent = ''

    if request:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0].strip()
        else:
            ip_address = request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:255]

    return AuditLog.objects.create(
        actor=actor,
        actor_type=actor_type,
        hotel=hotel,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        old_values=old_values or {},
        new_values=new_values or {},
        reason=reason,
        ip_address=ip_address,
        user_agent=user_agent,
    )
