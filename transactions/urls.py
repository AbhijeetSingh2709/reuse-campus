from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('request/buy/<int:pk>/', views.request_to_buy, name='request_to_buy'),
    path('request/rent/<int:pk>/', views.request_to_rent, name='request_to_rent'),
    path('buy-request/<int:req_id>/approve/', views.approve_buy_request, name='approve_buy_request'),
    path('buy-request/<int:req_id>/reject/', views.reject_buy_request, name='reject_buy_request'),
    path('rent-request/<int:req_id>/approve/', views.approve_rent_request, name='approve_rent_request'),
    path('rent-request/<int:req_id>/reject/', views.reject_rent_request, name='reject_rent_request'),
    path('rent-request/<int:req_id>/returned/', views.mark_returned, name='mark_returned'),
]
