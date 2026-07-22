from django.contrib import admin
from .models import Product, Review


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'brand', 'category', 'price', 'rating']
    list_filter = ['category', 'brand']
    search_fields = ['name', 'brand', 'description']


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['product', 'user', 'rating', 'sentiment', 'created_at']
    list_filter = ['rating', 'sentiment']
