from django.http import Http404, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages as django_messages
from django.db import transaction
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from .models import Conversation, Notification
from .forms import MessageForm
from users.models import User
from items.models import Item
from transactions.models import BuyRequest, RentRequest
from board.models import BoardRequest
from .services import create_notification


def _conversation_list_for(user):
    conversations = Conversation.objects.filter(
        participants=user
    ).select_related('item', 'board_request').prefetch_related(
        'participants', 'messages'
    ).order_by('-updated_at')

    conversation_list = []
    for conv in conversations:
        other_user = conv.get_other_user(user)
        last_msg = conv.last_message()
        unread_count = conv.messages.filter(is_read=False).exclude(sender=user).count()
        conversation_list.append({
            'conversation': conv,
            'other_user': other_user,
            'last_message': last_msg,
            'unread_count': unread_count,
            'item': conv.item,
        })

    return conversation_list


@login_required
def inbox_view(request):
    """List all conversations for the current user."""
    return render(request, 'messaging/inbox.html', {
        'conversation_list': _conversation_list_for(request.user),
    })


@login_required
def conversation_view(request, conv_id):
    """View a single conversation and send messages."""
    conversation = get_object_or_404(
        Conversation.objects.prefetch_related('participants'),
        pk=conv_id,
    )

    # Unknown IDs and other people's conversations both 404.
    if not conversation.participants.filter(pk=request.user.pk).exists():
        raise Http404('Conversation not found.')

    # Mark unread messages from the other person as read
    conversation.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)

    if request.method == 'POST':
        form = MessageForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                msg = form.save(commit=False)
                msg.conversation = conversation
                msg.sender = request.user
                msg.is_read = False
                msg.save()
                conversation.save(update_fields=['updated_at'])
                for recipient in conversation.participants.exclude(pk=request.user.pk):
                    create_notification(
                        recipient=recipient,
                        actor=request.user,
                        notification_type='message',
                        message=f'New message from {request.user.get_full_name() or request.user.username}.',
                        target=conversation,
                        target_url=reverse('conversation', args=[conversation.pk]),
                        dedupe_key=f'message:{msg.pk}',
                    )
            return redirect('conversation', conv_id=conv_id)
    else:
        form = MessageForm()

    other_user = conversation.get_other_user(request.user)
    all_messages = conversation.messages.order_by('created_at')

    return render(request, 'messaging/conversation.html', {
        'conversation': conversation,
        'other_user': other_user,
        'all_messages': all_messages,
        'form': form,
        'conversation_list': _conversation_list_for(request.user),
    })


@login_required
def start_board_conversation(request, board_request_id):
    with transaction.atomic():
        board_request = get_object_or_404(
            BoardRequest.objects.select_for_update(),
            pk=board_request_id,
            is_fulfilled=False,
        )
        if board_request.posted_by == request.user:
            django_messages.error(request, "You can't respond to your own request.")
            return redirect('board')

        conversation, created = Conversation.objects.get_or_create(
            board_request=board_request,
            board_responder=request.user,
        )
        conversation.participants.add(board_request.posted_by, request.user)
        if created:
            create_notification(
                recipient=board_request.posted_by,
                actor=request.user,
                notification_type='board_response',
                message=(
                    f'{request.user.get_full_name() or request.user.username} '
                    f'responded to your request: {board_request.title}.'
                ),
                target=conversation,
                target_url=reverse('conversation', args=[conversation.pk]),
                dedupe_key=f'board-response:{board_request.pk}:{request.user.pk}',
            )

    return redirect('conversation', conv_id=conversation.pk)


@login_required
def start_conversation(request, username, item_id=None):
    """Start a new conversation with a user, optionally about an item."""
    other_user = get_object_or_404(User, username=username)

    if other_user == request.user:
        django_messages.error(request, "You can't message yourself.")
        return redirect('home')

    item = None
    if item_id:
        item = get_object_or_404(Item, pk=item_id)
        if request.user == item.owner:
            request_model = BuyRequest if item.listing_type == 'sell' else RentRequest
            has_requested_item = request_model.objects.filter(
                item=item,
                requester=other_user,
            ).exists()
            if not has_requested_item:
                django_messages.error(
                    request,
                    'You can only message students who have requested this listing.',
                )
                return redirect('dashboard')
        elif other_user != item.owner:
            django_messages.error(request, 'You can only message the owner of this listing.')
            return redirect('item_detail', pk=item.pk)

    # Check if a conversation already exists between these two users about this item
    existing = Conversation.objects.filter(
        participants=request.user
    ).filter(
        participants=other_user
    )
    if item:
        existing = existing.filter(item=item)
    else:
        existing = existing.filter(item__isnull=True)

    conv = existing.first()

    if conv:
        return redirect('conversation', conv_id=conv.pk)

    # Create new conversation
    conv = Conversation.objects.create(item=item)
    conv.participants.add(request.user, other_user)

    django_messages.success(request, f'Conversation started with {other_user.get_full_name() or other_user.username}!')
    return redirect('conversation', conv_id=conv.pk)


@login_required
def notifications_view(request):
    notifications = Notification.objects.filter(
        recipient=request.user,
    ).select_related('actor', 'content_type')
    notification_rows = []
    for notification in notifications:
        action_data = _notification_action_data(notification, request.user)
        has_action = any((
            action_data['message_destination'],
            action_data['details_destination'],
            action_data['approve_url'],
            action_data['reject_url'],
        ))
        notification_rows.append({
            'notification': notification,
            'status_label': action_data['status_label'],
            'status_class': action_data['status_class'],
            'message_url': (
                f"{reverse('open_notification', args=[notification.pk])}?action=message"
                if action_data['message_destination'] else ''
            ),
            'message_label': action_data['message_label'],
            'details_url': (
                f"{reverse('open_notification', args=[notification.pk])}?action=details"
                if action_data['details_destination'] else ''
            ),
            'details_label': action_data['details_label'],
            'approve_url': action_data['approve_url'],
            'reject_url': action_data['reject_url'],
            'show_mark_read': not notification.is_read and not has_action,
        })

    return render(request, 'messaging/notifications.html', {
        'notification_rows': notification_rows,
    })


def _notification_action_data(notification, user):
    data = {
        'status_label': '',
        'status_class': '',
        'message_destination': '',
        'message_label': '',
        'details_destination': '',
        'details_label': '',
        'approve_url': '',
        'reject_url': '',
    }
    target = notification.content_object
    notification_type = notification.notification_type

    if notification_type == 'item_requested' and isinstance(target, (BuyRequest, RentRequest)):
        if target.item.owner_id != user.pk:
            return data

        data['status_label'] = target.get_status_display()
        data['status_class'] = f'status-{target.status}'
        data['message_destination'] = reverse(
            'start_conversation_item',
            args=[target.requester.username, target.item_id],
        )
        data['message_label'] = 'Message'
        if target.status == 'pending':
            if isinstance(target, BuyRequest):
                data['approve_url'] = reverse('approve_buy_request', args=[target.pk])
                data['reject_url'] = reverse('reject_buy_request', args=[target.pk])
            else:
                data['approve_url'] = reverse('approve_rent_request', args=[target.pk])
                data['reject_url'] = reverse('reject_rent_request', args=[target.pk])

    elif notification_type in {'item_approved', 'item_rejected'} and isinstance(
        target, (BuyRequest, RentRequest)
    ):
        if target.requester_id != user.pk:
            return data
        data['status_label'] = target.get_status_display()
        data['status_class'] = f'status-{target.status}'
        data['details_destination'] = reverse('item_detail', args=[target.item_id])
        data['details_label'] = 'View Details'
        data['message_destination'] = reverse(
            'start_conversation_item',
            args=[target.item.owner.username, target.item_id],
        )
        data['message_label'] = 'Message'

    elif notification_type == 'board_response' and isinstance(target, Conversation):
        if not target.participants.filter(pk=user.pk).exists():
            return data
        data['message_destination'] = reverse('conversation', args=[target.pk])
        data['message_label'] = 'Message'
        if target.board_request_id:
            data['details_destination'] = (
                f"{reverse('board')}#board-request-{target.board_request_id}"
            )
            data['details_label'] = 'View Request'

    elif notification_type == 'message' and isinstance(target, Conversation):
        if not target.participants.filter(pk=user.pk).exists():
            return data
        data['message_destination'] = reverse('conversation', args=[target.pk])
        data['message_label'] = 'Reply'

    elif notification_type == 'request_fulfilled' and isinstance(target, BoardRequest):
        data['status_label'] = 'Fulfilled' if target.is_fulfilled else 'Open'
        data['status_class'] = 'status-fulfilled' if target.is_fulfilled else 'status-open'
        data['details_destination'] = (
            f"{reverse('board')}?fulfilled=1#board-request-{target.pk}"
        )
        data['details_label'] = 'View Details'

    elif notification_type == 'transaction_status' and isinstance(target, RentRequest):
        if target.requester_id != user.pk:
            return data
        data['status_label'] = target.get_status_display()
        data['status_class'] = f'status-{target.status}'
        data['details_destination'] = reverse('item_detail', args=[target.item_id])
        data['details_label'] = 'View Details'
        data['message_destination'] = reverse(
            'start_conversation_item',
            args=[target.item.owner.username, target.item_id],
        )
        data['message_label'] = 'Message'

    return data


@login_required
def open_notification(request, notification_id):
    notification = get_object_or_404(
        Notification,
        pk=notification_id,
        recipient=request.user,
    )
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=['is_read'])

    action = request.GET.get('action')
    action_data = _notification_action_data(notification, request.user)
    destination = {
        'message': action_data['message_destination'],
        'details': action_data['details_destination'],
    }.get(action, '') or notification.target_url
    if (
        not destination.startswith('/')
        or destination.startswith('//')
        or not url_has_allowed_host_and_scheme(
            destination,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        )
    ):
        destination = reverse('notifications')
    return redirect(destination)


@login_required
@require_POST
def mark_notification_read(request, notification_id):
    notification = get_object_or_404(
        Notification,
        pk=notification_id,
        recipient=request.user,
    )
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=['is_read'])
    return redirect('notifications')


@login_required
@require_POST
def mark_all_notifications_read(request):
    Notification.objects.filter(
        recipient=request.user,
        is_read=False,
    ).update(is_read=True)
    return redirect('notifications')


@login_required
def unread_counts_json(request):
    from messaging.models import Message, Notification
    unread_messages = Message.objects.filter(
        conversation__participants=request.user,
        is_read=False,
    ).exclude(sender=request.user).count()
    unread_notifications = Notification.objects.filter(
        recipient=request.user,
        is_read=False,
    ).count()
    return JsonResponse({
        'unread_messages': unread_messages,
        'unread_notifications': unread_notifications,
    })
