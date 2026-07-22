from django.urls import path
from . import views

urlpatterns = [
    path('', views.product_list, name='product_list'),
    path('compare/', views.compare_products, name='compare_products'),
    path('compare/add/', views.add_to_compare, name='add_to_compare'),
    path('compare/clear/', views.clear_compare, name='clear_compare'),
    path('<int:pk>/', views.product_detail, name='product_detail'),
]
