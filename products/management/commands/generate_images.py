"""
Generate placeholder product images using Pillow.

Creates a colored image for every product that doesn't already have one.
Colors are assigned per category so products are visually distinguishable.
"""

import os
from django.core.management.base import BaseCommand
from django.conf import settings
from PIL import Image, ImageDraw, ImageFont
from products.models import Product

CATEGORY_COLORS = {
    'Laptop': ('#667eea', '#764ba2'),
    'Mobile': ('#11998e', '#38ef7d'),
    'Headphone': ('#f093fb', '#f5576c'),
    'Smartwatch': ('#4facfe', '#00f2fe'),
}

CATEGORY_ICONS = {
    'Laptop': '💻',
    'Mobile': '📱',
    'Headphone': '🎧',
    'Smartwatch': '⌚',
}


def generate_image(product):
    width, height = 400, 300
    color1, color2 = CATEGORY_COLORS.get(product.category, ('#667eea', '#764ba2'))
    icon = CATEGORY_ICONS.get(product.category, '🛒')

    img = Image.new('RGB', (width, height), color1)
    draw = ImageDraw.Draw(img)

    for y in range(height):
        r = int(int(color1[1:3], 16) + (int(color2[1:3], 16) - int(color1[1:3], 16)) * y / height)
        g = int(int(color1[3:5], 16) + (int(color2[3:5], 16) - int(color1[3:5], 16)) * y / height)
        b = int(int(color1[5:7], 16) + (int(color2[5:7], 16) - int(color1[5:7], 16)) * y / height)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 24)
        small_font = ImageFont.truetype("arial.ttf", 16)
    except Exception:
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    draw.text((width // 2, 60), icon, fill='white', font=font, anchor='mt')
    draw.text((width // 2, 120), product.brand, fill='white', font=font, anchor='mt')
    draw.text((width // 2, 155), product.name[:30], fill='white', font=small_font, anchor='mt')
    draw.text((width // 2, 190), f'₹{int(product.price)}', fill='white', font=font, anchor='mt')
    draw.text((width // 2, 235), f'★ {product.rating}', fill='#ffd700', font=small_font, anchor='mt')

    filename = f"product_{product.id}.png"
    filepath = os.path.join(settings.MEDIA_ROOT, 'products', filename)
    img.save(filepath)
    return f'products/{filename}'


class Command(BaseCommand):
    help = 'Generate placeholder images for all products'

    def handle(self, *args, **options):
        products = Product.objects.filter(image='')
        count = 0
        for product in products:
            path = generate_image(product)
            product.image = path
            product.save(update_fields=['image'])
            count += 1
        self.stdout.write(self.style.SUCCESS(f'Generated {count} product images'))
