from django.contrib.contenttypes.models import ContentType

from .models import Notification


def create_notification(
    *,
    recipient,
    notification_type,
    message,
    target_url,
    actor=None,
    target=None,
    dedupe_key,
):
    defaults = {
        'actor': actor,
        'notification_type': notification_type,
        'message': message,
        'target_url': target_url,
    }
    if target is not None:
        defaults['content_type'] = ContentType.objects.get_for_model(target)
        defaults['object_id'] = target.pk

    notification, created = Notification.objects.get_or_create(
        recipient=recipient,
        dedupe_key=dedupe_key,
        defaults=defaults,
    )
    return notification, created
