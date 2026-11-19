from django.contrib import admin
from .models import Conversation, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ['sender', 'body', 'is_read', 'created_at']


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'item', 'created_at', 'updated_at']
    list_filter = ['created_at']
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['sender', 'conversation', 'body', 'is_read', 'created_at']
    list_filter = ['is_read', 'created_at']
