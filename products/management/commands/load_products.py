import csv
from django.core.management.base import BaseCommand
from products.models import Product


class Command(BaseCommand):
    help = 'Load products from CSV dataset'

    def handle(self, *args, **options):
        path = 'dataset/products.csv'
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                Product.objects.get_or_create(
                    name=row['name'],
                    defaults={
                        'brand': row['brand'],
                        'category': row['category'],
                        'price': row['price'],
                        'ram': row['ram'],
                        'storage': row['storage'],
                        'processor': row['processor'],
                        'battery': row['battery'],
                        'display': row['display'],
                        'camera': row['camera'],
                        'rating': row['rating'],
                        'description': row['description'],
                        'features': row['features'],
                    }
                )
                count += 1
        self.stdout.write(self.style.SUCCESS(f'Loaded {count} products successfully'))
