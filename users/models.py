from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Extended user model for ReUse Campus."""
    phone = models.CharField(max_length=15, blank=True)
    bio = models.TextField(blank=True)
    profile_pic = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    is_email_verified = models.BooleanField(default=False)
    wishlist = models.ManyToManyField(
        'items.Item',
        blank=True,
        related_name='wishlisted_by',
        verbose_name='Saved items',
    )

    def __str__(self):
        return self.username
