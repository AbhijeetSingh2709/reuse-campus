import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from items.models import Item
from messaging.models import Conversation, Notification
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


@override_settings(
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage',
)
class ActionableNotificationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner', password='password')
        self.requester = User.objects.create_user(username='requester', password='password')
        self.other_user = User.objects.create_user(username='other', password='password')
        self.item = Item.objects.create(
            owner=self.owner,
            title='Physics textbook',
            description='A useful course book.',
            category='books',
            listing_type='sell',
            price=250,
        )

    def _create_request_notification(self):
        self.client.force_login(self.requester)
        response = self.client.post(
            reverse('request_to_buy', args=[self.item.pk]),
            {'message': 'I need this book.'},
        )
        self.assertEqual(response.status_code, 302)
        item_request = BuyRequest.objects.get(item=self.item, requester=self.requester)
        notification = Notification.objects.get(
            recipient=self.owner,
            notification_type='item_requested',
            object_id=item_request.pk,
        )
        return item_request, notification

    def test_owner_can_approve_from_action_centre_and_notification_updates(self):
        item_request, notification = self._create_request_notification()
        self.client.force_login(self.owner)

        page = self.client.get(reverse('notifications'))
        self.assertContains(page, 'Approve')
        self.assertContains(page, 'Reject')
        self.assertContains(page, 'Message')

        response = self.client.post(
            reverse('approve_buy_request', args=[item_request.pk]),
            {'notification_id': notification.pk},
        )
        self.assertRedirects(response, reverse('notifications'))
        item_request.refresh_from_db()
        notification.refresh_from_db()
        self.item.refresh_from_db()
        self.assertEqual(item_request.status, 'approved')
        self.assertEqual(self.item.status, 'sold')
        self.assertTrue(notification.is_read)

        page = self.client.get(reverse('notifications'))
        self.assertContains(page, 'Approved')
        self.assertNotContains(page, f'name="notification_id" value="{notification.pk}"')
        self.assertNotContains(page, reverse('approve_buy_request', args=[item_request.pk]))
        self.assertNotContains(page, reverse('reject_buy_request', args=[item_request.pk]))

    def test_owner_can_reject_from_action_centre(self):
        item_request, notification = self._create_request_notification()
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse('reject_buy_request', args=[item_request.pk]),
            {'notification_id': notification.pk},
        )

        self.assertRedirects(response, reverse('notifications'))
        item_request.refresh_from_db()
        notification.refresh_from_db()
        self.assertEqual(item_request.status, 'rejected')
        self.assertTrue(notification.is_read)

    def test_another_user_cannot_act_through_an_owner_notification(self):
        item_request, notification = self._create_request_notification()
        self.client.force_login(self.other_user)

        response = self.client.post(
            reverse('approve_buy_request', args=[item_request.pk]),
            {'notification_id': notification.pk},
        )

        self.assertEqual(response.status_code, 302)
        item_request.refresh_from_db()
        notification.refresh_from_db()
        self.item.refresh_from_db()
        self.assertEqual(item_request.status, 'pending')
        self.assertEqual(self.item.status, 'available')
        self.assertFalse(notification.is_read)

    def test_invalid_notification_reference_does_not_break_existing_request_action(self):
        item_request, notification = self._create_request_notification()
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse('approve_buy_request', args=[item_request.pk]),
            {'notification_id': 'invalid'},
        )

        self.assertRedirects(response, reverse('dashboard'))
        item_request.refresh_from_db()
        notification.refresh_from_db()
        self.assertEqual(item_request.status, 'approved')
        self.assertFalse(notification.is_read)

    def test_requester_status_notification_opens_item_details_and_seller_chat(self):
        item_request, _ = self._create_request_notification()
        self.client.force_login(self.owner)
        self.client.post(reverse('approve_buy_request', args=[item_request.pk]))
        notification = Notification.objects.get(
            recipient=self.requester,
            notification_type='item_approved',
            object_id=item_request.pk,
        )
        self.client.force_login(self.requester)

        page = self.client.get(reverse('notifications'))
        self.assertContains(page, 'View Details')
        self.assertContains(page, 'Message')

        response = self.client.get(
            f"{reverse('open_notification', args=[notification.pk])}?action=details"
        )
        self.assertRedirects(response, reverse('item_detail', args=[self.item.pk]))
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)

        response = self.client.get(
            f"{reverse('open_notification', args=[notification.pk])}?action=message"
        )
        self.assertEqual(
            response.url,
            reverse(
                'start_conversation_item',
                args=[self.owner.username, self.item.pk],
            ),
        )

    def test_returned_rental_notification_has_details_and_message_actions(self):
        rent_item = Item.objects.create(
            owner=self.owner,
            title='Lab coat',
            description='Clean lab coat.',
            category='lab',
            listing_type='rent',
            rent_per_day=10,
            status='rented',
        )
        start = datetime.date.today() + datetime.timedelta(days=1)
        rent_request = RentRequest.objects.create(
            item=rent_item,
            requester=self.requester,
            start_date=start,
            end_date=start + datetime.timedelta(days=2),
            status='approved',
        )
        self.client.force_login(self.owner)
        self.client.post(reverse('mark_returned', args=[rent_request.pk]))
        notification = Notification.objects.get(
            recipient=self.requester,
            notification_type='transaction_status',
            object_id=rent_request.pk,
        )
        self.client.force_login(self.requester)

        page = self.client.get(reverse('notifications'))
        self.assertContains(page, 'View Details')
        self.assertContains(page, 'Message')
        response = self.client.get(
            f"{reverse('open_notification', args=[notification.pk])}?action=details"
        )
        self.assertRedirects(response, reverse('item_detail', args=[rent_item.pk]))
        response = self.client.get(
            f"{reverse('open_notification', args=[notification.pk])}?action=message"
        )
        self.assertEqual(
            response.url,
            reverse(
                'start_conversation_item',
                args=[self.owner.username, rent_item.pk],
            ),
        )

    def test_message_action_marks_notification_read_and_starts_private_chat(self):
        _, notification = self._create_request_notification()
        self.client.force_login(self.owner)

        response = self.client.get(
            f"{reverse('open_notification', args=[notification.pk])}?action=message"
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse(
                'start_conversation_item',
                args=[self.requester.username, self.item.pk],
            ),
        )
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)
        start_response = self.client.get(response.url)
        self.assertEqual(start_response.status_code, 302)
        self.assertTrue(start_response.url.startswith('/messages/'))
        self.assertTrue(
            Conversation.objects.filter(
                item=self.item,
                participants=self.owner,
            ).filter(participants=self.requester).exists()
        )


@override_settings(
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage',
    RAZORPAY_KEY_ID='',
    RAZORPAY_KEY_SECRET='',
)
class ReRequestAndDepositTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner2', password='password')
        self.requester = User.objects.create_user(username='renter2', password='password')
        self.other = User.objects.create_user(username='other2', password='password')
        self.sell_item = Item.objects.create(
            owner=self.owner,
            title='Graphing Calc',
            description='TI-84',
            category='calculators',
            listing_type='sell',
            price=1200,
        )
        self.rent_item = Item.objects.create(
            owner=self.owner,
            title='DSLR Camera',
            description='For fest coverage',
            category='electronics',
            listing_type='rent',
            rent_per_day=300,
            security_deposit=1000,
        )

    def test_user_can_rerequest_after_rejection_but_not_while_pending(self):
        self.client.force_login(self.requester)
        self.client.post(reverse('request_to_buy', args=[self.sell_item.pk]), {'message': 'First try'})
        first_req = BuyRequest.objects.get(item=self.sell_item, requester=self.requester)

        # Duplicate while pending is blocked
        self.client.post(reverse('request_to_buy', args=[self.sell_item.pk]), {'message': 'Dup'})
        self.assertEqual(BuyRequest.objects.filter(item=self.sell_item, requester=self.requester).count(), 1)

        # Reject first request
        self.client.force_login(self.owner)
        self.client.post(reverse('reject_buy_request', args=[first_req.pk]))

        # Same user can re-request after rejection
        self.client.force_login(self.requester)
        resp = self.client.post(reverse('request_to_buy', args=[self.sell_item.pk]), {'message': 'Second try'})
        self.assertRedirects(resp, reverse('item_detail', args=[self.sell_item.pk]))
        self.assertEqual(BuyRequest.objects.filter(item=self.sell_item, requester=self.requester).count(), 2)

    def test_rental_deposit_escrow_hold_and_auto_release_on_return(self):
        start = datetime.date.today() + datetime.timedelta(days=1)
        end = start + datetime.timedelta(days=3)

        self.client.force_login(self.requester)
        self.client.post(reverse('request_to_rent', args=[self.rent_item.pk]), {
            'start_date': start.isoformat(),
            'end_date': end.isoformat(),
            'message': 'Need for weekend',
        })
        rent_req = RentRequest.objects.get(item=self.rent_item, requester=self.requester)
        self.assertEqual(rent_req.deposit_amount, 1000)
        self.assertEqual(rent_req.deposit_status, 'not_required')

        self.client.force_login(self.owner)
        self.client.post(reverse('approve_rent_request', args=[rent_req.pk]))
        rent_req.refresh_from_db()
        self.assertEqual(rent_req.status, 'approved')
        self.assertEqual(rent_req.deposit_status, 'pending')

        # Other user cannot pay deposit
        self.client.force_login(self.other)
        self.client.post(reverse('pay_rent_deposit', args=[rent_req.pk]))
        rent_req.refresh_from_db()
        self.assertEqual(rent_req.deposit_status, 'pending')

        # Requester holds deposit in escrow
        self.client.force_login(self.requester)
        pay_page = self.client.get(reverse('pay_rent_deposit', args=[rent_req.pk]))
        self.assertContains(pay_page, '1000')
        pay_resp = self.client.post(reverse('pay_rent_deposit', args=[rent_req.pk]))
        self.assertRedirects(pay_resp, reverse('dashboard'))
        rent_req.refresh_from_db()
        self.assertEqual(rent_req.deposit_status, 'held')
        self.assertTrue(rent_req.payment_reference.startswith('ESCROW-'))
        self.assertIsNotNone(rent_req.deposit_paid_at)

        # Owner marks returned -> deposit auto-released
        self.client.force_login(self.owner)
        ret_resp = self.client.post(reverse('mark_returned', args=[rent_req.pk]))
        self.assertRedirects(ret_resp, reverse('dashboard'))
        rent_req.refresh_from_db()
        self.rent_item.refresh_from_db()
        self.assertEqual(rent_req.status, 'returned')
        self.assertEqual(rent_req.deposit_status, 'released')
        self.assertIsNotNone(rent_req.deposit_released_at)
        self.assertEqual(self.rent_item.status, 'available')

    @override_settings(RAZORPAY_KEY_ID='rzp_test_123', RAZORPAY_KEY_SECRET='secret_xyz')
    def test_razorpay_signature_verification(self):
        import hashlib
        import hmac

        start = datetime.date.today() + datetime.timedelta(days=1)
        rent_req = RentRequest.objects.create(
            item=self.rent_item,
            requester=self.requester,
            start_date=start,
            end_date=start + datetime.timedelta(days=2),
            status='approved',
            deposit_amount=1000,
            deposit_status='pending',
        )
        self.client.force_login(self.requester)
        bad_resp = self.client.post(reverse('pay_rent_deposit', args=[rent_req.pk]), {
            'razorpay_payment_id': 'pay_123',
            'razorpay_order_id': 'order_123',
            'razorpay_signature': 'bad_sig',
        })
        self.assertRedirects(bad_resp, reverse('pay_rent_deposit', args=[rent_req.pk]))
        rent_req.refresh_from_db()
        self.assertEqual(rent_req.deposit_status, 'pending')

        valid_sig = hmac.new(
            b'secret_xyz', b'order_123|pay_123', hashlib.sha256
        ).hexdigest()
        good_resp = self.client.post(reverse('pay_rent_deposit', args=[rent_req.pk]), {
            'razorpay_payment_id': 'pay_123',
            'razorpay_order_id': 'order_123',
            'razorpay_signature': valid_sig,
        })
        self.assertRedirects(good_resp, reverse('dashboard'))
        rent_req.refresh_from_db()
        self.assertEqual(rent_req.deposit_status, 'held')
        self.assertEqual(rent_req.payment_reference, 'pay_123')
