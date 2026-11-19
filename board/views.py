from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.urls import reverse
from django.views.decorators.http import require_POST
from .models import BoardRequest
from .forms import BoardRequestForm
from items.models import CATEGORY_CHOICES
from messaging.services import create_notification
from users.models import User


def board_view(request):
    board_requests = BoardRequest.objects.all()

    category = request.GET.get('category', '')
    if category:
        board_requests = board_requests.filter(category=category)

    show_fulfilled = request.GET.get('fulfilled', '') == '1'
    if not show_fulfilled:
        board_requests = board_requests.filter(is_fulfilled=False)

    return render(request, 'board/board.html', {
        'board_requests': board_requests,
        'categories': CATEGORY_CHOICES,
        'selected_category': category,
        'show_fulfilled': show_fulfilled,
    })


@login_required
def post_board_request(request):
    if request.method == 'POST':
        form = BoardRequestForm(request.POST)
        if form.is_valid():
            br = form.save(commit=False)
            br.posted_by = request.user
            br.save()
            messages.success(request, 'Your request has been posted on the board!')
            return redirect('board')
    else:
        form = BoardRequestForm()
    return render(request, 'board/post_request.html', {'form': form})


@login_required
@require_POST
def fulfill_request(request, pk):
    with transaction.atomic():
        br = get_object_or_404(
            BoardRequest.objects.select_for_update(),
            pk=pk,
            posted_by=request.user,
        )
        if br.is_fulfilled:
            messages.info(request, 'This request is already fulfilled.')
            return redirect('board')

        br.is_fulfilled = True
        br.save(update_fields=['is_fulfilled'])
        responder_ids = br.conversations.exclude(
            board_responder=request.user,
        ).values_list('board_responder_id', flat=True).distinct()
        responders = User.objects.filter(pk__in=responder_ids)
        destination = f"{reverse('board')}#board-request-{br.pk}"
        for responder in responders:
            create_notification(
                recipient=responder,
                actor=request.user,
                notification_type='request_fulfilled',
                message=f'"{br.title}" has been marked as fulfilled.',
                target=br,
                target_url=destination,
                dedupe_key=f'board-request:{br.pk}:fulfilled:{responder.pk}',
            )
    messages.success(request, 'Marked as fulfilled!')
    return redirect('board')
