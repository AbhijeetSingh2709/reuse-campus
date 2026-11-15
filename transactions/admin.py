from django.contrib import admin
from .models import BuyRequest, RentRequest


@admin.register(BuyRequest)
class BuyRequestAdmin(admin.ModelAdmin):
    list_display = ['item', 'requester', 'status', 'created_at']
    list_filter = ['status']
    search_fields = ['item__title', 'requester__username']


@admin.register(RentRequest)
class RentRequestAdmin(admin.ModelAdmin):
    list_display = ['item', 'requester', 'start_date', 'end_date', 'status', 'created_at']
    list_filter = ['status']
    search_fields = ['item__title', 'requester__username']
