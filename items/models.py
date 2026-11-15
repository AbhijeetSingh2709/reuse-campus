from django.db import models
from django.conf import settings

CATEGORY_CHOICES = [
    ('books', 'Books & Study Materials'),
    ('electronics', 'Electronics'),
    ('calculators', 'Calculators'),
    ('lab', 'Lab Equipment'),
    ('uniforms', 'Uniforms & Clothing'),
    ('stationery', 'Stationery'),
    ('sports', 'Sports & Fitness'),
    ('other', 'Other'),
]

LISTING_TYPE_CHOICES = [
    ('sell', 'Sell'),
    ('rent', 'Rent'),
]

STATUS_CHOICES = [
    ('available', 'Available'),
    ('rented', 'Rented'),
    ('sold', 'Sold'),
]


class Item(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='items'
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    listing_type = models.CharField(max_length=10, choices=LISTING_TYPE_CHOICES)
    price = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text='Sale price (for Sell listings)'
    )
    rent_per_day = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text='Price per day (for Rent listings)'
    )
    image = models.ImageField(upload_to='item_images/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} ({self.get_listing_type_display()}) by {self.owner.username}'

    def get_display_price(self):
        if self.listing_type == 'sell' and self.price:
            return f'\u20b9{self.price}'
        elif self.listing_type == 'rent' and self.rent_per_day:
            return f'\u20b9{self.rent_per_day}/day'
        return 'Contact for price'
