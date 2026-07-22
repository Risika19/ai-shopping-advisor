from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User


class AdminPanelTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.normal = User.objects.create_user('test_n', 'n@t.com', 'pass')
        self.staff = User.objects.create_user('test_s', 's@t.com', 'pass', is_staff=True)
        self.admin = User.objects.create_superuser('test_a', 'a@t.com', 'pass')

    def test_normal_user_redirected(self):
        self.client.login(username='test_n', password='pass')
        r = self.client.get('/admin-panel/')
        self.assertIn(r.status_code, [302, 403])

    def test_admin_dashboard(self):
        self.client.login(username='test_a', password='pass')
        r = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(r.status_code, 200)

    def test_admin_products(self):
        self.client.login(username='test_a', password='pass')
        r = self.client.get(reverse('admin_products'))
        self.assertEqual(r.status_code, 200)

    def test_admin_product_add(self):
        self.client.login(username='test_a', password='pass')
        r = self.client.get(reverse('admin_product_add'))
        self.assertEqual(r.status_code, 200)

    def test_admin_product_add_post(self):
        self.client.login(username='test_a', password='pass')
        r = self.client.post(reverse('admin_product_add'), {
            'name': 'TestPhone', 'brand': 'TestB',
            'category': 'Mobile', 'price': '999'
        })
        self.assertEqual(r.status_code, 302)

    def test_admin_categories(self):
        self.client.login(username='test_a', password='pass')
        r = self.client.get(reverse('admin_categories'))
        self.assertEqual(r.status_code, 200)

    def test_admin_brands(self):
        self.client.login(username='test_a', password='pass')
        r = self.client.get(reverse('admin_brands'))
        self.assertEqual(r.status_code, 200)

    def test_admin_orders(self):
        self.client.login(username='test_a', password='pass')
        r = self.client.get(reverse('admin_orders'))
        self.assertEqual(r.status_code, 200)

    def test_admin_payments(self):
        self.client.login(username='test_a', password='pass')
        r = self.client.get(reverse('admin_payments'))
        self.assertEqual(r.status_code, 200)

    def test_admin_users(self):
        self.client.login(username='test_a', password='pass')
        r = self.client.get(reverse('admin_users'))
        self.assertEqual(r.status_code, 200)

    def test_admin_ai_analytics(self):
        self.client.login(username='test_a', password='pass')
        r = self.client.get(reverse('admin_ai_analytics'))
        self.assertEqual(r.status_code, 200)

    def test_admin_reports(self):
        self.client.login(username='test_a', password='pass')
        r = self.client.get(reverse('admin_reports'))
        self.assertEqual(r.status_code, 200)

    def test_export_csv(self):
        self.client.login(username='test_a', password='pass')
        r = self.client.get(reverse('admin_export_sales_csv') + '?period=month')
        self.assertIn(r.status_code, [200, 302])

    def test_export_excel(self):
        self.client.login(username='test_a', password='pass')
        r = self.client.get(reverse('admin_export_sales_excel') + '?period=month')
        self.assertIn(r.status_code, [200, 302])

    def test_export_pdf(self):
        self.client.login(username='test_a', password='pass')
        r = self.client.get(reverse('admin_export_sales_pdf') + '?period=month')
        self.assertIn(r.status_code, [200, 302])

    def test_user_toggle_block(self):
        self.client.login(username='test_a', password='pass')
        r = self.client.get(reverse('admin_user_toggle_block', args=[self.normal.id]))
        self.assertEqual(r.status_code, 302)

    def test_category_add(self):
        self.client.login(username='test_a', password='pass')
        r = self.client.post(reverse('admin_category_add'), {'name': 'Tablet'})
        self.assertEqual(r.status_code, 302)

    def test_brand_add(self):
        self.client.login(username='test_a', password='pass')
        r = self.client.post(reverse('admin_brand_add'), {'name': 'Samsung'})
        self.assertEqual(r.status_code, 302)
