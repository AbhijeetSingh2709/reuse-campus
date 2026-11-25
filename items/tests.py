from decimal import Decimal
from io import BytesIO
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.test.utils import override_settings
from django.urls import reverse
from PIL import Image

from .forms import ItemForm
from .models import Item, ItemImage


User = get_user_model()


def image_upload(name, color):
    image = Image.new('RGB', (2, 2), color=color)
    content = BytesIO()
    image.save(content, format='PNG')
    return SimpleUploadedFile(name, content.getvalue(), content_type='image/png')


@override_settings(
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage',
)
class ListingFeatureTests(TestCase):
    def setUp(self):
        self.media_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.media_dir.cleanup)
        media_settings = override_settings(MEDIA_ROOT=self.media_dir.name)
        media_settings.enable()
        self.addCleanup(media_settings.disable)
        self.owner = User.objects.create_user(username='seller', password='password')
        self.client.force_login(self.owner)

    def listing_data(self, title='Calculator'):
        return {
            'title': title,
            'description': 'A working calculator.',
            'category': 'calculators',
            'listing_type': 'sell',
            'price': '500',
            'rent_per_day': '',
        }

    def create_listing(self, title='Calculator', upload=None):
        data = self.listing_data(title)
        if upload:
            data['image'] = upload
        response = self.client.post(reverse('post_item'), data)
        self.assertEqual(response.status_code, 302)
        return Item.objects.get(title=title)

    def test_listing_image_upload_is_saved_and_served(self):
        item = self.create_listing(upload=image_upload('calculator.png', 'red'))

        self.assertTrue(item.image.storage.exists(item.image.name))
        self.assertContains(self.client.get(reverse('item_detail', args=[item.pk])), item.image.url)
        with item.image.open('rb') as uploaded_image:
            self.assertEqual(Image.open(uploaded_image).format, 'PNG')

    def test_edit_can_replace_preview_and_remove_listing_image(self):
        item = self.create_listing(upload=image_upload('original.png', 'red'))
        old_image_name = item.image.name

        edit_url = reverse('edit_item', args=[item.pk])
        edit_page = self.client.get(edit_url)
        self.assertContains(edit_page, 'id="photo-preview"')
        self.assertContains(edit_page, item.image.url)

        replacement = image_upload('replacement.png', 'blue')
        response = self.client.post(edit_url, {
            **self.listing_data('Calculator'),
            'image': replacement,
        })
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertNotEqual(item.image.name, old_image_name)
        self.assertFalse(item.image.storage.exists(old_image_name))
        self.assertTrue(item.image.storage.exists(item.image.name))

        replacement_name = item.image.name
        response = self.client.post(edit_url, {
            **self.listing_data('Calculator'),
            'remove_image': 'on',
        })
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertFalse(item.image)
        self.assertFalse(item.image.storage.exists(replacement_name))

    def test_price_fields_increment_by_one_and_reject_fractional_or_negative_rupees(self):
        form = ItemForm()
        self.assertEqual(form.fields['price'].widget.attrs['step'], '1')
        self.assertEqual(form.fields['rent_per_day'].widget.attrs['step'], '1')

        for invalid_price in ('10.50', '-1'):
            data = self.listing_data()
            data['price'] = invalid_price
            with self.subTest(price=invalid_price):
                form = ItemForm(data)
                self.assertFalse(form.is_valid())
                self.assertIn('price', form.errors)

        valid = ItemForm({**self.listing_data(), 'price': '0'})
        self.assertTrue(valid.is_valid(), valid.errors)
        self.assertEqual(valid.cleaned_data['price'], Decimal('0'))


@override_settings(
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage',
)
class HomeAuthenticationCtaTests(TestCase):
    def test_homepage_ctas_match_login_state(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Join community')
        self.assertContains(response, 'Log in')

        user = User.objects.create_user(username='member', password='password')
        self.client.force_login(user)
        response = self.client.get(reverse('home'))
        self.assertNotContains(response, 'Join community')
        self.assertContains(response, 'Browse all')
        self.assertContains(response, 'List an item')


@override_settings(
    STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage',
)
class MarketplaceEnhancementTests(TestCase):
    def setUp(self):
        self.media_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.media_dir.cleanup)
        media_settings = override_settings(MEDIA_ROOT=self.media_dir.name)
        media_settings.enable()
        self.addCleanup(media_settings.disable)

        self.owner = User.objects.create_user(username='owner', password='password')
        self.other_user = User.objects.create_user(username='buyer', password='password')
        self.staff_user = User.objects.create_user(username='staff', password='password', is_staff=True)

    def test_explore_filters_by_price_range_and_condition_and_paginates(self):
        for i in range(18):
            Item.objects.create(
                owner=self.owner,
                title=f'Item {i}',
                description='Campus item',
                category='books',
                listing_type='sell',
                price=100 + (i * 10),
                condition='like_new' if i % 2 == 0 else 'fair',
            )

        page1 = self.client.get(reverse('explore'))
        self.assertEqual(page1.status_code, 200)
        self.assertEqual(len(page1.context['items']), 16)
        self.assertContains(page1, 'Page 1 of 2')

        page2 = self.client.get(reverse('explore') + '?page=2')
        self.assertEqual(len(page2.context['items']), 2)

        filtered = self.client.get(
            reverse('explore'),
            {'min_price': '200', 'max_price': '250', 'condition': 'like_new'},
        )
        titles = [item.title for item in filtered.context['items']]
        self.assertEqual(set(titles), {'Item 10', 'Item 12', 'Item 14'})

        invalid_price = self.client.get(reverse('explore'), {'min_price': 'abc'})
        self.assertEqual(invalid_price.status_code, 200)

    def test_multiple_images_lightbox_and_cleanup_on_delete(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse('post_item'), {
            'title': 'Multi Photo Bike',
            'description': 'Good cycle',
            'category': 'other',
            'listing_type': 'sell',
            'price': '2500',
            'condition': 'good',
            'image': image_upload('main.png', 'red'),
            'extra_images-TOTAL_FORMS': '2',
            'extra_images-INITIAL_FORMS': '0',
            'extra_images-MIN_NUM_FORMS': '0',
            'extra_images-MAX_NUM_FORMS': '5',
            'extra_images-0-image': image_upload('angle1.png', 'green'),
            'extra_images-1-image': image_upload('angle2.png', 'blue'),
        })
        self.assertEqual(response.status_code, 302)
        item = Item.objects.get(title='Multi Photo Bike')
        self.assertEqual(item.extra_images.count(), 2)
        extra_names = [img.image.name for img in item.extra_images.all()]

        detail = self.client.get(reverse('item_detail', args=[item.pk]))
        self.assertContains(detail, 'id="lightbox"')
        self.assertContains(detail, 'Good')
        for img in item.extra_images.all():
            self.assertContains(detail, img.image_url)

        self.client.post(reverse('delete_item', args=[item.pk]))
        self.assertFalse(Item.objects.filter(pk=item.pk).exists())
        for name in extra_names:
            self.assertFalse(ItemImage._meta.get_field('image').storage.exists(name))

    def test_wishlist_toggle_ajax_and_page(self):
        item = Item.objects.create(
            owner=self.owner,
            title='Lab Coat',
            description='White lab coat',
            category='lab',
            listing_type='sell',
            price=300,
        )
        self.client.force_login(self.other_user)
        toggle_url = reverse('toggle_wishlist', args=[item.pk])

        resp = self.client.post(toggle_url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['saved'], True)

        wishlist_page = self.client.get(reverse('wishlist'))
        self.assertContains(wishlist_page, 'Lab Coat')

        resp = self.client.post(toggle_url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.json()['saved'], False)
        self.assertNotContains(self.client.get(reverse('wishlist')), 'Lab Coat')

    def test_non_owner_cannot_edit_or_delete_and_non_staff_cannot_view_admin_dashboard(self):
        item = Item.objects.create(
            owner=self.owner,
            title='Protected Book',
            description='Book',
            category='books',
            listing_type='sell',
            price=150,
        )
        self.client.force_login(self.other_user)
        self.client.post(reverse('edit_item', args=[item.pk]), {
            'title': 'Hacked',
            'description': 'Hacked',
            'category': 'books',
            'listing_type': 'sell',
            'price': '1',
        })
        item.refresh_from_db()
        self.assertEqual(item.title, 'Protected Book')

        self.client.post(reverse('delete_item', args=[item.pk]))
        self.assertTrue(Item.objects.filter(pk=item.pk).exists())

        self.assertEqual(self.client.get(reverse('admin_dashboard')).status_code, 302)
        self.client.force_login(self.staff_user)
        self.assertEqual(self.client.get(reverse('admin_dashboard')).status_code, 200)
