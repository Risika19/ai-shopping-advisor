from django.contrib import admin
from django.urls import path, reverse
from django.shortcuts import redirect
from django.utils.html import format_html
from .models import Cart, CartItem, Wishlist, Order, OrderItem, Payment


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['product_name', 'product_price', 'quantity', 'subtotal']

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = ['razorpay_order_id', 'razorpay_payment_id', 'amount', 'method', 'status', 'created_at']

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_id', 'user', 'name', 'total', 'payment_method', 'payment_status', 'order_status', 'created_at']
    list_filter = ['order_status', 'payment_status', 'payment_method', 'created_at']
    search_fields = ['order_id', 'name', 'email', 'phone', 'user__username']
    readonly_fields = ['order_id', 'total', 'razorpay_order_id', 'razorpay_payment_id', 'razorpay_signature', 'created_at']
    inlines = [OrderItemInline, PaymentInline]
    actions = ['mark_confirmed', 'mark_packed', 'mark_shipped', 'mark_delivered', 'mark_cancelled']

    def mark_confirmed(self, request, queryset):
        queryset.update(order_status='CONFIRMED')
    mark_confirmed.short_description = "Mark selected orders as Confirmed"

    def mark_packed(self, request, queryset):
        queryset.update(order_status='PACKED')
    mark_packed.short_description = "Mark selected orders as Packed"

    def mark_shipped(self, request, queryset):
        queryset.update(order_status='SHIPPED')
    mark_shipped.short_description = "Mark selected orders as Shipped"

    def mark_delivered(self, request, queryset):
        queryset.update(order_status='DELIVERED')
    mark_delivered.short_description = "Mark selected orders as Delivered"

    def mark_cancelled(self, request, queryset):
        queryset.update(order_status='CANCELLED')
    mark_cancelled.short_description = "Mark selected orders as Cancelled"

    fieldsets = (
        ('Order Info', {
            'fields': ('order_id', 'user', 'name', 'email', 'phone')
        }),
        ('Shipping Address', {
            'fields': ('address', 'city', 'state', 'pincode')
        }),
        ('Payment', {
            'fields': ('payment_method', 'payment_status', 'total',
                       'razorpay_order_id', 'razorpay_payment_id', 'razorpay_signature')
        }),
        ('Status', {
            'fields': ('order_status', 'created_at', 'updated_at')
        }),
    )


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ['user', 'item_count', 'total', 'created_at']
    search_fields = ['user__username']


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ['cart', 'product', 'quantity', 'subtotal']


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ['user', 'product', 'created_at']
    search_fields = ['user__username', 'product__name']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['order', 'amount', 'method', 'status', 'razorpay_payment_id', 'created_at']
    list_filter = ['method', 'status', 'created_at']
    search_fields = ['order__order_id', 'razorpay_payment_id']
    readonly_fields = ['order', 'amount', 'method', 'status', 'razorpay_order_id', 'razorpay_payment_id', 'razorpay_signature', 'created_at']
