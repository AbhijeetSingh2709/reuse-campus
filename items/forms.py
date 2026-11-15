from django import forms
from .models import Item


class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ['title', 'description', 'category', 'listing_type', 'price', 'rent_per_day', 'image']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'listing_type': forms.Select(attrs={'id': 'id_listing_type'}),
        }
        help_texts = {
            'price': 'Fill this if listing type is Sell.',
            'rent_per_day': 'Fill this if listing type is Rent.',
        }

    def clean(self):
        cleaned_data = super().clean()
        listing_type = cleaned_data.get('listing_type')
        price = cleaned_data.get('price')
        rent_per_day = cleaned_data.get('rent_per_day')

        if listing_type == 'sell' and not price:
            self.add_error('price', 'Please enter a sale price for this listing.')
        if listing_type == 'rent' and not rent_per_day:
            self.add_error('rent_per_day', 'Please enter a price per day for this rental.')
        return cleaned_data
