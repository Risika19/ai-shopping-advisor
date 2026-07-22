from django.shortcuts import render
from .utils import get_recommendations


def recommend(request):
    recommendations = None
    query = ''
    budget_exceeded = False

    if request.method == 'POST':
        query = request.POST.get('query', '')
        budget = request.POST.get('budget', '')
        category = request.POST.get('category', '')

        if query:
            recommendations, budget_exceeded = get_recommendations(query)
        else:
            parts = []
            if category:
                parts.append(category)
            if budget:
                parts.append(f"under {budget}")
            if parts:
                recommendations, budget_exceeded = get_recommendations(' '.join(parts))
            else:
                from products.models import Product
                recommendations = Product.objects.order_by('-rating')[:8]
                budget_exceeded = False

        if request.user.is_authenticated:
            from dashboard.models import RecommendationHistory
            RecommendationHistory.objects.create(user=request.user, query=query or ' '.join(parts))

    context = {
        'recommendations': recommendations,
        'query': query,
        'budget_exceeded': budget_exceeded,
    }
    return render(request, 'recommendation/recommend.html', context)
