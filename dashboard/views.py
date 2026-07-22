from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from products.models import Product
from .models import RecentlyViewed, Favorite, RecommendationHistory


@login_required
def dashboard(request):
    recent = RecentlyViewed.objects.filter(user=request.user)[:8]
    favorites = Favorite.objects.filter(user=request.user)[:8]
    history = RecommendationHistory.objects.filter(user=request.user)[:5]

    context = {
        'recent_products': [r.product for r in recent],
        'favorites': [f.product for f in favorites],
        'history': history,
    }
    return render(request, 'dashboard/dashboard.html', context)


@login_required
def add_favorite(request, pk):
    product = get_object_or_404(Product, pk=pk)
    fav, created = Favorite.objects.get_or_create(user=request.user, product=product)
    if created:
        messages.success(request, f'{product.name} added to favorites.')
    else:
        fav.delete()
        messages.info(request, f'{product.name} removed from favorites.')
    referer = request.META.get('HTTP_REFERER', '')
    if referer:
        return redirect(referer)
    return redirect('dashboard')


@login_required
def remove_favorite(request, pk):
    product = get_object_or_404(Product, pk=pk)
    Favorite.objects.filter(user=request.user, product=product).delete()
    messages.info(request, 'Product removed from favorites.')
    return redirect('dashboard')
