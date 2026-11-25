from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.contrib import messages
from django.conf import settings
from django.contrib.auth.views import PasswordResetView
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.http import require_POST
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


def _send_verification_email(request, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    verify_url = request.build_absolute_uri(
        reverse('verify_email', args=[uid, token])
    )
    body = render_to_string('users/verify_email_body.txt', {
        'user': user,
        'verify_url': verify_url,
    })
    send_mail(
        subject='Verify your ReUse Campus email',
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            require_verification = getattr(settings, 'REQUIRE_EMAIL_VERIFICATION', False)
            user = form.save(commit=False)
            if require_verification:
                user.is_active = False
                user.is_email_verified = False
                user.save()
                _send_verification_email(request, user)
                return render(request, 'users/verify_email_sent.html', {'email': user.email})

            user.is_email_verified = True
            user.save()
            login(request, user)
            messages.success(request, f'Welcome to ReUse Campus, {user.first_name}!')
            return redirect('home')
    else:
        form = RegisterForm()
    return render(request, 'users/register.html', {'form': form})


def verify_email_view(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.is_email_verified = True
        user.save(update_fields=['is_active', 'is_email_verified'])
        login(request, user)
        messages.success(request, 'Your email has been verified. Welcome to ReUse Campus!')
        return redirect('home')

    messages.error(request, 'This verification link is invalid or has expired.')
    return redirect('login')


@require_POST
def resend_verification_view(request):
    email = request.POST.get('email', '').strip().lower()
    user = User.objects.filter(email__iexact=email, is_active=False).first()
    if user is not None:
        _send_verification_email(request, user)
    messages.info(request, 'If an unverified account exists for that email, a new verification link has been sent.')
    return render(request, 'users/verify_email_sent.html', {'email': email})


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
