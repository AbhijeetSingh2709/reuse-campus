from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q


class Conversation(models.Model):
    """A conversation thread between two users, optionally about a specific item."""
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL, related_name='conversations'
    )
    item = models.ForeignKey(
        'items.Item', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='conversations',
        help_text='The item this conversation is about (optional)'
    )
    board_request = models.ForeignKey(
        'board.BoardRequest', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='conversations',
        help_text='The Request Board post this conversation is about (optional)'
    )
    board_responder = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True,
        related_name='board_conversations_started',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        constraints = [
            models.UniqueConstraint(
                fields=['board_request', 'board_responder'],
                condition=Q(board_request__isnull=False, board_responder__isnull=False),
                name='unique_board_request_responder',
            ),
            models.CheckConstraint(
                check=Q(board_request__isnull=True) | Q(board_responder__isnull=False),
                name='board_conversation_has_responder',
            ),
        ]

    def __str__(self):
        usernames = ', '.join(u.username for u in self.participants.all())
        item_title = f' — {self.item.title}' if self.item else ''
        return f'Chat: {usernames}{item_title}'

    def get_other_user(self, user):
        """Return the other participant in a 2-person conversation."""
        return self.participants.exclude(pk=user.pk).first()

    def last_message(self):
        return self.messages.order_by('-created_at').first()


class Message(models.Model):
    """A single message within a conversation."""
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name='messages'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages'
    )
    body = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.sender.username}: {self.body[:40]}'


class Notification(models.Model):
    TYPE_CHOICES = [
        ('item_requested', 'Item requested'),
        ('item_approved', 'Item request approved'),
        ('item_rejected', 'Item request rejected'),
        ('board_response', 'Request Board response'),
        ('message', 'New message'),
        ('request_fulfilled', 'Request fulfilled'),
        ('transaction_status', 'Transaction status changed'),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='notifications_sent',
    )
    notification_type = models.CharField(max_length=32, choices=TYPE_CHOICES)
    message = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    target_url = models.CharField(max_length=500, blank=True)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    object_id = models.PositiveBigIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    dedupe_key = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(
                fields=['recipient', 'is_read', '-created_at'],
                name='notif_recipient_read_idx',
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['recipient', 'dedupe_key'],
                condition=Q(dedupe_key__isnull=False),
                name='unique_notification_event',
            ),
        ]

    def __str__(self):
        return f'{self.recipient.username}: {self.message}'
