"""Fetch final 7 images by directly hitting known product page URLs."""

import os, io, requests, re
from PIL import Image
from django.core.management.base import BaseCommand
from django.conf import settings
from products.models import Product
from urllib.parse import urlparse
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

# Direct product page URLs
DIRECT_URLS = {
    58: [
        'https://www.garmin.com/en-US/p/862927',
        'https://www.notebookcheck.net/Garmin-Forerunner-265.698376.0.html',
        'https://www8.garmin.com/images/forerunner-265-hero.png',
        'https://garmindigital.net/images/products/forerunner-265-big.png',
    ],
    70: [
        'https://www.samsung.com/in/audio-sound/galaxy-buds/galaxy-buds2-pro-bora-purple-sm-r510nlabins/',
        'https://images.samsung.com/is/image/samsung/p6pim/in/2208/gallery/in-galaxy-buds2-pro-r510-front-532237902',
        'https://www.notebookcheck.net/Samsung-Galaxy-Buds-2-Pro.648513.0.html',
    ],
    71: [
        'https://www.oneplus.in/product/nord-buds-3',
        'https://image01.oneplus.net/oob/202304/10/buds-nord-3-hero.png',
        'https://www.notebookcheck.net/OnePlus-Nord-Buds-3.697847.0.html',
    ],
    79: [
        'https://www.asus.com/laptops/zenbook-14-ux3405/',
        'https://dlcdnwebimgs.asus.com/gain/ACB6B8B7-8D9E-4A8A-9B0A-1C0E0F0D0C0E',
        'https://www.notebookcheck.net/Asus-Zenbook-14-OLED-UX3405.801521.0.html',
    ],
    80: [
        'https://www.lenovo.com/in/en/laptops/thinkpad/thinkpad-e-series/ThinkPad-E14-Gen-5/',
        'https://www.notebookcheck.net/Lenovo-ThinkPad-E14-Gen-5.576684.0.html',
    ],
    81: [
        'https://www.gsmarena.com/iqoo_z9-12907.php',
        'https://www.notebookcheck.net/iQOO-Z9.820209.0.html',
        'https://fdn2.gsmarena.net/vv/bigpic/iqoo/iqoo-z9.jpg',
    ],
    83: [
        'https://www.gsmarena.com/asus_rog_phone_8_pro-12817.php',
        'https://www.notebookcheck.net/Asus-ROG-Phone-8-Pro.796761.0.html',
        'https://fdn2.gsmarena.net/vv/bigpic/asus/asus-rog-phone-8-pro.jpg',
    ],
}


def extract_image_from_page(url):
    """Fetch a page and extract image from og:image or first product image."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # og:image
        for tag in soup.find_all('meta', property='og:image'):
            content = tag.get('content', '')
            if content:
                if content.startswith('/'):
                    parsed = urlparse(url)
                    content = f'{parsed.scheme}://{parsed.netloc}{content}'
                return content
        
        # twitter:image
        for tag in soup.find_all('meta', attrs={'name': 'twitter:image'}):
            content = tag.get('content', '')
            if content:
                return content
                
    except Exception:
        pass
    return None


def fetch_img_from_url(url):
    """Try to fetch an image directly from a URL."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=12, allow_redirects=True)
        if r.status_code == 200 and len(r.content) > 5000:
            img = Image.open(io.BytesIO(r.content))
            if img.width >= 200 and img.height >= 200:
                if img.mode in ('RGBA', 'P', 'LA'):
                    img = img.convert('RGB')
                return img
    except Exception:
        pass
    return None


class Command(BaseCommand):
    help = 'Fetch final 7 images from direct product page URLs'

    def handle(self, *args, **options):
        target = os.path.join(settings.MEDIA_ROOT, 'products')
        products = Product.objects.filter(id__in=list(DIRECT_URLS.keys())).order_by('id')
        ok = 0

        for prod in products:
            fname = f"product_{prod.id}.jpg"
            dest = os.path.join(target, fname)

            self.stdout.write(f"[{prod.id:2d}] {prod.brand} {prod.name[:30]:30s} ... ", ending='')
            self.stdout.flush()

            img = None
            urls = DIRECT_URLS.get(prod.id, [])

            # Try each URL
            for url in urls:
                # Is it directly an image URL?
                if any(url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']):
                    img = fetch_img_from_url(url)
                    if img:
                        self.stdout.write(f'DIRECT [{url.rsplit("/", 1)[-1][:30]}]', ending='')
                        break
                else:
                    # It's a page URL - extract og:image
                    og_url = extract_image_from_page(url)
                    if og_url:
                        img = fetch_img_from_url(og_url)
                        if img:
                            self.stdout.write(f'OG [{og_url.rsplit("/", 1)[-1][:30]}]', ending='')
                            break

            if img:
                img.save(dest, 'JPEG', quality=90, optimize=True)
                prod.image = f'products/{fname}'
                prod.save(update_fields=['image'])
                sz = os.path.getsize(dest)
                self.stdout.write(f' -> {img.size[0]}x{img.size[1]} {sz:,}b')
                ok += 1
            else:
                self.stdout.write(self.style.WARNING('NONE'))

        self.stdout.write(self.style.SUCCESS(f'\nDone! {ok} new images'))
