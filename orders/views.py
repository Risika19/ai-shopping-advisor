import json
import hashlib
import hmac
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.template.loader import render_to_string
from django.utils import timezone
from products.models import Product
from .models import Cart, CartItem, Wishlist, Order, OrderItem, Payment
from .forms import CheckoutForm


def _get_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


@login_required
def cart_view(request):
    cart = _get_cart(request.user)
    items = cart.items.select_related('product').all()
    total = cart.total
    return render(request, 'orders/cart.html', {
        'cart': cart,
        'items': items,
        'total': total,
    })


@login_required
def cart_add(request, pk):
    product = get_object_or_404(Product, pk=pk)
    cart = _get_cart(request.user)
    item, created = CartItem.objects.get_or_create(cart=cart, product=product)
    if not created:
        item.quantity += 1
        item.save()
        messages.info(request, f'Updated quantity: {product.name} (x{item.quantity})')
    else:
        messages.success(request, f'Added {product.name} to cart.')
    referer = request.META.get('HTTP_REFERER', '')
    if 'checkout' in request.GET:
        return redirect('checkout')
    if referer:
        return redirect(referer)
    return redirect('cart_view')


@login_required
def cart_update(request, pk):
    if request.method == 'POST':
        product = get_object_or_404(Product, pk=pk)
        cart = _get_cart(request.user)
        item = get_object_or_404(CartItem, cart=cart, product=product)
        qty = int(request.POST.get('quantity', 1))
        if qty > 0:
            item.quantity = qty
            item.save()
            messages.success(request, f'Updated quantity: {product.name} (x{qty})')
        else:
            item.delete()
            messages.info(request, f'Removed {product.name} from cart.')
    return redirect('cart_view')


@login_required
def cart_remove(request, pk):
    product = get_object_or_404(Product, pk=pk)
    cart = _get_cart(request.user)
    CartItem.objects.filter(cart=cart, product=product).delete()
    messages.info(request, f'Removed {product.name} from cart.')
    return redirect('cart_view')


@login_required
def wishlist_view(request):
    items = Wishlist.objects.filter(user=request.user).select_related('product')
    return render(request, 'orders/wishlist.html', {'wishlist_items': items})


@login_required
def wishlist_add(request, pk):
    product = get_object_or_404(Product, pk=pk)
    item, created = Wishlist.objects.get_or_create(user=request.user, product=product)
    if created:
        messages.success(request, f'{product.name} added to wishlist.')
    else:
        messages.info(request, f'{product.name} is already in your wishlist.')
    referer = request.META.get('HTTP_REFERER', '')
    if referer:
        return redirect(referer)
    return redirect('wishlist_view')


@login_required
def wishlist_remove(request, pk):
    product = get_object_or_404(Product, pk=pk)
    Wishlist.objects.filter(user=request.user, product=product).delete()
    messages.info(request, f'Removed {product.name} from wishlist.')
    referer = request.META.get('HTTP_REFERER', '')
    if referer:
        return redirect(referer)
    return redirect('wishlist_view')


@login_required
def wishlist_move_to_cart(request, pk):
    product = get_object_or_404(Product, pk=pk)
    cart = _get_cart(request.user)
    CartItem.objects.get_or_create(cart=cart, product=product)
    Wishlist.objects.filter(user=request.user, product=product).delete()
    messages.success(request, f'Moved {product.name} to cart.')
    return redirect('cart_view')


@login_required
def checkout(request):
    cart = _get_cart(request.user)
    items = cart.items.select_related('product').all()
    if not items:
        messages.warning(request, 'Your cart is empty. Add some products first.')
        return redirect('cart_view')

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            total = cart.total
            order = Order.objects.create(
                user=request.user,
                name=cd['name'],
                email=cd['email'],
                phone=cd['phone'],
                address=cd['address'],
                city=cd['city'],
                state=cd['state'],
                pincode=cd['pincode'],
                total=total,
                payment_method=cd['payment_method'],
            )
            for item in items:
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    product_name=item.product.name,
                    product_price=item.product.price,
                    quantity=item.quantity,
                )

            Payment.objects.create(
                order=order,
                amount=total,
                method=cd['payment_method'],
                status='PENDING',
            )

            if cd['payment_method'] == 'COD':
                order.payment_status = 'PENDING'
                order.order_status = 'CONFIRMED'
                order.save()
                Payment.objects.filter(order=order).update(status='PENDING')
                cart.items.all().delete()
                _send_order_confirmation(request, order)
                messages.success(request, f'Order placed successfully! Your order ID is {order.order_id}.')
                return redirect('order_detail', pk=order.pk)
            elif cd['payment_method'] == 'RAZORPAY':
                razorpay_order = _create_razorpay_order(order)
                if razorpay_order:
                    order.razorpay_order_id = razorpay_order['id']
                    order.save()
                    Payment.objects.filter(order=order).update(
                        razorpay_order_id=razorpay_order['id']
                    )
                    cart.items.all().delete()
                    return render(request, 'orders/razorpay_pay.html', {
                        'order': order,
                        'razorpay_key': settings.RAZORPAY_KEY_ID,
                        'razorpay_amount': int(order.total * 100),
                        'razorpay_order_id': razorpay_order['id'],
                        'user_name': order.name,
                        'user_email': order.email,
                        'user_phone': order.phone,
                    })
                else:
                    messages.error(request, 'Payment gateway error. Please try again.')
                    return redirect('checkout')
            else:
                order.payment_status = 'SUCCESS'
                order.order_status = 'CONFIRMED'
                order.save()
                Payment.objects.filter(order=order).update(status='SUCCESS')
                cart.items.all().delete()
                _send_order_confirmation(request, order)
                messages.success(request, f'Order placed successfully! Your order ID is {order.order_id}.')
                return redirect('order_detail', pk=order.pk)
    else:
        initial = {
            'name': request.user.get_full_name() or request.user.username,
            'email': request.user.email,
        }
        form = CheckoutForm(initial=initial)

    return render(request, 'orders/checkout.html', {
        'form': form,
        'cart': cart,
        'items': items,
        'total': cart.total,
    })


def _create_razorpay_order(order):
    try:
        import razorpay
        client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        data = {
            'amount': int(order.total * 100),
            'currency': 'INR',
            'receipt': order.order_id,
            'payment_capture': 1,
        }
        razorpay_order = client.order.create(data=data)
        return razorpay_order
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Razorpay order creation failed: {e}")
        return None


@csrf_exempt
def razorpay_callback(request):
    if request.method == 'POST':
        razorpay_payment_id = request.POST.get('razorpay_payment_id', '')
        razorpay_order_id = request.POST.get('razorpay_order_id', '')
        razorpay_signature = request.POST.get('razorpay_signature', '')

        order = Order.objects.filter(razorpay_order_id=razorpay_order_id).first()
        if not order:
            messages.error(request, 'Invalid payment session.')
            return redirect('home')

        params_dict = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature,
        }

        if _verify_razorpay_signature(params_dict):
            order.payment_status = 'SUCCESS'
            order.order_status = 'CONFIRMED'
            order.razorpay_payment_id = razorpay_payment_id
            order.razorpay_signature = razorpay_signature
            order.save()
            Payment.objects.filter(order=order).update(
                razorpay_payment_id=razorpay_payment_id,
                razorpay_signature=razorpay_signature,
                status='SUCCESS',
            )
            _send_order_confirmation(request, order)
            messages.success(request, f'Payment successful! Your order ID is {order.order_id}.')
            return redirect('payment_success', pk=order.pk)
        else:
            order.payment_status = 'FAILED'
            order.save()
            Payment.objects.filter(order=order).update(status='FAILED')
            messages.error(request, 'Payment verification failed.')
            return redirect('payment_failed', pk=order.pk)

    return redirect('home')


def _verify_razorpay_signature(params_dict):
    razorpay_order_id = params_dict.get('razorpay_order_id', '')
    razorpay_payment_id = params_dict.get('razorpay_payment_id', '')
    razorpay_signature = params_dict.get('razorpay_signature', '')

    msg = f"{razorpay_order_id}|{razorpay_payment_id}"
    secret = settings.RAZORPAY_KEY_SECRET
    expected_sig = hmac.new(
        secret.encode(),
        msg.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_sig, razorpay_signature)


@login_required
def payment_success(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    return render(request, 'orders/payment_success.html', {'order': order})


@login_required
def payment_failed(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    return render(request, 'orders/payment_failed.html', {'order': order})


@login_required
def my_orders(request):
    orders = Order.objects.filter(user=request.user).prefetch_related('items')
    return render(request, 'orders/my_orders.html', {'orders': orders})


@login_required
def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    return render(request, 'orders/order_detail.html', {'order': order})


@login_required
def order_invoice(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    return render(request, 'orders/invoice.html', {'order': order})


def _send_order_confirmation(request, order):
    try:
        from django.core.mail import send_mail
        subject = f'Order Confirmed - {order.order_id}'
        html_message = render_to_string('orders/email_confirmation.html', {'order': order})
        send_mail(
            subject,
            '',
            settings.DEFAULT_FROM_EMAIL,
            [order.email],
            html_message=html_message,
            fail_silently=True,
        )
    except Exception:
        pass


def buy_now(request, pk):
    product = get_object_or_404(Product, pk=pk)
    cart = _get_cart(request.user)
    CartItem.objects.filter(cart=cart).delete()
    CartItem.objects.create(cart=cart, product=product, quantity=1)
    return redirect('checkout')
