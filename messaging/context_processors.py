from .models import Message, Notification


def unread_messages(request):
    """Unread incoming messages for the navbar badge."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {
            'unread_message_count': 0,
            'unread_notification_count': 0,
        }

    unread_message_count = Message.objects.filter(
        conversation__participants=user,
        is_read=False,
    ).exclude(sender=user).count()
    unread_notification_count = Notification.objects.filter(
        recipient=user,
        is_read=False,
    ).count()
    return {
        'unread_message_count': unread_message_count,
        'unread_notification_count': unread_notification_count,
    }
