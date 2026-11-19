import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse


User = get_user_model()


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    EMAIL_HOST='',
    DEFAULT_FROM_EMAIL='noreply@example.test',
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage',
)
class PasswordResetFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='member',
            email='member@example.test',
            password='OldPassword!13579',
        )

    def test_password_reset_token_updates_password_and_unknown_email_is_generic(self):
        reset_url = reverse('password_reset')
        response = self.client.post(reset_url, {'email': self.user.email})
        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)

        match = re.search(
            r'http://testserver(/password-reset/[^/\s]+/[^/\s]+/)',
            mail.outbox[0].body,
        )
        self.assertIsNotNone(match)
        response = self.client.get(match.group(1), follow=True)
        self.assertEqual(response.status_code, 200)

        confirm_url = response.redirect_chain[-1][0]
        response = self.client.post(confirm_url, {
            'new_password1': 'NewPassword!24680',
            'new_password2': 'NewPassword!24680',
        })
        self.assertRedirects(response, reverse('password_reset_complete'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewPassword!24680'))

        response = self.client.post(reset_url, {'email': 'unknown@example.test'})
        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend',
        EMAIL_HOST='',
        DEFAULT_FROM_EMAIL='',
    )
    def test_unconfigured_smtp_is_explained_without_email_delivery(self):
        response = self.client.post(
            reverse('password_reset'),
            {'email': self.user.email},
        )

        self.assertEqual(response.status_code, 503)
        self.assertContains(response, 'EMAIL_HOST_PASSWORD', status_code=503)
        self.assertEqual(len(mail.outbox), 0)
