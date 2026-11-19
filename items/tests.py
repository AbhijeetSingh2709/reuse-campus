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
from .models import Item


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
        self.assertContains(response, 'Join Community')
        self.assertContains(response, 'Login')

        user = User.objects.create_user(username='member', password='password')
        self.client.force_login(user)
        response = self.client.get(reverse('home'))
        self.assertNotContains(response, 'Join Community')
        self.assertContains(response, 'Explore Items')
        self.assertContains(response, 'Browse Requests')
