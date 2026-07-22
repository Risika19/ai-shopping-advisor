from django.urls import path
from . import views

urlpatterns = [
    path('cart/', views.cart_view, name='cart_view'),
    path('cart/add/<int:pk>/', views.cart_add, name='cart_add'),
    path('cart/update/<int:pk>/', views.cart_update, name='cart_update'),
    path('cart/remove/<int:pk>/', views.cart_remove, name='cart_remove'),
    path('wishlist/', views.wishlist_view, name='wishlist_view'),
    path('wishlist/add/<int:pk>/', views.wishlist_add, name='wishlist_add'),
    path('wishlist/remove/<int:pk>/', views.wishlist_remove, name='wishlist_remove'),
    path('wishlist/move/<int:pk>/', views.wishlist_move_to_cart, name='wishlist_move_to_cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('payment/success/<int:pk>/', views.payment_success, name='payment_success'),
    path('payment/failed/<int:pk>/', views.payment_failed, name='payment_failed'),
    path('payment/callback/', views.razorpay_callback, name='razorpay_callback'),
    path('orders/', views.my_orders, name='my_orders'),
    path('orders/<int:pk>/', views.order_detail, name='order_detail'),
    path('orders/<int:pk>/invoice/', views.order_invoice, name='order_invoice'),
    path('buy-now/<int:pk>/', views.buy_now, name='buy_now'),
]
