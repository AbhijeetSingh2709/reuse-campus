from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from items.models import Item
from .models import BuyRequest, RentRequest
from .forms import BuyRequestForm, RentRequestForm


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
            req.save()
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
            req.save()
            messages.success(request, 'Rent request sent! The owner will review it shortly.')
            return redirect('item_detail', pk=pk)
    else:
        form = RentRequestForm()

    return render(request, 'transactions/request_to_rent.html', {'form': form, 'item': item})


@login_required
def approve_buy_request(request, req_id):
    buy_req = get_object_or_404(BuyRequest, pk=req_id)
    if buy_req.item.owner != request.user:
        messages.error(request, 'Permission denied.')
        return redirect('dashboard')

    buy_req.status = 'approved'
    buy_req.save()

    # Mark item as sold
    buy_req.item.status = 'sold'
    buy_req.item.save()

    # Auto-reject all other pending requests for this item
    BuyRequest.objects.filter(
        item=buy_req.item, status='pending'
    ).exclude(pk=req_id).update(status='rejected')

    messages.success(request, f'Request by {buy_req.requester.username} approved. Item marked as sold.')
    return redirect('dashboard')


@login_required
def reject_buy_request(request, req_id):
    buy_req = get_object_or_404(BuyRequest, pk=req_id)
    if buy_req.item.owner != request.user:
        messages.error(request, 'Permission denied.')
        return redirect('dashboard')

    buy_req.status = 'rejected'
    buy_req.save()
    messages.info(request, f'Request by {buy_req.requester.username} rejected.')
    return redirect('dashboard')


@login_required
def approve_rent_request(request, req_id):
    rent_req = get_object_or_404(RentRequest, pk=req_id)
    if rent_req.item.owner != request.user:
        messages.error(request, 'Permission denied.')
        return redirect('dashboard')

    rent_req.status = 'approved'
    rent_req.save()

    # Mark item as rented
    rent_req.item.status = 'rented'
    rent_req.item.save()

    # Auto-reject all other pending rent requests for this item
    RentRequest.objects.filter(
        item=rent_req.item, status='pending'
    ).exclude(pk=req_id).update(status='rejected')

    messages.success(
        request,
        f'Rent request by {rent_req.requester.username} approved. Item is now rented out.'
    )
    return redirect('dashboard')


@login_required
def reject_rent_request(request, req_id):
    rent_req = get_object_or_404(RentRequest, pk=req_id)
    if rent_req.item.owner != request.user:
        messages.error(request, 'Permission denied.')
        return redirect('dashboard')

    rent_req.status = 'rejected'
    rent_req.save()
    messages.info(request, f'Rent request by {rent_req.requester.username} rejected.')
    return redirect('dashboard')


@login_required
def mark_returned(request, req_id):
    rent_req = get_object_or_404(RentRequest, pk=req_id, status='approved')
    if rent_req.item.owner != request.user:
        messages.error(request, 'Permission denied.')
        return redirect('dashboard')

    rent_req.status = 'returned'
    rent_req.save()

    # Make item available for rent again
    rent_req.item.status = 'available'
    rent_req.item.save()

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
