from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import Item, CATEGORY_CHOICES
from .forms import ItemForm


def home_view(request):
    items = Item.objects.filter(status='available')

    # Search
    query = request.GET.get('q', '')
    if query:
        items = items.filter(Q(title__icontains=query) | Q(description__icontains=query))

    # Filter by category
    category = request.GET.get('category', '')
    if category:
        items = items.filter(category=category)

    # Filter by listing type
    listing_type = request.GET.get('type', '')
    if listing_type in ['sell', 'rent']:
        items = items.filter(listing_type=listing_type)

    # Sort
    sort = request.GET.get('sort', 'newest')
    if sort == 'price_asc':
        items = items.order_by('price', 'rent_per_day')
    elif sort == 'price_desc':
        items = items.order_by('-price', '-rent_per_day')
    else:
        items = items.order_by('-created_at')

    recent_items = Item.objects.filter(status='available').order_by('-created_at')[:8]

    return render(request, 'items/home.html', {
        'items': items,
        'recent_items': recent_items,
        'categories': CATEGORY_CHOICES,
        'query': query,
        'selected_category': category,
        'selected_type': listing_type,
        'sort': sort,
    })


def explore_view(request):
    items = Item.objects.filter(status='available')

    query = request.GET.get('q', '')
    if query:
        items = items.filter(Q(title__icontains=query) | Q(description__icontains=query))

    category = request.GET.get('category', '')
    if category:
        items = items.filter(category=category)

    listing_type = request.GET.get('type', '')
    if listing_type in ['sell', 'rent']:
        items = items.filter(listing_type=listing_type)

    sort = request.GET.get('sort', 'newest')
    if sort == 'price_asc':
        items = items.order_by('price', 'rent_per_day')
    elif sort == 'price_desc':
        items = items.order_by('-price', '-rent_per_day')
    else:
        items = items.order_by('-created_at')

    return render(request, 'items/explore.html', {
        'items': items,
        'categories': CATEGORY_CHOICES,
        'query': query,
        'selected_category': category,
        'selected_type': listing_type,
        'sort': sort,
    })


def item_detail_view(request, pk):
    item = get_object_or_404(Item, pk=pk)

    # Check if the logged-in user has an APPROVED request for this item
    show_contact = False
    has_pending_request = False
    has_approved_request = False

    if request.user.is_authenticated and request.user != item.owner:
        from transactions.models import BuyRequest, RentRequest

        approved_buy = BuyRequest.objects.filter(
            item=item, requester=request.user, status='approved'
        ).exists()
        approved_rent = RentRequest.objects.filter(
            item=item, requester=request.user, status='approved'
        ).exists()
        show_contact = approved_buy or approved_rent
        has_approved_request = show_contact

        pending_buy = BuyRequest.objects.filter(
            item=item, requester=request.user, status='pending'
        ).exists()
        pending_rent = RentRequest.objects.filter(
            item=item, requester=request.user, status='pending'
        ).exists()
        has_pending_request = pending_buy or pending_rent

    # Related items: same category, available, not this one
    related_items = Item.objects.filter(
        category=item.category, status='available'
    ).exclude(pk=pk)[:4]

    return render(request, 'items/item_detail.html', {
        'item': item,
        'show_contact': show_contact,
        'has_pending_request': has_pending_request,
        'has_approved_request': has_approved_request,
        'related_items': related_items,
    })


@login_required
def post_item_view(request):
    if request.method == 'POST':
        form = ItemForm(request.POST, request.FILES)
        if form.is_valid():
            item = form.save(commit=False)
            item.owner = request.user
            item.save()
            messages.success(request, 'Your listing is live!')
            return redirect('item_detail', pk=item.pk)
    else:
        form = ItemForm()
    return render(request, 'items/post_item.html', {'form': form})


@login_required
def edit_item_view(request, pk):
    item = get_object_or_404(Item, pk=pk)
    if item.owner != request.user:
        messages.error(request, 'You can only edit your own listings.')
        return redirect('item_detail', pk=pk)
    if item.status != 'available':
        messages.error(request, 'You cannot edit a rented or sold item.')
        return redirect('item_detail', pk=pk)

    if request.method == 'POST':
        form = ItemForm(request.POST, request.FILES, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, 'Listing updated.')
            return redirect('item_detail', pk=pk)
    else:
        form = ItemForm(instance=item)
    return render(request, 'items/edit_item.html', {'form': form, 'item': item})


@login_required
def delete_item_view(request, pk):
    item = get_object_or_404(Item, pk=pk)
    if item.owner != request.user:
        messages.error(request, 'You can only delete your own listings.')
        return redirect('item_detail', pk=pk)
    if request.method == 'POST':
        item.delete()
        messages.success(request, 'Listing deleted.')
        return redirect('my_items')
    return render(request, 'items/delete_item.html', {'item': item})


@login_required
def my_items_view(request):
    my_items = Item.objects.filter(owner=request.user).order_by('-created_at')
    return render(request, 'items/my_items.html', {'my_items': my_items})
