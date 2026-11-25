import datetime
from decimal import Decimal, InvalidOperation

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.files.storage import default_storage
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import Item, ItemImage, CATEGORY_CHOICES, CONDITION_CHOICES
from .forms import ItemForm, ItemImageFormSet


def _delete_stored_file(name):
    """Remove a media file after the database no longer points at it."""
    if name:
        default_storage.delete(name)


def _parse_decimal(raw_value):
    if not raw_value:
        return None
    try:
        value = Decimal(str(raw_value).strip())
        return value if value >= 0 else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def _wishlisted_item_ids(user):
    if user and user.is_authenticated:
        return set(user.wishlist.values_list('pk', flat=True))
    return set()


def _apply_filters(request, queryset):
    query = request.GET.get('q', '').strip()
    if query:
        queryset = queryset.filter(Q(title__icontains=query) | Q(description__icontains=query))
    category = request.GET.get('category', '')
    if category:
        queryset = queryset.filter(category=category)
    listing_type = request.GET.get('type', '')
    if listing_type in ['sell', 'rent']:
        queryset = queryset.filter(listing_type=listing_type)
    condition = request.GET.get('condition', '')
    valid_conditions = {code for code, _ in CONDITION_CHOICES}
    if condition in valid_conditions:
        queryset = queryset.filter(condition=condition)
    else:
        condition = ''

    min_price = _parse_decimal(request.GET.get('min_price', ''))
    max_price = _parse_decimal(request.GET.get('max_price', ''))
    if min_price is not None:
        queryset = queryset.filter(
            Q(listing_type='sell', price__gte=min_price) |
            Q(listing_type='rent', rent_per_day__gte=min_price)
        )
    if max_price is not None:
        queryset = queryset.filter(
            Q(listing_type='sell', price__lte=max_price) |
            Q(listing_type='rent', rent_per_day__lte=max_price)
        )

    sort = request.GET.get('sort', 'newest')
    if sort == 'price_asc':
        queryset = queryset.order_by('price', 'rent_per_day')
    elif sort == 'price_desc':
        queryset = queryset.order_by('-price', '-rent_per_day')
    else:
        queryset = queryset.order_by('-created_at')
    return queryset, query, category, listing_type, condition, sort


def home_view(request):
    base_qs = Item.objects.filter(status='available')
    items, query, category, listing_type, condition, sort = _apply_filters(request, base_qs)
    paginator = Paginator(items, 12)
    page_obj = paginator.get_page(request.GET.get('page'))
    recent_items = Item.objects.filter(status='available').order_by('-created_at')[:8]
    return render(request, 'items/home.html', {
        'items': page_obj,
        'page_obj': page_obj,
        'recent_items': recent_items,
        'categories': CATEGORY_CHOICES,
        'conditions': CONDITION_CHOICES,
        'query': query,
        'selected_category': category,
        'selected_type': listing_type,
        'selected_condition': condition,
        'sort': sort,
        'wishlisted_ids': _wishlisted_item_ids(request.user),
    })


def explore_view(request):
    base_qs = Item.objects.filter(status='available')
    items, query, category, listing_type, condition, sort = _apply_filters(request, base_qs)
    paginator = Paginator(items, 16)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'items/explore.html', {
        'items': page_obj,
        'page_obj': page_obj,
        'categories': CATEGORY_CHOICES,
        'conditions': CONDITION_CHOICES,
        'query': query,
        'selected_category': category,
        'selected_type': listing_type,
        'selected_condition': condition,
        'sort': sort,
        'min_price': request.GET.get('min_price', ''),
        'max_price': request.GET.get('max_price', ''),
        'wishlisted_ids': _wishlisted_item_ids(request.user),
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
        has_formset = 'extra_images-TOTAL_FORMS' in request.POST
        image_formset = (
            ItemImageFormSet(
                request.POST, request.FILES, queryset=ItemImage.objects.none(), prefix='extra_images'
            )
            if has_formset
            else ItemImageFormSet(queryset=ItemImage.objects.none(), prefix='extra_images')
        )
        formset_ok = image_formset.is_valid() if has_formset else True
        if form.is_valid() and formset_ok:
            item = form.save(commit=False)
            item.owner = request.user
            item.save()
            if has_formset:
                for img_form in image_formset:
                    if img_form.cleaned_data.get('image') and not img_form.cleaned_data.get('DELETE', False):
                        img_obj = img_form.save(commit=False)
                        img_obj.item = item
                        img_obj.save()
            messages.success(request, 'Your listing is live!')
            return redirect('item_detail', pk=item.pk)
    else:
        form = ItemForm()
        image_formset = ItemImageFormSet(queryset=ItemImage.objects.none(), prefix='extra_images')
    return render(request, 'items/post_item.html', {'form': form, 'image_formset': image_formset})


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
        previous_image = item.image.name if item.image else ''
        form = ItemForm(request.POST, request.FILES, instance=item)
        has_formset = 'extra_images-TOTAL_FORMS' in request.POST
        image_formset = (
            ItemImageFormSet(
                request.POST, request.FILES, queryset=item.extra_images.all(), prefix='extra_images'
            )
            if has_formset
            else ItemImageFormSet(queryset=item.extra_images.all(), prefix='extra_images')
        )
        formset_ok = image_formset.is_valid() if has_formset else True
        if form.is_valid() and formset_ok:
            new_upload = 'image' in request.FILES
            remove_image = form.cleaned_data.get('remove_image') and not new_upload
            updated = form.save(commit=False)
            if remove_image:
                updated.image = None
            updated.save()
            current_image = updated.image.name if updated.image else ''
            if previous_image and previous_image != current_image:
                _delete_stored_file(previous_image)
            if has_formset:
                for img_form in image_formset:
                    if img_form.cleaned_data.get('DELETE') and img_form.instance.pk:
                        _delete_stored_file(img_form.instance.image.name if img_form.instance.image else '')
                        img_form.instance.delete()
                    elif img_form.cleaned_data.get('image') and not img_form.cleaned_data.get('DELETE', False):
                        old_extra = ''
                        if img_form.instance.pk and 'image' in img_form.changed_data:
                            old_extra = ItemImage.objects.filter(pk=img_form.instance.pk).values_list('image', flat=True).first() or ''
                        img_obj = img_form.save(commit=False)
                        img_obj.item = item
                        img_obj.save()
                        if old_extra and old_extra != img_obj.image.name:
                            _delete_stored_file(old_extra)
            messages.success(request, 'Listing updated.')
            return redirect('item_detail', pk=pk)
    else:
        form = ItemForm(instance=item)
        image_formset = ItemImageFormSet(queryset=item.extra_images.all(), prefix='extra_images')
    return render(request, 'items/edit_item.html', {'form': form, 'item': item, 'image_formset': image_formset})


@login_required
def delete_item_view(request, pk):
    item = get_object_or_404(Item, pk=pk)
    if item.owner != request.user:
        messages.error(request, 'You can only delete your own listings.')
        return redirect('item_detail', pk=pk)
    if request.method == 'POST':
        previous_image = item.image.name if item.image else ''
        extra_files = [img.image.name for img in item.extra_images.all() if img.image]
        item.delete()
        _delete_stored_file(previous_image)
        for extra_file in extra_files:
            _delete_stored_file(extra_file)
        messages.success(request, 'Listing deleted.')
        return redirect('my_items')
    return render(request, 'items/delete_item.html', {'item': item})


@login_required
def my_items_view(request):
    my_items = Item.objects.filter(owner=request.user).order_by('-created_at')
    return render(request, 'items/my_items.html', {'my_items': my_items})


@login_required
@require_POST
def toggle_wishlist(request, pk):
    item = get_object_or_404(Item, pk=pk)
    user = request.user
    if user.wishlist.filter(pk=item.pk).exists():
        user.wishlist.remove(item)
        saved = False
    else:
        user.wishlist.add(item)
        saved = True
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'saved': saved})
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER', '')
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(next_url)
    return redirect('item_detail', pk=pk)


@login_required
def wishlist_view(request):
    saved_items = request.user.wishlist.filter(status='available').order_by('-created_at')
    return render(request, 'items/wishlist.html', {'saved_items': saved_items})


@staff_member_required
def admin_dashboard_view(request):
    thirty_days_ago = timezone.now() - datetime.timedelta(days=30)
    total_items = Item.objects.count()
    available_items = Item.objects.filter(status='available').count()
    sold_items = Item.objects.filter(status='sold').count()
    rented_items = Item.objects.filter(status='rented').count()
    items_this_month = Item.objects.filter(created_at__gte=thirty_days_ago).count()
    from transactions.models import BuyRequest, RentRequest
    total_buy_requests = BuyRequest.objects.count()
    approved_buy = BuyRequest.objects.filter(status='approved').count()
    total_rent_requests = RentRequest.objects.count()
    approved_rent = RentRequest.objects.filter(status='approved').count()
    from users.models import User
    total_users = User.objects.count()
    new_users_this_month = User.objects.filter(date_joined__gte=thirty_days_ago).count()
    category_data = Item.objects.values('category').annotate(count=Count('id')).order_by('-count')
    popular_categories = [(d['category'], d['count']) for d in category_data]
    recent_items = Item.objects.select_related('owner').order_by('-created_at')[:10]
    return render(request, 'items/admin_dashboard.html', {
        'total_items': total_items,
        'available_items': available_items,
        'sold_items': sold_items,
        'rented_items': rented_items,
        'items_this_month': items_this_month,
        'total_buy_requests': total_buy_requests,
        'approved_buy': approved_buy,
        'total_rent_requests': total_rent_requests,
        'approved_rent': approved_rent,
        'total_users': total_users,
        'new_users_this_month': new_users_this_month,
        'popular_categories': popular_categories,
        'recent_items': recent_items,
    })
