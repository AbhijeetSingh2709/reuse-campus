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

CONDITION_CHOICES = [
    ('new', 'Brand New'),
    ('like_new', 'Like New'),
    ('good', 'Good'),
    ('fair', 'Fair'),
    ('poor', 'Poor'),
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
    security_deposit = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text='Optional refundable security deposit (for Rent listings)'
    )
    image = models.ImageField(upload_to='item_images/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='good')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} ({self.get_listing_type_display()}) by {self.owner.username}'

    @property
    def image_url(self):
        """Public media URL when a photo is stored and the file is still present."""
        if not self.image or not self.image.name:
            return ''
        try:
            if not self.image.storage.exists(self.image.name):
                return ''
            return self.image.url
        except (OSError, ValueError):
            return ''

    @staticmethod
    def _rupee_text(amount):
        if amount == amount.to_integral_value():
            return str(int(amount))
        return f'{amount:.2f}'

    def get_display_price(self):
        if self.listing_type == 'sell' and self.price is not None:
            return f'\u20b9{self._rupee_text(self.price)}'
        if self.listing_type == 'rent' and self.rent_per_day is not None:
            return f'\u20b9{self._rupee_text(self.rent_per_day)}/day'
        return 'Contact for price'


class ItemImage(models.Model):
    """Additional photos for a listing."""
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='extra_images')
    image = models.ImageField(upload_to='item_images/')
    order = models.PositiveSmallIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'uploaded_at']

    def __str__(self):
        return f'Image for {self.item.title} (#{self.order})'

    @property
    def image_url(self):
        if not self.image or not self.image.name:
            return ''
        try:
            if not self.image.storage.exists(self.image.name):
                return ''
            return self.image.url
        except (OSError, ValueError):
            return ''
