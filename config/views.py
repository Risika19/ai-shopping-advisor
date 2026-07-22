from django.shortcuts import render
from products.models import Product, Review
from django.db.models import Count


def home(request):
    featured = Product.objects.order_by('-rating')[:8]
    new_arrivals = Product.objects.order_by('-created_at')[:8]
    top_rated = Product.objects.order_by('-rating')[:8]
    trending = Product.objects.filter(rating__gte=4.0).order_by('?')[:8]

    categories = Product.objects.values_list('category', flat=True).distinct()
    brands = Product.objects.values_list('brand', flat=True).distinct()

    category_counts = Product.objects.values('category').annotate(count=Count('id'))

    recent_reviews = Review.objects.select_related('product', 'user').order_by('-created_at')[:6]

    product_count = Product.objects.count()
    review_count = Review.objects.count()

    context = {
        'featured_products': featured,
        'new_arrivals': new_arrivals,
        'top_rated': top_rated,
        'trending_products': trending,
        'categories': categories,
        'brands': brands,
        'category_counts': category_counts,
        'recent_reviews': recent_reviews,
        'product_count': product_count,
        'review_count': review_count,
    }
    return render(request, 'home.html', context)
