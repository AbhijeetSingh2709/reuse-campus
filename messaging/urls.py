from django.urls import path
from . import views

urlpatterns = [
    path('', views.inbox_view, name='inbox'),
    path('notifications/', views.notifications_view, name='notifications'),
    path(
        'notifications/<int:notification_id>/open/',
        views.open_notification,
        name='open_notification',
    ),
    path(
        'notifications/<int:notification_id>/read/',
        views.mark_notification_read,
        name='mark_notification_read',
    ),
    path(
        'notifications/read-all/',
        views.mark_all_notifications_read,
        name='mark_all_notifications_read',
    ),
    path(
        'board/<int:board_request_id>/start/',
        views.start_board_conversation,
        name='start_board_conversation',
    ),
    path('<int:conv_id>/', views.conversation_view, name='conversation'),
    path('start/<str:username>/', views.start_conversation, name='start_conversation'),
    path('start/<str:username>/item/<int:item_id>/', views.start_conversation, name='start_conversation_item'),
    path('unread-counts/', views.unread_counts_json, name='unread_counts_json'),
]
