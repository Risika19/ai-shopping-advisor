from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='admin_dashboard'),

    # Products
    path('products/', views.product_list, name='admin_products'),
    path('products/add/', views.product_add, name='admin_product_add'),
    path('products/<int:pk>/edit/', views.product_edit, name='admin_product_edit'),
    path('products/<int:pk>/delete/', views.product_delete, name='admin_product_delete'),

    # Categories
    path('categories/', views.category_list, name='admin_categories'),
    path('categories/add/', views.category_add, name='admin_category_add'),
    path('categories/<int:pk>/edit/', views.category_edit, name='admin_category_edit'),
    path('categories/<int:pk>/delete/', views.category_delete, name='admin_category_delete'),

    # Brands
    path('brands/', views.brand_list, name='admin_brands'),
    path('brands/add/', views.brand_add, name='admin_brand_add'),
    path('brands/<int:pk>/edit/', views.brand_edit, name='admin_brand_edit'),
    path('brands/<int:pk>/delete/', views.brand_delete, name='admin_brand_delete'),

    # Orders
    path('orders/', views.order_list, name='admin_orders'),
    path('orders/<int:pk>/', views.order_detail, name='admin_order_detail'),

    # Payments
    path('payments/', views.payment_list, name='admin_payments'),

    # Users
    path('users/', views.user_list, name='admin_users'),
    path('users/<int:user_id>/toggle-block/', views.user_toggle_block, name='admin_user_toggle_block'),

    # AI Analytics
    path('ai-analytics/', views.ai_analytics, name='admin_ai_analytics'),

    # Reports
    path('reports/', views.reports, name='admin_reports'),
    path('reports/export/sales/csv/', views.export_sales_csv, name='admin_export_sales_csv'),
    path('reports/export/sales/excel/', views.export_sales_excel, name='admin_export_sales_excel'),
    path('reports/export/sales/pdf/', views.export_sales_pdf, name='admin_export_sales_pdf'),
    path('reports/export/products/csv/', views.export_products_csv, name='admin_export_products_csv'),
    path('reports/export/products/excel/', views.export_products_excel, name='admin_export_products_excel'),
]
