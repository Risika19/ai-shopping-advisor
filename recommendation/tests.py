from django.test import TestCase
from products.models import Product
from .utils import (
    get_recommendations, extract_budget, extract_category,
    extract_brand, extract_keywords
)


class RecommendationEngineTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Product.objects.create(
            name='Gaming Laptop', brand='ASUS', category='Laptop', price=80000,
            ram='16GB', storage='1TB SSD', processor='Intel i7',
            battery='6 hours', display='15.6 FHD', rating=4.5,
            description='High performance gaming laptop with dedicated GPU',
            features='Gaming,High performance,Dedicated GPU'
        )
        Product.objects.create(
            name='Ultrabook', brand='Dell', category='Laptop', price=60000,
            ram='8GB', storage='512GB SSD', processor='Intel i5',
            battery='12 hours', display='13.3 FHD', rating=4.3,
            description='Lightweight laptop for productivity',
            features='Lightweight,Long battery,Productivity'
        )
        Product.objects.create(
            name='Flagship Phone', brand='Samsung', category='Mobile', price=70000,
            ram='12GB', storage='256GB', processor='Snapdragon 8 Gen 3',
            battery='5000mAh', display='6.8 AMOLED', camera='200MP', rating=4.6,
            description='Premium smartphone with amazing camera',
            features='Great camera,AMOLED,Flagship'
        )
        Product.objects.create(
            name='Budget Laptop', brand='HP', category='Laptop', price=45000,
            ram='8GB', storage='512GB SSD', processor='Intel i3',
            battery='8 hours', display='15.6 FHD', rating=4.0,
            description='Affordable laptop for everyday use',
            features='Budget friendly,Everyday use'
        )

    def test_recommendation_returns_products(self):
        results, _ = get_recommendations('laptop for gaming')
        self.assertTrue(len(results) > 0)

    def test_recommendation_relevance(self):
        results, _ = get_recommendations('gaming laptop')
        names = [p.name for p in results]
        self.assertIn('Gaming Laptop', names)

    def test_recommendation_mobile_query(self):
        results, _ = get_recommendations('phone with good camera')
        names = [p.name for p in results]
        self.assertIn('Flagship Phone', names)

    def test_budget_filter_strict(self):
        results, exceeded = get_recommendations('laptop under 50000')
        for p in results:
            self.assertLessEqual(float(p.price), 50000,
                                 f'{p.name} costs ₹{p.price} > ₹50000 (budget)')

    def test_budget_filter_hp(self):
        results, exceeded = get_recommendations('hp laptop under 50000')
        for p in results:
            self.assertLessEqual(float(p.price), 50000,
                                 f'{p.name} costs ₹{p.price} > ₹50000')
            self.assertEqual(p.brand.lower(), 'hp',
                             f'{p.name} is not HP')

    def test_budget_filter_no_products_fallback(self):
        results, exceeded = get_recommendations('laptop under 1000')
        self.assertTrue(exceeded, 'Budget exceeded flag should be True')

    def test_budget_filter_all_products_within(self):
        results, exceeded = get_recommendations('laptop under 100000')
        for p in results:
            self.assertLessEqual(float(p.price), 100000,
                                 f'{p.name} costs ₹{p.price} > ₹100000')

    def test_category_filter(self):
        results, _ = get_recommendations('laptop')
        for p in results:
            self.assertEqual(p.category.lower(), 'laptop')

    def test_brand_filter(self):
        results, _ = get_recommendations('samsung phone')
        for p in results:
            self.assertEqual(p.brand.lower(), 'samsung')

    def test_no_budget_query(self):
        results, exceeded = get_recommendations('gaming laptop')
        self.assertFalse(exceeded)
        self.assertTrue(len(results) > 0)

    def test_budget_with_k_suffix(self):
        results, exceeded = get_recommendations('laptop under 50k')
        for p in results:
            self.assertLessEqual(float(p.price), 50000,
                                 f'{p.name} costs ₹{p.price} > ₹50000')

    def test_budget_first_query(self):
        results, exceeded = get_recommendations('budget 50000 laptop')
        for p in results:
            self.assertLessEqual(float(p.price), 50000)

    def test_recommendation_order_preserved(self):
        results, _ = get_recommendations('laptop')
        if len(results) >= 2:
            self.assertTrue(len(results) > 0)
            for p in results:
                self.assertEqual(p.category.lower(), 'laptop')


class ExtractionUnitTests(TestCase):
    def test_extract_budget_under(self):
        self.assertEqual(extract_budget('under 50000'), 50000)

    def test_extract_budget_below(self):
        self.assertEqual(extract_budget('below 20000'), 20000)

    def test_extract_budget_less_than(self):
        self.assertEqual(extract_budget('less than 10000'), 10000)

    def test_extract_budget_within(self):
        self.assertEqual(extract_budget('within 30000'), 30000)

    def test_extract_budget_k_suffix(self):
        self.assertEqual(extract_budget('under 50k'), 50000)

    def test_extract_budget_20k(self):
        self.assertEqual(extract_budget('phone under 20k'), 20000)

    def test_extract_budget_none(self):
        self.assertIsNone(extract_budget('no budget here'))

    def test_extract_budget_budget_first(self):
        self.assertEqual(extract_budget('budget 30000 laptop'), 30000)

    def test_extract_category_laptop(self):
        self.assertEqual(extract_category('gaming laptop'), 'Laptop')

    def test_extract_category_mobile(self):
        self.assertEqual(extract_category('best phone'), 'Mobile')

    def test_extract_category_headphone(self):
        self.assertEqual(extract_category('wireless earphones'), 'Headphone')

    def test_extract_category_smartwatch(self):
        self.assertEqual(extract_category('smartwatch'), 'Smartwatch')

    def test_extract_category_none(self):
        self.assertIsNone(extract_category('no category here'))

    def test_extract_brand_hp(self):
        self.assertEqual(extract_brand('hp laptop'), 'Hp')

    def test_extract_brand_samsung(self):
        self.assertEqual(extract_brand('samsung phone'), 'Samsung')

    def test_extract_brand_dell(self):
        self.assertEqual(extract_brand('dell laptop'), 'Dell')

    def test_extract_brand_apple(self):
        self.assertEqual(extract_brand('apple macbook'), 'Apple')

    def test_extract_brand_none(self):
        self.assertIsNone(extract_brand('no brand here'))

    def test_extract_keywords_gaming(self):
        kws = extract_keywords('gaming laptop under 50000', 'Laptop', None, 50000)
        self.assertIn('gaming', kws)
        self.assertNotIn('laptop', kws)
