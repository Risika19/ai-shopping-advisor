import csv
import io
from decimal import Decimal
from datetime import datetime, timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Count, Sum, Q, Value, CharField
from django.db.models.functions import TruncMonth, TruncDay
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone

import openpyxl
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

from .decorators import admin_required
from .models import Category, Brand
from products.models import Product, Review
from orders.models import Order, OrderItem, Payment
from chatbot.models import ChatSession, ChatMessage
from dashboard.models import RecommendationHistory
from django.conf import settings


@admin_required
def dashboard(request):
    total_products = Product.objects.count()
    total_categories = Category.objects.count()
    total_users = User.objects.count()
    total_orders = Order.objects.count()
    total_revenue = Order.objects.filter(
        payment_status='SUCCESS',
        order_status='DELIVERED'
    ).aggregate(Sum('total'))['total__sum'] or 0
    pending_orders = Order.objects.filter(order_status='PENDING').count()
    delivered_orders = Order.objects.filter(order_status='DELIVERED').count()
    rec_count = RecommendationHistory.objects.count()
    chat_count = ChatMessage.objects.count()

    orders_chart = Order.objects.filter(
        created_at__gte=timezone.now() - timedelta(days=30)
    ).annotate(
        day=TruncDay('created_at')
    ).values('day').annotate(
        count=Count('id'),
        revenue=Sum('total')
    ).order_by('day')

    days = []
    order_counts = []
    revenue_data = []
    for entry in orders_chart:
        days.append(entry['day'].strftime('%b %d') if entry['day'] else '')
        order_counts.append(entry['count'])
        revenue_data.append(float(entry['revenue'] or 0))

    status_dist = Order.objects.values('order_status').annotate(
        count=Count('id')
    ).order_by('order_status')
    status_labels = [s['order_status'] for s in status_dist]
    status_counts_list = [s['count'] for s in status_dist]

    category_dist = Product.objects.values('category').annotate(
        count=Count('id')
    ).order_by('-count')
    cat_labels = [c['category'] for c in category_dist]
    cat_counts_list = [c['count'] for c in category_dist]

    recent_orders = Order.objects.select_related('user').order_by('-created_at')[:5]

    ctx = {
        'total_products': total_products,
        'total_categories': total_categories,
        'total_users': total_users,
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'pending_orders': pending_orders,
        'delivered_orders': delivered_orders,
        'rec_count': rec_count,
        'chat_count': chat_count,
        'days': days,
        'order_counts': order_counts,
        'revenue_data': revenue_data,
        'status_labels': status_labels,
        'status_counts': status_counts_list,
        'cat_labels': cat_labels,
        'cat_counts': cat_counts_list,
        'recent_orders': recent_orders,
    }
    return render(request, 'admin_panel/dashboard.html', ctx)


@admin_required
def product_list(request):
    q = request.GET.get('q', '')
    cat = request.GET.get('category', '')
    brand = request.GET.get('brand', '')
    sort = request.GET.get('sort', '-created_at')

    products = Product.objects.all()
    if q:
        products = products.filter(
            Q(name__icontains=q) | Q(brand__icontains=q) |
            Q(category__icontains=q) | Q(description__icontains=q)
        )
    if cat:
        products = products.filter(category=cat)
    if brand:
        products = products.filter(brand__iexact=brand)
    products = products.order_by(sort)

    paginator = Paginator(products, 15)
    page = request.GET.get('page', 1)
    products_page = paginator.get_page(page)

    categories = Product.objects.values_list('category', flat=True).distinct().order_by('category')
    brands = Product.objects.values_list('brand', flat=True).distinct().order_by('brand')

    ctx = {
        'products': products_page,
        'categories': categories,
        'brands': brands,
        'q': q,
        'cat': cat,
        'brand_filter': brand,
        'sort': sort,
        'paginator': paginator,
    }
    return render(request, 'admin_panel/product_list.html', ctx)


@admin_required
def product_add(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        brand = request.POST.get('brand')
        category = request.POST.get('category')
        price = request.POST.get('price')
        rating = request.POST.get('rating', 0)
        description = request.POST.get('description', '')
        features = request.POST.get('features', '')
        ram = request.POST.get('ram', '')
        storage = request.POST.get('storage', '')
        processor = request.POST.get('processor', '')
        battery = request.POST.get('battery', '')
        display = request.POST.get('display', '')
        camera = request.POST.get('camera', '')
        image = request.FILES.get('image')

        if not all([name, brand, category, price]):
            messages.error(request, 'Name, Brand, Category and Price are required.')
            return redirect('admin_product_add')

        try:
            product = Product(
                name=name, brand=brand, category=category,
                price=price, rating=rating, description=description,
                features=features, ram=ram, storage=storage,
                processor=processor, battery=battery, display=display,
                camera=camera,
            )
            if image:
                product.image = image
            product.save()
            messages.success(request, f'Product "{product.name}" added successfully.')
            return redirect('admin_products')
        except Exception as e:
            messages.error(request, f'Error adding product: {e}')
            return redirect('admin_product_add')

    categories = Product._meta.get_field('category').choices
    ctx = {'categories': categories, 'is_edit': False}
    return render(request, 'admin_panel/product_form.html', ctx)


@admin_required
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        product.name = request.POST.get('name', product.name)
        product.brand = request.POST.get('brand', product.brand)
        product.category = request.POST.get('category', product.category)
        product.price = request.POST.get('price', product.price)
        product.rating = request.POST.get('rating', product.rating)
        product.description = request.POST.get('description', product.description)
        product.features = request.POST.get('features', product.features)
        product.ram = request.POST.get('ram', product.ram)
        product.storage = request.POST.get('storage', product.storage)
        product.processor = request.POST.get('processor', product.processor)
        product.battery = request.POST.get('battery', product.battery)
        product.display = request.POST.get('display', product.display)
        product.camera = request.POST.get('camera', product.camera)
        if request.FILES.get('image'):
            product.image = request.FILES['image']
        product.save()
        messages.success(request, f'Product "{product.name}" updated.')
        return redirect('admin_products')

    categories = Product._meta.get_field('category').choices
    ctx = {'product': product, 'categories': categories, 'is_edit': True}
    return render(request, 'admin_panel/product_form.html', ctx)


@admin_required
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    product.delete()
    messages.success(request, f'Product "{product.name}" deleted.')
    return redirect('admin_products')


@admin_required
def category_list(request):
    categories = Category.objects.all().annotate(
        product_count=Count('name')
    ).order_by('name')

    product_categories = Product.objects.values('category').annotate(
        count=Count('id')
    ).order_by('category')

    ctx = {'categories': categories, 'product_categories': product_categories}
    return render(request, 'admin_panel/category_list.html', ctx)


@admin_required
def category_add(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '')
        icon = request.POST.get('icon', '')
        if not name:
            messages.error(request, 'Category name is required.')
            return redirect('admin_category_add')
        if Category.objects.filter(name__iexact=name).exists():
            messages.error(request, 'Category already exists.')
            return redirect('admin_category_add')
        Category.objects.create(name=name, description=description, icon=icon)
        messages.success(request, f'Category "{name}" created.')
        return redirect('admin_categories')
    ctx = {'is_edit': False}
    return render(request, 'admin_panel/category_form.html', ctx)


@admin_required
def category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Category name is required.')
            return redirect('admin_category_edit', pk=pk)
        if Category.objects.filter(name__iexact=name).exclude(pk=pk).exists():
            messages.error(request, 'Category name already exists.')
            return redirect('admin_category_edit', pk=pk)
        category.name = name
        category.description = request.POST.get('description', '')
        category.icon = request.POST.get('icon', '')
        category.save()
        messages.success(request, f'Category "{category.name}" updated.')
        return redirect('admin_categories')
    ctx = {'category': category, 'is_edit': True}
    return render(request, 'admin_panel/category_form.html', ctx)


@admin_required
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    category.delete()
    messages.success(request, f'Category "{category.name}" deleted.')
    return redirect('admin_categories')


@admin_required
def brand_list(request):
    brands = Brand.objects.all().annotate(
        product_count=Count('name')
    ).order_by('name')

    product_brands = Product.objects.values('brand').annotate(
        count=Count('id')
    ).order_by('brand')

    ctx = {'brands': brands, 'product_brands': product_brands}
    return render(request, 'admin_panel/brand_list.html', ctx)


@admin_required
def brand_add(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '')
        logo = request.FILES.get('logo')
        if not name:
            messages.error(request, 'Brand name is required.')
            return redirect('admin_brand_add')
        if Brand.objects.filter(name__iexact=name).exists():
            messages.error(request, 'Brand already exists.')
            return redirect('admin_brand_add')
        brand = Brand(name=name, description=description)
        if logo:
            brand.logo = logo
        brand.save()
        messages.success(request, f'Brand "{name}" created.')
        return redirect('admin_brands')
    ctx = {'is_edit': False}
    return render(request, 'admin_panel/brand_form.html', ctx)


@admin_required
def brand_edit(request, pk):
    brand = get_object_or_404(Brand, pk=pk)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'Brand name is required.')
            return redirect('admin_brand_edit', pk=pk)
        if Brand.objects.filter(name__iexact=name).exclude(pk=pk).exists():
            messages.error(request, 'Brand name already exists.')
            return redirect('admin_brand_edit', pk=pk)
        brand.name = name
        brand.description = request.POST.get('description', '')
        if request.FILES.get('logo'):
            brand.logo = request.FILES['logo']
        brand.save()
        messages.success(request, f'Brand "{brand.name}" updated.')
        return redirect('admin_brands')
    ctx = {'brand': brand, 'is_edit': True}
    return render(request, 'admin_panel/brand_form.html', ctx)


@admin_required
def brand_delete(request, pk):
    brand = get_object_or_404(Brand, pk=pk)
    brand.delete()
    messages.success(request, f'Brand "{brand.name}" deleted.')
    return redirect('admin_brands')


@admin_required
def order_list(request):
    q = request.GET.get('q', '')
    status = request.GET.get('status', '')
    pay_status = request.GET.get('pay_status', '')

    orders = Order.objects.select_related('user').prefetch_related('items')
    if q:
        orders = orders.filter(
            Q(order_id__icontains=q) | Q(name__icontains=q) |
            Q(user__username__icontains=q) | Q(email__icontains=q)
        )
    if status:
        orders = orders.filter(order_status=status)
    if pay_status:
        orders = orders.filter(payment_status=pay_status)
    orders = orders.order_by('-created_at')

    paginator = Paginator(orders, 20)
    page = request.GET.get('page', 1)
    orders_page = paginator.get_page(page)

    ctx = {
        'orders': orders_page,
        'q': q,
        'status': status,
        'pay_status': pay_status,
        'status_choices': Order.ORDER_STATUS_CHOICES,
        'pay_status_choices': Order.PAYMENT_STATUS_CHOICES,
        'paginator': paginator,
    }
    return render(request, 'admin_panel/order_list.html', ctx)


@admin_required
def order_detail(request, pk):
    order = get_object_or_404(Order.objects.select_related('user').prefetch_related('items', 'payments'), pk=pk)
    payments = order.payments.all()

    if request.method == 'POST':
        new_status = request.POST.get('order_status')
        if new_status in dict(Order.ORDER_STATUS_CHOICES):
            order.order_status = new_status
            if new_status == 'DELIVERED':
                order.payment_status = 'SUCCESS'
            elif new_status == 'CANCELLED':
                order.payment_status = 'REFUNDED'
            order.save()
            messages.success(request, f'Order {order.order_id} status updated to {order.get_order_status_display()}.')
        return redirect('admin_order_detail', pk=pk)

    ctx = {
        'order': order,
        'payments': payments,
        'status_choices': Order.ORDER_STATUS_CHOICES,
    }
    return render(request, 'admin_panel/order_detail.html', ctx)


@admin_required
def payment_list(request):
    q = request.GET.get('q', '')
    status = request.GET.get('status', '')

    payments = Payment.objects.select_related('order__user').order_by('-created_at')
    if q:
        payments = payments.filter(
            Q(order__order_id__icontains=q) | Q(razorpay_payment_id__icontains=q) |
            Q(order__user__username__icontains=q) | Q(method__icontains=q)
        )
    if status:
        payments = payments.filter(status=status)

    paginator = Paginator(payments, 20)
    page = request.GET.get('page', 1)
    payments_page = paginator.get_page(page)

    ctx = {
        'payments': payments_page,
        'q': q,
        'status': status,
        'paginator': paginator,
    }
    return render(request, 'admin_panel/payment_list.html', ctx)


@admin_required
def user_list(request):
    q = request.GET.get('q', '')
    users = User.objects.all().order_by('-date_joined')
    if q:
        users = users.filter(
            Q(username__icontains=q) | Q(email__icontains=q) |
            Q(first_name__icontains=q) | Q(last_name__icontains=q)
        )

    user_data = []
    for u in users:
        order_count = Order.objects.filter(user=u).count()
        total_spent = Order.objects.filter(user=u, payment_status='SUCCESS').aggregate(
            Sum('total')
        )['total__sum'] or 0
        user_data.append({
            'user': u,
            'order_count': order_count,
            'total_spent': total_spent,
        })

    paginator = Paginator(user_data, 20)
    page = request.GET.get('page', 1)
    users_page = paginator.get_page(page)

    ctx = {'users': users_page, 'q': q, 'paginator': paginator}
    return render(request, 'admin_panel/user_list.html', ctx)


@admin_required
def user_toggle_block(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    if user.is_superuser:
        messages.error(request, 'Cannot block a superuser.')
        return redirect('admin_users')
    user.is_active = not user.is_active
    user.save()
    status = 'unblocked' if user.is_active else 'blocked'
    messages.success(request, f'User "{user.username}" {status}.')
    return redirect('admin_users')


@admin_required
def ai_analytics(request):
    rec_history = RecommendationHistory.objects.select_related('user').order_by('-created_at')[:100]
    chat_sessions = ChatSession.objects.select_related('user').prefetch_related('messages').order_by('-created_at')[:50]

    rec_queries = RecommendationHistory.objects.values('query').annotate(
        count=Count('id')
    ).order_by('-count')[:20]

    all_products = Product.objects.all()
    searched_products = []
    for rh in rec_history:
        for p in all_products:
            if p.name.lower() in rh.query.lower() or p.brand.lower() in rh.query.lower():
                searched_products.append(p.name)
                break
    from collections import Counter
    product_freq = Counter(searched_products).most_common(10)

    popular_cats = Product.objects.filter(
        id__in=RecommendationHistory.objects.values_list('id', flat=True)
    ).values('category').annotate(count=Count('id')).order_by('-count')[:5]

    ctx = {
        'rec_history': rec_history,
        'chat_sessions': chat_sessions,
        'rec_queries': rec_queries,
        'product_freq': product_freq,
        'popular_cats': popular_cats,
    }
    return render(request, 'admin_panel/ai_analytics.html', ctx)


@admin_required
def reports(request):
    period = request.GET.get('period', 'month')
    now = timezone.now()
    if period == 'week':
        start_date = now - timedelta(days=7)
    elif period == 'month':
        start_date = now - timedelta(days=30)
    elif period == 'year':
        start_date = now - timedelta(days=365)
    else:
        start_date = now - timedelta(days=30)

    orders = Order.objects.filter(created_at__gte=start_date)
    total_sales = orders.count()
    total_revenue = orders.filter(payment_status='SUCCESS').aggregate(Sum('total'))['total__sum'] or 0
    avg_order_value = total_revenue / total_sales if total_sales else 0

    sales_by_day = orders.annotate(
        day=TruncDay('created_at')
    ).values('day').annotate(
        count=Count('id'),
        revenue=Sum('total')
    ).order_by('day')

    top_products = OrderItem.objects.filter(
        order__created_at__gte=start_date
    ).values('product_name').annotate(
        total_qty=Sum('quantity'),
        total_rev=Sum('product_price')
    ).order_by('-total_qty')[:10]

    ctx = {
        'period': period,
        'total_sales': total_sales,
        'total_revenue': total_revenue,
        'avg_order_value': avg_order_value,
        'orders': orders[:20],
        'sales_by_day': sales_by_day,
        'top_products': top_products,
        'start_date': start_date,
    }
    return render(request, 'admin_panel/reports.html', ctx)


@admin_required
def export_sales_csv(request):
    period = request.GET.get('period', 'month')
    now = timezone.now()
    start_date = now - timedelta(days=30)
    if period == 'week':
        start_date = now - timedelta(days=7)
    elif period == 'year':
        start_date = now - timedelta(days=365)

    orders = Order.objects.filter(created_at__gte=start_date).order_by('-created_at')
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="sales_report_{period}.csv"'
    writer = csv.writer(response)
    writer.writerow(['Order ID', 'Customer', 'Email', 'Total', 'Payment', 'Status', 'Date'])
    for o in orders:
        writer.writerow([o.order_id, o.name, o.email, o.total, o.payment_method, o.order_status, o.created_at.strftime('%Y-%m-%d')])
    return response


@admin_required
def export_sales_excel(request):
    period = request.GET.get('period', 'month')
    now = timezone.now()
    start_date = now - timedelta(days=30)
    if period == 'week':
        start_date = now - timedelta(days=7)
    elif period == 'year':
        start_date = now - timedelta(days=365)

    orders = Order.objects.filter(created_at__gte=start_date).order_by('-created_at')
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Sales Report'
    ws.append(['Order ID', 'Customer', 'Email', 'Total', 'Payment Method', 'Order Status', 'Payment Status', 'Date'])
    for o in orders:
        ws.append([o.order_id, o.name, o.email, float(o.total), o.payment_method, o.order_status, o.payment_status, o.created_at.strftime('%Y-%m-%d')])

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="sales_report_{period}.xlsx"'
    wb.save(response)
    return response


@admin_required
def export_sales_pdf(request):
    period = request.GET.get('period', 'month')
    now = timezone.now()
    start_date = now - timedelta(days=30)
    if period == 'week':
        start_date = now - timedelta(days=7)
    elif period == 'year':
        start_date = now - timedelta(days=365)

    orders = Order.objects.filter(created_at__gte=start_date).order_by('-created_at')
    total_rev = orders.filter(payment_status='SUCCESS').aggregate(Sum('total'))['total__sum'] or 0

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="sales_report_{period}.pdf"'

    doc = SimpleDocTemplate(response, pagesize=landscape(letter))
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph(f'Sales Report - {period.upper()}', styles['Title']))
    elements.append(Paragraph(f'Period: {start_date.strftime("%b %d, %Y")} to {now.strftime("%b %d, %Y")}', styles['Normal']))
    elements.append(Paragraph(f'Total Orders: {orders.count()} | Total Revenue: ${float(total_rev):.2f}', styles['Normal']))
    elements.append(Spacer(1, 20))

    data = [['Order ID', 'Customer', 'Total', 'Status', 'Date']]
    for o in orders:
        data.append([o.order_id, o.name, f'${float(o.total):.2f}', o.order_status, o.created_at.strftime('%Y-%m-%d')])

    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0d6efd')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
    ]))
    elements.append(table)
    doc.build(elements)
    return response


@admin_required
def export_products_csv(request):
    products = Product.objects.all().order_by('-created_at')
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="products.csv"'
    writer = csv.writer(response)
    writer.writerow(['Name', 'Brand', 'Category', 'Price', 'Rating', 'Stock', 'Created'])
    for p in products:
        writer.writerow([p.name, p.brand, p.category, p.price, p.rating, p.created_at.strftime('%Y-%m-%d')])
    return response


@admin_required
def export_products_excel(request):
    products = Product.objects.all().order_by('-created_at')
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Products'
    ws.append(['Name', 'Brand', 'Category', 'Price', 'Rating', 'Created'])
    for p in products:
        ws.append([p.name, p.brand, p.category, float(p.price), float(p.rating), p.created_at.strftime('%Y-%m-%d')])

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="products.xlsx"'
    wb.save(response)
    return response
