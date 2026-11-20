from django.contrib.contenttypes.models import ContentType
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.urls import reverse
from django.views.decorators.http import require_POST
from items.models import Item
from messaging.models import Notification
from messaging.services import create_notification
from .models import BuyRequest, RentRequest
from .forms import BuyRequestForm, RentRequestForm


def _notify_request_status(item_request, actor, status):
    approved = status == 'approved'
    request_anchor = (
        'my-buy-request'
        if item_request._meta.model_name == 'buyrequest'
        else 'my-rent-request'
    )
    create_notification(
        recipient=item_request.requester,
        actor=actor,
        notification_type='item_approved' if approved else 'item_rejected',
        message=(
            f'Your request for "{item_request.item.title}" was '
            f'{"approved" if approved else "rejected"}.'
        ),
        target=item_request,
        target_url=f"{reverse('dashboard')}#{request_anchor}-{item_request.pk}",
        dedupe_key=f'{item_request._meta.model_name}:{item_request.pk}:{status}',
    )


def _mark_action_notification_read(request, item_request):
    notification_id = request.POST.get('notification_id')
    if not notification_id:
        return False
    try:
        notification_id = int(notification_id)
    except ValueError:
        return False

    content_type = ContentType.objects.get_for_model(item_request)
    notification = Notification.objects.filter(
        pk=notification_id,
        recipient=request.user,
        notification_type='item_requested',
        content_type=content_type,
        object_id=item_request.pk,
        is_read=False,
    ).first()
    if notification is None:
        return False

    notification.is_read = True
    notification.save(update_fields=['is_read'])
    return True


@login_required
def request_to_buy(request, pk):
    item = get_object_or_404(Item, pk=pk, listing_type='sell', status='available')

    if item.owner == request.user:
        messages.error(request, "You can't request your own item.")
        return redirect('item_detail', pk=pk)

    if BuyRequest.objects.filter(item=item, requester=request.user).exists():
        messages.warning(request, 'You already have a request for this item.')
        return redirect('item_detail', pk=pk)

    if request.method == 'POST':
        form = BuyRequestForm(request.POST)
        if form.is_valid():
            req = form.save(commit=False)
            req.item = item
            req.requester = request.user
            with transaction.atomic():
                req.save()
                create_notification(
                    recipient=item.owner,
                    actor=request.user,
                    notification_type='item_requested',
                    message=f'{request.user.get_full_name() or request.user.username} requested to buy "{item.title}".',
                    target=req,
                    target_url=f"{reverse('dashboard')}#buy-request-{req.pk}",
                    dedupe_key=f'buy-request:{req.pk}:submitted',
                )
            messages.success(request, 'Request sent! You will be notified when the seller responds.')
            return redirect('item_detail', pk=pk)
    else:
        form = BuyRequestForm()

    return render(request, 'transactions/request_to_buy.html', {'form': form, 'item': item})


@login_required
def request_to_rent(request, pk):
    item = get_object_or_404(Item, pk=pk, listing_type='rent', status='available')

    if item.owner == request.user:
        messages.error(request, "You can't request your own item.")
        return redirect('item_detail', pk=pk)

    if RentRequest.objects.filter(item=item, requester=request.user).exists():
        messages.warning(request, 'You already have a request for this item.')
        return redirect('item_detail', pk=pk)

    if request.method == 'POST':
        form = RentRequestForm(request.POST)
        if form.is_valid():
            req = form.save(commit=False)
            req.item = item
            req.requester = request.user
            with transaction.atomic():
                req.save()
                create_notification(
                    recipient=item.owner,
                    actor=request.user,
                    notification_type='item_requested',
                    message=f'{request.user.get_full_name() or request.user.username} requested to rent "{item.title}".',
                    target=req,
                    target_url=f"{reverse('dashboard')}#rent-request-{req.pk}",
                    dedupe_key=f'rent-request:{req.pk}:submitted',
                )
            messages.success(request, 'Rent request sent! The owner will review it shortly.')
            return redirect('item_detail', pk=pk)
    else:
        form = RentRequestForm()

    return render(request, 'transactions/request_to_rent.html', {'form': form, 'item': item})


@login_required
@require_POST
def approve_buy_request(request, req_id):
    acted_from_notification = False
    with transaction.atomic():
        buy_req = get_object_or_404(
            BuyRequest.objects.select_for_update().select_related('item', 'requester'),
            pk=req_id,
        )
        if buy_req.item.owner != request.user:
            messages.error(request, 'Permission denied.')
            return redirect('dashboard')
        if buy_req.status != 'pending':
            messages.info(request, 'This request has already been handled.')
            return redirect('dashboard')

        other_requests = list(
            BuyRequest.objects.select_for_update().filter(
                item=buy_req.item,
                status='pending',
            ).exclude(pk=req_id).select_related('requester')
        )
        buy_req.status = 'approved'
        buy_req.save(update_fields=['status'])
        buy_req.item.status = 'sold'
        buy_req.item.save(update_fields=['status'])
        _notify_request_status(buy_req, request.user, 'approved')

        for other_request in other_requests:
            other_request.status = 'rejected'
            other_request.save(update_fields=['status'])
            _notify_request_status(other_request, request.user, 'rejected')
        acted_from_notification = _mark_action_notification_read(request, buy_req)

    messages.success(request, f'Request by {buy_req.requester.username} approved. Item marked as sold.')
    return redirect('notifications' if acted_from_notification else 'dashboard')


@login_required
@require_POST
def reject_buy_request(request, req_id):
    acted_from_notification = False
    with transaction.atomic():
        buy_req = get_object_or_404(
            BuyRequest.objects.select_for_update().select_related('item', 'requester'),
            pk=req_id,
        )
        if buy_req.item.owner != request.user:
            messages.error(request, 'Permission denied.')
            return redirect('dashboard')
        if buy_req.status != 'pending':
            messages.info(request, 'This request has already been handled.')
            return redirect('dashboard')
        buy_req.status = 'rejected'
        buy_req.save(update_fields=['status'])
        _notify_request_status(buy_req, request.user, 'rejected')
        acted_from_notification = _mark_action_notification_read(request, buy_req)

    messages.info(request, f'Request by {buy_req.requester.username} rejected.')
    return redirect('notifications' if acted_from_notification else 'dashboard')


@login_required
@require_POST
def approve_rent_request(request, req_id):
    acted_from_notification = False
    with transaction.atomic():
        rent_req = get_object_or_404(
            RentRequest.objects.select_for_update().select_related('item', 'requester'),
            pk=req_id,
        )
        if rent_req.item.owner != request.user:
            messages.error(request, 'Permission denied.')
            return redirect('dashboard')
        if rent_req.status != 'pending':
            messages.info(request, 'This request has already been handled.')
            return redirect('dashboard')

        other_requests = list(
            RentRequest.objects.select_for_update().filter(
                item=rent_req.item,
                status='pending',
            ).exclude(pk=req_id).select_related('requester')
        )
        rent_req.status = 'approved'
        rent_req.save(update_fields=['status'])
        rent_req.item.status = 'rented'
        rent_req.item.save(update_fields=['status'])
        _notify_request_status(rent_req, request.user, 'approved')

        for other_request in other_requests:
            other_request.status = 'rejected'
            other_request.save(update_fields=['status'])
            _notify_request_status(other_request, request.user, 'rejected')
        acted_from_notification = _mark_action_notification_read(request, rent_req)

    messages.success(
        request,
        f'Rent request by {rent_req.requester.username} approved. Item is now rented out.'
    )
    return redirect('notifications' if acted_from_notification else 'dashboard')


@login_required
@require_POST
def reject_rent_request(request, req_id):
    acted_from_notification = False
    with transaction.atomic():
        rent_req = get_object_or_404(
            RentRequest.objects.select_for_update().select_related('item', 'requester'),
            pk=req_id,
        )
        if rent_req.item.owner != request.user:
            messages.error(request, 'Permission denied.')
            return redirect('dashboard')
        if rent_req.status != 'pending':
            messages.info(request, 'This request has already been handled.')
            return redirect('dashboard')
        rent_req.status = 'rejected'
        rent_req.save(update_fields=['status'])
        _notify_request_status(rent_req, request.user, 'rejected')
        acted_from_notification = _mark_action_notification_read(request, rent_req)

    messages.info(request, f'Rent request by {rent_req.requester.username} rejected.')
    return redirect('notifications' if acted_from_notification else 'dashboard')


@login_required
@require_POST
def mark_returned(request, req_id):
    with transaction.atomic():
        rent_req = get_object_or_404(
            RentRequest.objects.select_for_update().select_related('item', 'requester'),
            pk=req_id,
            status='approved',
        )
        if rent_req.item.owner != request.user:
            messages.error(request, 'Permission denied.')
            return redirect('dashboard')

        rent_req.status = 'returned'
        rent_req.save(update_fields=['status'])
        rent_req.item.status = 'available'
        rent_req.item.save(update_fields=['status'])
        create_notification(
            recipient=rent_req.requester,
            actor=request.user,
            notification_type='transaction_status',
            message=f'"{rent_req.item.title}" has been marked as returned.',
            target=rent_req,
            target_url=f"{reverse('dashboard')}#my-rent-request-{rent_req.pk}",
            dedupe_key=f'rent-request:{rent_req.pk}:returned',
        )

    messages.success(request, 'Item marked as returned and is now available for rent again!')
    return redirect('dashboard')


@login_required
def dashboard_view(request):
    # === AS SELLER ===
    my_items = Item.objects.filter(owner=request.user).order_by('-created_at')
    incoming_buy_requests = BuyRequest.objects.filter(
        item__owner=request.user, status='pending'
    ).select_related('item', 'requester')
    incoming_rent_requests = RentRequest.objects.filter(
        item__owner=request.user, status='pending'
    ).select_related('item', 'requester')
    active_rentals_out = RentRequest.objects.filter(
        item__owner=request.user, status='approved'
    ).select_related('item', 'requester')

    # === AS BUYER / RENTER ===
    my_buy_requests = BuyRequest.objects.filter(
        requester=request.user
    ).select_related('item').order_by('-created_at')
    my_rent_requests = RentRequest.objects.filter(
        requester=request.user
    ).select_related('item').order_by('-created_at')

    return render(request, 'transactions/dashboard.html', {
        # seller
        'my_items': my_items,
        'incoming_buy_requests': incoming_buy_requests,
        'incoming_rent_requests': incoming_rent_requests,
        'active_rentals_out': active_rentals_out,
        # buyer/renter
        'my_buy_requests': my_buy_requests,
        'my_rent_requests': my_rent_requests,
    })
