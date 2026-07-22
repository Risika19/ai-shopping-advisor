from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('favorite/<int:pk>/', views.add_favorite, name='add_favorite'),
    path('favorite/<int:pk>/remove/', views.remove_favorite, name='remove_favorite'),
]
