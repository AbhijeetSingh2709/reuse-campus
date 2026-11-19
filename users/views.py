from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.contrib.auth.views import PasswordResetView
from django.urls import reverse_lazy
from .forms import RegisterForm, LoginForm, ProfileEditForm
from .models import User
from items.models import Item


class CampusPasswordResetView(PasswordResetView):
    template_name = 'users/password_reset_form.html'
    email_template_name = 'users/password_reset_email.html'
    subject_template_name = 'users/password_reset_subject.txt'
    success_url = reverse_lazy('password_reset_done')

    def email_backend_available(self):
        backend = settings.EMAIL_BACKEND
        if backend.endswith(('console.EmailBackend', 'locmem.EmailBackend')):
            return True
        if backend != 'django.core.mail.backends.smtp.EmailBackend':
            return True
        return bool(
            settings.EMAIL_HOST
            and settings.EMAIL_FROM_ADDRESS_CONFIGURED
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['email_backend_is_console'] = settings.EMAIL_BACKEND.endswith(
            'console.EmailBackend'
        )
        context['email_delivery_configured'] = self.email_backend_available()
        return context

    def form_valid(self, form):
        if not self.email_backend_available():
            return self.render_to_response(
                self.get_context_data(
                    form=form,
                    email_delivery_unavailable=True,
                ),
                status=503,
            )
        return super().form_valid(form)


def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Welcome to ReUse Campus, {user.first_name}!')
            return redirect('home')
    else:
        form = RegisterForm()
    return render(request, 'users/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Welcome back, {user.first_name or user.username}!')
            next_url = request.GET.get('next', 'home')
            return redirect(next_url)
    else:
        form = LoginForm()
    return render(request, 'users/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('home')


def profile_view(request, username):
    profile_user = get_object_or_404(User, username=username)
    listings = Item.objects.filter(owner=profile_user).order_by('-created_at')
    return render(request, 'users/profile.html', {
        'profile_user': profile_user,
        'listings': listings,
    })


@login_required
def edit_profile_view(request):
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('profile', username=request.user.username)
    else:
        form = ProfileEditForm(instance=request.user)
    return render(request, 'users/edit_profile.html', {'form': form})
