from django.db import models
from django.conf import settings
from items.models import Item

REQUEST_STATUS = [
    ('pending', 'Pending'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
]

DEPOSIT_STATUS_CHOICES = [
    ('not_required', 'Not Required'),
    ('pending', 'Deposit Pending'),
    ('held', 'Deposit Held'),
    ('released', 'Deposit Refunded'),
]


class BuyRequest(models.Model):
    """A request to buy an item listed for sale."""
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='buy_requests')
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='buy_requests_sent'
    )
    status = models.CharField(max_length=20, choices=REQUEST_STATUS, default='pending')
    message = models.TextField(blank=True, help_text='Optional message to the seller')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'BuyRequest: {self.requester.username} -> {self.item.title} [{self.status}]'


class RentRequest(models.Model):
    """A request to rent an item listed for rent."""
    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='rent_requests')
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='rent_requests_sent'
    )
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=REQUEST_STATUS + [('returned', 'Returned')],
        default='pending'
    )
    deposit_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    deposit_status = models.CharField(
        max_length=20,
        choices=DEPOSIT_STATUS_CHOICES,
        default='not_required',
    )
    payment_reference = models.CharField(max_length=120, blank=True)
    deposit_paid_at = models.DateTimeField(null=True, blank=True)
    deposit_released_at = models.DateTimeField(null=True, blank=True)
    message = models.TextField(blank=True, help_text='Optional message to the owner')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'RentRequest: {self.requester.username} -> {self.item.title} [{self.status}]'

    def duration_days(self):
        return max((self.end_date - self.start_date).days, 1)

    def total_cost(self):
        if self.item.rent_per_day:
            return self.duration_days() * self.item.rent_per_day
        return 0
