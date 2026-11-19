from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.test import RequestFactory
from django.urls import reverse

from items.models import Item
from transactions.models import BuyRequest

from .context_processors import unread_messages
from .models import Conversation, Message, Notification


User = get_user_model()


@override_settings(
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage',
)
class MessagingFlowTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='seller', password='password')
        self.requester = User.objects.create_user(username='requester', password='password')
        self.other_user = User.objects.create_user(username='other', password='password')
        self.item = Item.objects.create(
            owner=self.owner,
            title='Calculator',
            description='A working calculator.',
            category='calculators',
            listing_type='sell',
            price=500,
        )
        self.buy_request = BuyRequest.objects.create(
            item=self.item,
            requester=self.requester,
        )

    def start_url(self, username):
        return reverse(
            'start_conversation_item',
            args=[username, self.item.pk],
        )

    def test_requester_can_message_seller_and_seller_can_reply(self):
        self.client.force_login(self.requester)
        response = self.client.get(self.start_url(self.owner.username))
        self.assertEqual(response.status_code, 302)
        conversation = Conversation.objects.get(item=self.item)

        response = self.client.post(
            reverse('conversation', args=[conversation.pk]),
            {'body': 'Is the calculator still available?'},
        )
        self.assertRedirects(response, reverse('conversation', args=[conversation.pk]))
        message = Message.objects.get(conversation=conversation)
        self.assertEqual(message.sender, self.requester)
        self.assertFalse(message.is_read)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.owner,
                notification_type='message',
                content_type__model='conversation',
                object_id=conversation.pk,
            ).exists()
        )

        self.client.force_login(self.owner)
        inbox = self.client.get(reverse('inbox'))
        self.assertContains(inbox, 'class="nav-unread">1</span>', count=2)
        self.assertContains(inbox, 'class="unread-badge">1</span>')
        self.assertContains(inbox, 'Is the calculator still available?')
        counts = unread_messages(self._request_for(self.owner))
        self.assertEqual(counts['unread_message_count'], 1)
        self.assertEqual(counts['unread_notification_count'], 1)

        response = self.client.get(reverse('conversation', args=[conversation.pk]))
        self.assertEqual(response.status_code, 200)
        message.refresh_from_db()
        self.assertTrue(message.is_read)
        counts = unread_messages(self._request_for(self.owner))
        self.assertEqual(counts['unread_message_count'], 0)
        self.assertEqual(counts['unread_notification_count'], 1)

        response = self.client.post(
            reverse('conversation', args=[conversation.pk]),
            {'body': 'Yes, it is available.'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Message.objects.count(), 2)

    def test_seller_can_start_conversation_with_a_requester(self):
        self.client.force_login(self.owner)

        response = self.client.get(self.start_url(self.requester.username))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Conversation.objects.filter(item=self.item).exists())

    def test_seller_cannot_start_item_conversation_with_unrelated_user(self):
        self.client.force_login(self.owner)

        response = self.client.get(self.start_url(self.other_user.username))

        self.assertRedirects(response, reverse('dashboard'))
        self.assertFalse(Conversation.objects.filter(item=self.item).exists())

    def test_nonparticipant_cannot_read_or_send_messages(self):
        conversation = Conversation.objects.create(item=self.item)
        conversation.participants.add(self.owner, self.requester)
        self.client.force_login(self.other_user)

        response = self.client.get(reverse('conversation', args=[conversation.pk]))
        self.assertEqual(response.status_code, 404)

        response = self.client.post(
            reverse('conversation', args=[conversation.pk]),
            {'body': 'Private message'},
        )
        self.assertEqual(response.status_code, 404)
        self.assertFalse(Message.objects.filter(conversation=conversation).exists())

    @staticmethod
    def _request_for(user):
        request = RequestFactory().get('/')
        request.user = user
        return request


@override_settings(
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage',
)
class NotificationAccessTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner', password='password')
        self.other_user = User.objects.create_user(username='other', password='password')
        self.owner_notification = Notification.objects.create(
            recipient=self.owner,
            notification_type='message',
            message='Owner private notification',
            target_url=reverse('inbox'),
            dedupe_key='owner-event',
        )
        self.other_notification = Notification.objects.create(
            recipient=self.other_user,
            notification_type='item_requested',
            message="Other user's notification",
            target_url=reverse('dashboard'),
            dedupe_key='other-event',
        )

    def test_user_sees_and_marks_only_their_own_notifications(self):
        self.client.force_login(self.other_user)
        response = self.client.get(reverse('notifications'))
        self.assertContains(response, 'Other user&#x27;s notification')
        self.assertNotContains(response, 'Owner private notification')

        response = self.client.get(
            reverse('open_notification', args=[self.owner_notification.pk])
        )
        self.assertEqual(response.status_code, 404)
        response = self.client.post(
            reverse('mark_notification_read', args=[self.owner_notification.pk])
        )
        self.assertEqual(response.status_code, 404)

        response = self.client.post(
            reverse('mark_notification_read', args=[self.other_notification.pk])
        )
        self.assertRedirects(response, reverse('notifications'))
        self.other_notification.refresh_from_db()
        self.owner_notification.refresh_from_db()
        self.assertTrue(self.other_notification.is_read)
        self.assertFalse(self.owner_notification.is_read)

    def test_opening_notification_marks_read_and_uses_its_destination(self):
        self.client.force_login(self.owner)

        response = self.client.get(
            reverse('open_notification', args=[self.owner_notification.pk])
        )

        self.assertRedirects(response, reverse('inbox'))
        self.owner_notification.refresh_from_db()
        self.assertTrue(self.owner_notification.is_read)

    def test_notification_count_updates_when_marked_and_hides_at_zero(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse('home'))
        self.assertContains(response, "href=\"/messages/notifications/\"")
        self.assertContains(response, 'class="nav-unread">1</span>')

        response = self.client.post(
            reverse('mark_all_notifications_read'),
        )
        self.assertRedirects(response, reverse('notifications'))
        self.owner_notification.refresh_from_db()
        self.other_notification.refresh_from_db()
        self.assertTrue(self.owner_notification.is_read)
        self.assertFalse(self.other_notification.is_read)
        response = self.client.get(reverse('home'))
        self.assertNotContains(response, 'class="nav-unread"')

        unread = Notification.objects.create(
            recipient=self.owner,
            notification_type='message',
            message='Another notification',
            target_url=reverse('inbox'),
            dedupe_key='owner-event-2',
        )
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'class="nav-unread">1</span>')
        self.assertFalse(unread.is_read)

    def test_notifications_persist_across_logout(self):
        self.client.force_login(self.owner)
        self.client.logout()
        self.client.force_login(self.owner)

        response = self.client.get(reverse('notifications'))

        self.assertContains(response, 'Owner private notification')
