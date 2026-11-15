from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import BoardRequest
from .forms import BoardRequestForm
from items.models import CATEGORY_CHOICES


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
def fulfill_request(request, pk):
    br = get_object_or_404(BoardRequest, pk=pk, posted_by=request.user)
    br.is_fulfilled = True
    br.save()
    messages.success(request, 'Marked as fulfilled!')
    return redirect('board')
