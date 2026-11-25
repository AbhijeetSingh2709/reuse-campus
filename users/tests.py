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


@override_settings(
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage',
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    ALLOWED_EMAIL_DOMAINS=['*'],
    REQUIRE_EMAIL_VERIFICATION=False,
)
class EmailRegistrationTests(TestCase):
    def _payload(self, username, email):
        return {
            'username': username,
            'first_name': 'Asha',
            'last_name': 'Rao',
            'email': email,
            'password1': 'CampusPass!9876',
            'password2': 'CampusPass!9876',
        }

    def test_any_valid_email_can_register_and_duplicates_are_blocked(self):
        gmail_resp = self.client.post(reverse('register'), self._payload('asha1', 'asha@gmail.com'))
        self.assertRedirects(gmail_resp, reverse('home'))
        self.assertTrue(User.objects.filter(username='asha1', email='asha@gmail.com', is_active=True).exists())

        self.client.logout()
        edu_resp = self.client.post(reverse('register'), self._payload('asha2', 'asha@iitb.ac.in'))
        self.assertRedirects(edu_resp, reverse('home'))
        self.assertTrue(User.objects.filter(username='asha2', email='asha@iitb.ac.in').exists())

        self.client.logout()
        dup = self.client.post(reverse('register'), self._payload('asha3', 'ASHA@gmail.com'))
        self.assertEqual(dup.status_code, 200)
        self.assertContains(dup, 'An account with this email already exists.')

    @override_settings(REQUIRE_EMAIL_VERIFICATION=True)
    def test_email_verification_activates_any_valid_email_account(self):
        resp = self.client.post(reverse('register'), self._payload('asha_verify', 'asha.verify@gmail.com'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'asha.verify@gmail.com')
        user = User.objects.get(username='asha_verify')
        self.assertFalse(user.is_active)
        self.assertFalse(user.is_email_verified)
        self.assertEqual(len(mail.outbox), 1)

        match = re.search(r'http://testserver(/verify-email/[^/\s]+/[^/\s]+/)', mail.outbox[0].body)
        self.assertIsNotNone(match)
        verify_resp = self.client.get(match.group(1))
        self.assertRedirects(verify_resp, reverse('home'))
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertTrue(user.is_email_verified)

    @override_settings(ALLOWED_EMAIL_DOMAINS=['.edu', '.ac.in'])
    def test_optional_domain_restriction_still_works_when_configured(self):
        bad = self.client.post(reverse('register'), self._payload('asha_bad', 'asha@gmail.com'))
        self.assertEqual(bad.status_code, 200)
        self.assertContains(bad, 'Please use an allowed email domain')
        self.assertFalse(User.objects.filter(username='asha_bad').exists())
