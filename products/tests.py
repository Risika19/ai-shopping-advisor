from django.test import TestCase
from django.urls import reverse
from .models import Product, Review
from django.contrib.auth.models import User


class ProductModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Product.objects.create(
            name='Test Laptop',
            brand='TestBrand',
            category='Laptop',
            price=50000,
            ram='8GB',
            storage='256GB SSD',
            processor='Intel i5',
            rating=4.5,
        )

    def test_product_creation(self):
        product = Product.objects.get(id=1)
        self.assertEqual(product.name, 'Test Laptop')
        self.assertEqual(product.brand, 'TestBrand')
        self.assertEqual(str(product), 'TestBrand Test Laptop (Laptop)')

    def test_product_list_view(self):
        response = self.client.get(reverse('product_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Laptop')

    def test_product_detail_view(self):
        response = self.client.get(reverse('product_detail', args=[1]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Laptop')


class ProductSearchTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Product.objects.create(name='Gaming Laptop', brand='ASUS', category='Laptop', price=80000, rating=4.0)
        Product.objects.create(name='Office Laptop', brand='Dell', category='Laptop', price=50000, rating=4.0)
        Product.objects.create(name='iPhone 15', brand='Apple', category='Mobile', price=79900, rating=4.5)

    def test_search_by_name(self):
        response = self.client.get(reverse('product_list'), {'search': 'Gaming'})
        self.assertContains(response, 'Gaming Laptop')
        self.assertNotContains(response, 'Office Laptop')

    def test_filter_by_category(self):
        response = self.client.get(reverse('product_list'), {'category': 'Mobile'})
        self.assertContains(response, 'iPhone 15')
        self.assertNotContains(response, 'Gaming Laptop')
        self.assertNotContains(response, 'Office Laptop')

    def test_filter_by_price(self):
        response = self.client.get(reverse('product_list'), {'max_price': '60000'})
        self.assertContains(response, 'Office Laptop')
        self.assertNotContains(response, 'iPhone 15')


class ReviewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='reviewer', password='pass')
        cls.product = Product.objects.create(name='Test Phone', brand='Test', category='Mobile', price=20000, rating=4.0)

    def test_review_creation(self):
        self.client.login(username='reviewer', password='pass')
        response = self.client.post(reverse('product_detail', args=[self.product.pk]), {
            'rating': 5,
            'comment': 'Excellent product!',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Review.objects.count(), 1)
        review = Review.objects.first()
        self.assertEqual(review.sentiment, 'Positive')
