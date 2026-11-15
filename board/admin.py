from django.contrib import admin
from .models import BoardRequest


@admin.register(BoardRequest)
class BoardRequestAdmin(admin.ModelAdmin):
    list_display = ['title', 'posted_by', 'category', 'is_fulfilled', 'created_at']
    list_filter = ['category', 'is_fulfilled']
    search_fields = ['title', 'posted_by__username']
