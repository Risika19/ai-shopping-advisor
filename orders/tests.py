from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from products.models import Product
from .models import Cart, CartItem, Wishlist, Order, OrderItem, Payment


class EcommerceFlowTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass123')
        self.product = Product.objects.create(
            name='Test Laptop', brand='TestBrand', category='Laptop',
            price=50000, ram='8GB', storage='512GB', processor='Intel i5',
            rating=4.5, description='A test laptop'
        )
        self.product2 = Product.objects.create(
            name='Test Phone', brand='TestBrand', category='Mobile',
            price=25000, ram='6GB', storage='128GB', processor='Snapdragon',
            rating=4.3, description='A test phone'
        )

    def test_01_cart_add_requires_login(self):
        response = self.client.get(reverse('cart_add', args=[self.product.pk]))
        self.assertNotEqual(response.status_code, 200)

    def test_02_cart_add_authenticated(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('cart_add', args=[self.product.pk]))
        self.assertEqual(response.status_code, 302)
        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.items.count(), 1)

    def test_03_cart_view(self):
        self.client.login(username='testuser', password='testpass123')
        self.client.get(reverse('cart_add', args=[self.product.pk]))
        response = self.client.get(reverse('cart_view'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Laptop')

    def test_04_cart_update_quantity(self):
        self.client.login(username='testuser', password='testpass123')
        self.client.get(reverse('cart_add', args=[self.product.pk]))
        response = self.client.post(reverse('cart_update', args=[self.product.pk]), {'quantity': 3})
        self.assertEqual(response.status_code, 302)
        cart = Cart.objects.get(user=self.user)
        item = CartItem.objects.get(cart=cart, product=self.product)
        self.assertEqual(item.quantity, 3)

    def test_05_cart_remove(self):
        self.client.login(username='testuser', password='testpass123')
        self.client.get(reverse('cart_add', args=[self.product.pk]))
        response = self.client.get(reverse('cart_remove', args=[self.product.pk]))
        self.assertEqual(response.status_code, 302)
        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.items.count(), 0)

    def test_06_cart_total(self):
        self.client.login(username='testuser', password='testpass123')
        self.client.get(reverse('cart_add', args=[self.product.pk]))
        self.client.get(reverse('cart_add', args=[self.product2.pk]))
        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.total, 50000 + 25000)

    def test_07_wishlist_add(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('wishlist_add', args=[self.product.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Wishlist.objects.filter(user=self.user, product=self.product).exists())

    def test_08_wishlist_remove(self):
        self.client.login(username='testuser', password='testpass123')
        self.client.get(reverse('wishlist_add', args=[self.product.pk]))
        response = self.client.get(reverse('wishlist_remove', args=[self.product.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Wishlist.objects.filter(user=self.user, product=self.product).exists())

    def test_09_wishlist_move_to_cart(self):
        self.client.login(username='testuser', password='testpass123')
        self.client.get(reverse('wishlist_add', args=[self.product.pk]))
        response = self.client.get(reverse('wishlist_move_to_cart', args=[self.product.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Wishlist.objects.filter(user=self.user, product=self.product).exists())
        cart = Cart.objects.get(user=self.user)
        self.assertTrue(CartItem.objects.filter(cart=cart, product=self.product).exists())

    def test_10_wishlist_view(self):
        self.client.login(username='testuser', password='testpass123')
        self.client.get(reverse('wishlist_add', args=[self.product.pk]))
        response = self.client.get(reverse('wishlist_view'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Laptop')

    def test_11_checkout_requires_auth(self):
        response = self.client.get(reverse('checkout'))
        self.assertNotEqual(response.status_code, 200)

    def test_12_checkout_empty_cart_redirect(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('checkout'))
        self.assertEqual(response.status_code, 302)

    def test_13_checkout_get(self):
        self.client.login(username='testuser', password='testpass123')
        self.client.get(reverse('cart_add', args=[self.product.pk]))
        response = self.client.get(reverse('checkout'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Laptop')

    def test_14_checkout_cod_order(self):
        self.client.login(username='testuser', password='testpass123')
        self.client.get(reverse('cart_add', args=[self.product.pk]))
        response = self.client.post(reverse('checkout'), {
            'name': 'Test User',
            'email': 'test@example.com',
            'phone': '9876543210',
            'address': '123 Test St',
            'city': 'Test City',
            'state': 'Test State',
            'pincode': '123456',
            'payment_method': 'COD',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Order.objects.filter(user=self.user).exists())
        order = Order.objects.get(user=self.user)
        self.assertEqual(order.payment_method, 'COD')
        self.assertEqual(order.order_status, 'CONFIRMED')
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.first().product_name, 'Test Laptop')

    def test_15_order_detail(self):
        self.client.login(username='testuser', password='testpass123')
        self.client.get(reverse('cart_add', args=[self.product.pk]))
        self.client.post(reverse('checkout'), {
            'name': 'Test User', 'email': 'test@example.com', 'phone': '9876543210',
            'address': '123 Test St', 'city': 'Test City', 'state': 'Test State',
            'pincode': '123456', 'payment_method': 'COD',
        })
        order = Order.objects.get(user=self.user)
        response = self.client.get(reverse('order_detail', args=[order.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, order.order_id)

    def test_16_my_orders(self):
        self.client.login(username='testuser', password='testpass123')
        self.client.get(reverse('cart_add', args=[self.product.pk]))
        self.client.post(reverse('checkout'), {
            'name': 'Test User', 'email': 'test@example.com', 'phone': '9876543210',
            'address': '123 Test St', 'city': 'Test City', 'state': 'Test State',
            'pincode': '123456', 'payment_method': 'COD',
        })
        response = self.client.get(reverse('my_orders'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Laptop')

    def test_17_invoice(self):
        self.client.login(username='testuser', password='testpass123')
        self.client.get(reverse('cart_add', args=[self.product.pk]))
        self.client.post(reverse('checkout'), {
            'name': 'Test User', 'email': 'test@example.com', 'phone': '9876543210',
            'address': '123 Test St', 'city': 'Test City', 'state': 'Test State',
            'pincode': '123456', 'payment_method': 'COD',
        })
        order = Order.objects.get(user=self.user)
        response = self.client.get(reverse('order_invoice', args=[order.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'INVOICE')

    def test_18_buy_now(self):
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('buy_now', args=[self.product.pk]))
        self.assertEqual(response.status_code, 302)
        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.items.count(), 1)

    def test_19_razorpay_payment_flow(self):
        self.client.login(username='testuser', password='testpass123')
        self.client.get(reverse('cart_add', args=[self.product.pk]))
        self.client.post(reverse('checkout'), {
            'name': 'Test User', 'email': 'test@example.com', 'phone': '9876543210',
            'address': '123 Test St', 'city': 'Test City', 'state': 'Test State',
            'pincode': '123456', 'payment_method': 'RAZORPAY',
        })
        order = Order.objects.get(user=self.user)
        self.assertEqual(order.payment_method, 'RAZORPAY')
        self.assertIn('ORD-', order.order_id)
        payment = Payment.objects.get(order=order)
        self.assertEqual(payment.status, 'PENDING')

    def test_20_order_status_default(self):
        self.client.login(username='testuser', password='testpass123')
        self.client.get(reverse('cart_add', args=[self.product.pk]))
        self.client.post(reverse('checkout'), {
            'name': 'Test User', 'email': 'test@example.com', 'phone': '9876543210',
            'address': '123 Test St', 'city': 'Test City', 'state': 'Test State',
            'pincode': '123456', 'payment_method': 'COD',
        })
        order = Order.objects.get(user=self.user)
        self.assertEqual(order.order_status, 'CONFIRMED')

    def test_21_cart_item_count(self):
        self.client.login(username='testuser', password='testpass123')
        self.client.get(reverse('cart_add', args=[self.product.pk]))
        self.client.get(reverse('cart_add', args=[self.product2.pk]))
        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.item_count, 2)

    def test_22_add_to_cart_twice_increases_quantity(self):
        self.client.login(username='testuser', password='testpass123')
        self.client.get(reverse('cart_add', args=[self.product.pk]))
        self.client.get(reverse('cart_add', args=[self.product.pk]))
        cart = Cart.objects.get(user=self.user)
        item = CartItem.objects.get(cart=cart, product=self.product)
        self.assertEqual(item.quantity, 2)

    def test_23_checkout_creates_payment(self):
        self.client.login(username='testuser', password='testpass123')
        self.client.get(reverse('cart_add', args=[self.product.pk]))
        self.client.post(reverse('checkout'), {
            'name': 'Test User', 'email': 'test@example.com', 'phone': '9876543210',
            'address': '123 Test St', 'city': 'Test City', 'state': 'Test State',
            'pincode': '123456', 'payment_method': 'COD',
        })
        order = Order.objects.get(user=self.user)
        self.assertEqual(Payment.objects.filter(order=order).count(), 1)

    def test_24_payment_success_page(self):
        self.client.login(username='testuser', password='testpass123')
        self.client.get(reverse('cart_add', args=[self.product.pk]))
        self.client.post(reverse('checkout'), {
            'name': 'Test User', 'email': 'test@example.com', 'phone': '9876543210',
            'address': '123 Test St', 'city': 'Test City', 'state': 'Test State',
            'pincode': '123456', 'payment_method': 'CARD',
        })
        order = Order.objects.get(user=self.user)
        response = self.client.get(reverse('payment_success', args=[order.pk]))
        self.assertEqual(response.status_code, 200)
