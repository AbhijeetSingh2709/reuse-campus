from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User


class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=50, required=True, label='First Name')
    last_name = forms.CharField(max_length=50, required=True, label='Last Name')

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if not email:
            raise forms.ValidationError('Email is required.')
        from django.conf import settings
        allowed_domains = [
            d.strip().lower()
            for d in getattr(settings, 'ALLOWED_EMAIL_DOMAINS', [])
            if d.strip()
        ]
        if allowed_domains and '*' not in allowed_domains:
            domain = email.split('@')[-1] if '@' in email else ''
            is_allowed = any(
                domain.endswith(allowed) if allowed.startswith('.') else domain == allowed
                for allowed in allowed_domains
            )
            if not is_allowed:
                raise forms.ValidationError(
                    f'Please use an allowed email domain ({", ".join(allowed_domains)}).'
                )
        # Check uniqueness
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email


class LoginForm(AuthenticationForm):
    pass


class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'bio', 'profile_pic']

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        qs = User.objects.filter(email__iexact=email)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email
