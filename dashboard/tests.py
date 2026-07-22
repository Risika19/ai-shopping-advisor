from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from products.models import Product
from .models import RecentlyViewed, Favorite


class DashboardTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='dashuser', password='pass')
        cls.product = Product.objects.create(name='Dash Test', brand='Test', category='Laptop', price=30000, rating=4.0)

    def test_dashboard_redirects_anonymous(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_dashboard_authenticated(self):
        self.client.login(username='dashuser', password='pass')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'dashboard/dashboard.html')

    def test_recently_viewed_tracking(self):
        self.client.login(username='dashuser', password='pass')
        self.client.get(reverse('product_detail', args=[self.product.pk]))
        self.assertEqual(RecentlyViewed.objects.count(), 1)

    def test_add_favorite(self):
        self.client.login(username='dashuser', password='pass')
        response = self.client.get(reverse('add_favorite', args=[self.product.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Favorite.objects.filter(user=self.user, product=self.product).exists())
