import os

from django import forms
from django.core.files.uploadedfile import UploadedFile
from django.forms import modelformset_factory
from PIL import Image, UnidentifiedImageError

from .models import Item, ItemImage

MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}


def _validate_uploaded_image(image):
    """Validate uploaded image extension, size, and readable contents."""
    if not isinstance(image, UploadedFile):
        return image

    extension = os.path.splitext(image.name or '')[1].lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise forms.ValidationError('Upload a JPG, PNG, WEBP, or GIF photo.')

    if image.size > MAX_IMAGE_BYTES:
        raise forms.ValidationError('Photo must be 5 MB or smaller.')

    try:
        image.seek(0)
        with Image.open(image) as opened:
            opened.verify()
        image.seek(0)
    except (UnidentifiedImageError, OSError, ValueError):
        raise forms.ValidationError('This file could not be read as an image.')

    return image


class ItemForm(forms.ModelForm):
    remove_image = forms.BooleanField(
        required=False,
        label='Remove current photo',
    )

    class Meta:
        model = Item
        fields = [
            'title', 'description', 'category', 'listing_type',
            'price', 'rent_per_day', 'security_deposit', 'condition', 'image',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'listing_type': forms.Select(attrs={'id': 'id_listing_type'}),
            'price': forms.NumberInput(attrs={
                'step': '1',
                'min': '0',
                'inputmode': 'numeric',
                'placeholder': 'e.g. 500',
            }),
            'rent_per_day': forms.NumberInput(attrs={
                'step': '1',
                'min': '0',
                'inputmode': 'numeric',
                'placeholder': 'e.g. 20',
            }),
            'security_deposit': forms.NumberInput(attrs={
                'step': '1',
                'min': '0',
                'inputmode': 'numeric',
                'placeholder': 'Optional, e.g. 200',
            }),
            'image': forms.FileInput(attrs={
                'accept': 'image/jpeg,image/png,image/gif,image/webp',
            }),
        }
        help_texts = {
            'price': 'Whole rupees only. The arrows change the price by ₹1.',
            'rent_per_day': 'Whole rupees only. The arrows change the price by ₹1.',
            'security_deposit': 'Optional refundable deposit held until return (whole rupees).',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['condition'].required = False

    def clean_condition(self):
        return self.cleaned_data.get('condition') or 'good'

    def _reject_fractional_or_negative(self, field_name, label):
        value = self.cleaned_data.get(field_name)
        if value is None:
            return
        if value < 0:
            self.add_error(field_name, f'{label} cannot be negative.')
            return
        if value != value.to_integral_value():
            self.add_error(field_name, f'{label} must be a whole number of rupees.')

    def clean_image(self):
        return _validate_uploaded_image(self.cleaned_data.get('image'))

    def clean(self):
        cleaned_data = super().clean()
        listing_type = cleaned_data.get('listing_type')
        price = cleaned_data.get('price')
        rent_per_day = cleaned_data.get('rent_per_day')

        if listing_type == 'sell' and price is None:
            self.add_error('price', 'Please enter a sale price for this listing.')
        if listing_type == 'rent' and rent_per_day is None:
            self.add_error('rent_per_day', 'Please enter a price per day for this rental.')

        self._reject_fractional_or_negative('price', 'Sale price')
        self._reject_fractional_or_negative('rent_per_day', 'Rent per day')
        self._reject_fractional_or_negative('security_deposit', 'Security deposit')
        return cleaned_data


class ItemImageForm(forms.ModelForm):
    class Meta:
        model = ItemImage
        fields = ['image']
        widgets = {
            'image': forms.FileInput(attrs={'accept': 'image/jpeg,image/png,image/gif,image/webp'}),
        }

    def clean_image(self):
        return _validate_uploaded_image(self.cleaned_data.get('image'))


ItemImageFormSet = modelformset_factory(
    ItemImage,
    form=ItemImageForm,
    extra=3,
    max_num=5,
    can_delete=True,
)
