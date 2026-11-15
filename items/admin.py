from django.contrib import admin
from .models import Item


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ['title', 'owner', 'category', 'listing_type', 'status', 'created_at']
    list_filter = ['category', 'listing_type', 'status']
    search_fields = ['title', 'description', 'owner__username']
