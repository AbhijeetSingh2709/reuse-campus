from django.urls import path
from . import views

urlpatterns = [
    path('', views.board_view, name='board'),
    path('post/', views.post_board_request, name='post_board_request'),
    path('<int:pk>/fulfill/', views.fulfill_request, name='fulfill_request'),
]
