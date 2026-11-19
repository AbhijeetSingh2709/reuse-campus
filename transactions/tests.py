import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from items.models import Item
from messaging.models import Notification
from .models import BuyRequest, RentRequest


User = get_user_model()


@override_settings(
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage',
)
class RequesterEmailPrivacyTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='seller',
            email='seller@example.test',
            password='password',
        )
        self.requester = User.objects.create_user(
            username='requester',
            email='requester@example.test',
            password='password',
        )
        self.other_user = User.objects.create_user(
            username='other',
            email='other@example.test',
            password='password',
        )
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

    def test_requester_email_is_only_shown_in_the_listing_owners_dashboard(self):
        dashboard_url = reverse('dashboard')

        self.client.force_login(self.owner)
        owner_dashboard = self.client.get(dashboard_url)
        self.assertContains(owner_dashboard, 'mailto:requester@example.test')
        self.assertContains(owner_dashboard, 'requester@example.test')

        self.client.force_login(self.requester)
        requester_dashboard = self.client.get(dashboard_url)
        self.assertNotContains(requester_dashboard, 'requester@example.test')

        self.client.force_login(self.other_user)
        other_dashboard = self.client.get(dashboard_url)
        self.assertNotContains(other_dashboard, 'requester@example.test')

        public_detail = self.client.get(reverse('item_detail', args=[self.item.pk]))
        self.assertNotContains(public_detail, 'requester@example.test')
        public_profile = self.client.get(
            reverse('profile', args=[self.requester.username])
        )
        self.assertNotContains(public_profile, 'requester@example.test')

    def test_dashboard_requires_authentication_before_showing_requester_email(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('requester@example.test', response.url)


@override_settings(
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage',
)
class TransactionNotificationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner', password='password')
        self.requester = User.objects.create_user(username='requester', password='password')
        self.second_requester = User.objects.create_user(
            username='second-requester',
            password='password',
        )
        self.sell_item = Item.objects.create(
            owner=self.owner,
            title='Textbook',
            description='Course textbook.',
            category='books',
            listing_type='sell',
            price=100,
        )
        self.rent_item = Item.objects.create(
            owner=self.owner,
            title='Lab coat',
            description='Clean lab coat.',
            category='lab',
            listing_type='rent',
            rent_per_day=10,
        )

    def test_request_approval_and_auto_rejection_notify_each_requester_once(self):
        self.client.force_login(self.requester)
        response = self.client.post(
            reverse('request_to_buy', args=[self.sell_item.pk]),
            {'message': 'I would like to buy this.'},
        )
        self.assertEqual(response.status_code, 302)
        buy_request = BuyRequest.objects.get(item=self.sell_item, requester=self.requester)

        self.client.force_login(self.second_requester)
        self.client.post(
            reverse('request_to_buy', args=[self.sell_item.pk]),
            {'message': 'I would like this too.'},
        )
        second_request = BuyRequest.objects.get(
            item=self.sell_item,
            requester=self.second_requester,
        )

        self.assertEqual(
            Notification.objects.filter(
                recipient=self.owner,
                notification_type='item_requested',
            ).count(),
            2,
        )
        self.assertIn(
            f'#buy-request-{buy_request.pk}',
            Notification.objects.get(
                recipient=self.owner,
                notification_type='item_requested',
                content_type__model='buyrequest',
                object_id=buy_request.pk,
            ).target_url,
        )

        self.client.force_login(self.owner)
        approval_url = reverse('approve_buy_request', args=[buy_request.pk])
        response = self.client.post(approval_url)
        self.assertEqual(response.status_code, 302)
        response = self.client.post(approval_url)
        self.assertEqual(response.status_code, 302)

        buy_request.refresh_from_db()
        second_request.refresh_from_db()
        self.sell_item.refresh_from_db()
        self.assertEqual(buy_request.status, 'approved')
        self.assertEqual(second_request.status, 'rejected')
        self.assertEqual(self.sell_item.status, 'sold')
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.requester,
                notification_type='item_approved',
            ).count(),
            1,
        )
        approval_notification = Notification.objects.get(
            recipient=self.requester,
            notification_type='item_approved',
        )
        self.assertIn(f'#my-buy-request-{buy_request.pk}', approval_notification.target_url)
        self.assertEqual(
            Notification.objects.filter(
                recipient=self.second_requester,
                notification_type='item_rejected',
            ).count(),
            1,
        )

    def test_rent_request_rejection_and_return_notify_requester(self):
        start = datetime.date.today() + datetime.timedelta(days=1)
        end = start + datetime.timedelta(days=2)
        self.client.force_login(self.requester)
        response = self.client.post(
            reverse('request_to_rent', args=[self.rent_item.pk]),
            {
                'start_date': start.isoformat(),
                'end_date': end.isoformat(),
                'message': 'I need this for lab.',
            },
        )
        self.assertEqual(response.status_code, 302)
        rent_request = RentRequest.objects.get(item=self.rent_item, requester=self.requester)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.owner,
                notification_type='item_requested',
                content_type__model='rentrequest',
            ).exists()
        )

        self.client.force_login(self.owner)
        self.client.post(reverse('reject_rent_request', args=[rent_request.pk]))
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.requester,
                notification_type='item_rejected',
            ).exists()
        )

        rent_request.status = 'approved'
        rent_request.save(update_fields=['status'])
        self.rent_item.status = 'rented'
        self.rent_item.save(update_fields=['status'])
        response = self.client.post(reverse('mark_returned', args=[rent_request.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.requester,
                notification_type='transaction_status',
            ).exists()
        )
