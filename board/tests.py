from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from messaging.models import Conversation, Notification
from .models import BoardRequest


User = get_user_model()


@override_settings(
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage',
)
class BoardMessagingTests(TestCase):
    def setUp(self):
        self.requester = User.objects.create_user(
            username='requester',
            email='requester@example.test',
            password='password',
        )
        self.responder = User.objects.create_user(
            username='responder',
            email='responder@example.test',
            password='password',
        )
        self.other_user = User.objects.create_user(
            username='other',
            email='other@example.test',
            password='password',
        )
        self.board_request = BoardRequest.objects.create(
            posted_by=self.requester,
            title='Looking for a calculator',
            description='Scientific calculator for exams.',
            category='calculators',
        )

    def start_url(self):
        return reverse('start_board_conversation', args=[self.board_request.pk])

    def test_authenticated_responder_creates_one_request_linked_conversation(self):
        self.client.force_login(self.responder)
        first_response = self.client.get(self.start_url())
        second_response = self.client.get(self.start_url())

        self.assertEqual(first_response.status_code, 302)
        self.assertEqual(first_response.url, second_response.url)
        conversation = Conversation.objects.get(board_request=self.board_request)
        self.assertEqual(conversation.board_responder, self.responder)
        self.assertSetEqual(
            set(conversation.participants.values_list('pk', flat=True)),
            {self.requester.pk, self.responder.pk},
        )
        self.assertEqual(Conversation.objects.filter(board_request=self.board_request).count(), 1)
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.requester,
                notification_type='board_response',
            ).count(),
            1,
        )

    def test_only_conversation_participants_can_view_messages_or_email(self):
        self.client.force_login(self.responder)
        self.client.get(self.start_url())
        conversation = Conversation.objects.get(board_request=self.board_request)

        self.client.force_login(self.requester)
        response = self.client.get(reverse('conversation', args=[conversation.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.responder.email)
        self.assertContains(response, self.board_request.title)

        self.client.force_login(self.other_user)
        response = self.client.get(reverse('conversation', args=[conversation.pk]))
        self.assertEqual(response.status_code, 404)

        response = self.client.get(reverse('board'))
        self.assertNotContains(response, self.responder.email)

    def test_only_request_creator_can_fulfill_and_fulfillment_notifies_responder(self):
        self.client.force_login(self.responder)
        self.client.get(self.start_url())

        fulfill_url = reverse('fulfill_request', args=[self.board_request.pk])
        response = self.client.post(fulfill_url)
        self.assertEqual(response.status_code, 404)
        self.board_request.refresh_from_db()
        self.assertFalse(self.board_request.is_fulfilled)

        self.client.force_login(self.requester)
        self.assertEqual(self.client.get(fulfill_url).status_code, 405)
        response = self.client.post(fulfill_url)
        self.assertEqual(response.status_code, 302)
        self.board_request.refresh_from_db()
        self.assertTrue(self.board_request.is_fulfilled)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.responder,
                notification_type='request_fulfilled',
            ).exists()
        )

    def test_login_is_required_to_respond_and_owner_cannot_respond_to_own_post(self):
        response = self.client.get(self.start_url())
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

        self.client.force_login(self.requester)
        response = self.client.get(self.start_url())
        self.assertRedirects(response, reverse('board'))
        self.assertFalse(Conversation.objects.filter(board_request=self.board_request).exists())
