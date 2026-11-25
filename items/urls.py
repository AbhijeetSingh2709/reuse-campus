from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('explore/', views.explore_view, name='explore'),
    path('items/post/', views.post_item_view, name='post_item'),
    path('items/<int:pk>/', views.item_detail_view, name='item_detail'),
    path('items/<int:pk>/edit/', views.edit_item_view, name='edit_item'),
    path('items/<int:pk>/delete/', views.delete_item_view, name='delete_item'),
    path('items/<int:pk>/wishlist/', views.toggle_wishlist, name='toggle_wishlist'),
    path('my-items/', views.my_items_view, name='my_items'),
    path('wishlist/', views.wishlist_view, name='wishlist'),
    path('admin-dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
]
