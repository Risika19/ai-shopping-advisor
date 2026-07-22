from django.contrib import admin
from .models import RecentlyViewed, Favorite, RecommendationHistory

admin.site.register(RecentlyViewed)
admin.site.register(Favorite)
admin.site.register(RecommendationHistory)
