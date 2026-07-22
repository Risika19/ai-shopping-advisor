from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Avg, Count
from .models import Product, Review
from .forms import ReviewForm
from .sentiment import analyze_sentiment


def get_compare_list(request):
    return request.session.get('compare_ids', [])


def product_list(request):
    products = Product.objects.all()
    categories = Product.objects.values_list('category', flat=True).distinct()
    brands = Product.objects.values_list('brand', flat=True).distinct()

    search = request.GET.get('search', '')
    category = request.GET.get('category', '')
    brand = request.GET.get('brand', '')
    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')

    if search:
        products = products.filter(name__icontains=search) | products.filter(brand__icontains=search)
    if category:
        products = products.filter(category=category)
    if brand:
        products = products.filter(brand=brand)
    if min_price:
        products = products.filter(price__gte=min_price)
    if max_price:
        products = products.filter(price__lte=max_price)

    context = {
        'products': products,
        'categories': categories,
        'brands': brands,
        'search': search,
        'selected_category': category,
        'selected_brand': brand,
        'min_price': min_price,
        'max_price': max_price,
        'compare_ids': request.session.get('compare_ids', []),
    }
    return render(request, 'products/product_list.html', context)


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    reviews = product.reviews.all()
    form = ReviewForm()

    if request.user.is_authenticated:
        from dashboard.models import RecentlyViewed
        RecentlyViewed.objects.get_or_create(user=request.user, product=product)

    if request.method == 'POST' and request.user.is_authenticated:
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.product = product
            review.user = request.user
            result = analyze_sentiment(review.comment)
            review.sentiment = result['label']
            review.save()
            messages.success(request, 'Review added successfully!')
            return redirect('product_detail', pk=product.pk)

    sentiment_stats = reviews.values('sentiment').annotate(count=Count('id'))
    avg_rating = reviews.aggregate(avg=Avg('rating'))['avg']
    is_favorite = False
    if request.user.is_authenticated:
        from dashboard.models import Favorite
        is_favorite = Favorite.objects.filter(user=request.user, product=product).exists()

    context = {
        'product': product,
        'reviews': reviews,
        'form': form,
        'sentiment_stats': sentiment_stats,
        'avg_rating': avg_rating,
        'is_favorite': is_favorite,
    }
    return render(request, 'products/product_detail.html', context)


def add_to_compare(request):
    product_id = request.GET.get('product_id')
    if product_id:
        compare_ids = request.session.get('compare_ids', [])
        pid = int(product_id)
        if pid not in compare_ids:
            if len(compare_ids) >= 4:
                messages.warning(request, 'You can compare up to 4 products at a time.')
            else:
                compare_ids.append(pid)
                messages.success(request, 'Product added to comparison.')
        else:
            compare_ids.remove(pid)
            messages.info(request, 'Product removed from comparison.')
        request.session['compare_ids'] = compare_ids
    return redirect(request.META.get('HTTP_REFERER', 'product_list'))


def clear_compare(request):
    request.session['compare_ids'] = []
    messages.info(request, 'Comparison list cleared.')
    return redirect('product_list')


def compare_products(request):
    compare_ids = request.session.get('compare_ids', [])
    products = Product.objects.filter(id__in=compare_ids)
    return render(request, 'products/compare.html', {'products': products})
