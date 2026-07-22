"""Find real images for final 7 products by scraping tech review pages."""

import os, io, requests, re
from PIL import Image
from django.core.management.base import BaseCommand
from django.conf import settings
from products.models import Product
from ddgs import DDGS
from urllib.parse import urlparse, quote
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

# Preferred review/product sites to scrape images from
PREFERRED_DOMAINS = [
    'notebookcheck.net', 'gsmarena.com', 'theverge.com', 'techradar.com',
    'cnet.com', 'androidcentral.com', 'xda-developers.com', 'garmin.com',
    'samsung.com', 'oneplus.com', 'asus.com', 'lenovo.com', 'amazon.com',
    'amazon.in', 'flipkart.com', '91mobiles.com', 'smartprix.com',
]

# Specific search queries for each remaining product
SEARCH_QUERIES = {
    58: ['Garmin Forerunner 265 review notebookcheck', 'Garmin Forerunner 265 garmin.com product'],
    70: ['Samsung Galaxy Buds 2 Pro review', 'Samsung Galaxy Buds 2 Pro samsung.com product'],
    71: ['OnePlus Nord Buds 3 review', 'OnePlus Nord Buds 3 oneplus.com product'],
    79: ['ASUS Zenbook 14 UX3405 review notebookcheck', 'ASUS Zenbook 14 asus.com laptop'],
    80: ['Lenovo ThinkPad E14 Gen 5 review', 'Lenovo ThinkPad E14 Gen 5 lenovo.com product'],
    81: ['iQOO Z9 review gsmarena', 'iQOO Z9 5G smartphone review'],
    83: ['ASUS ROG Phone 8 Pro review gsmarena', 'ASUS ROG Phone 8 Pro asus.com product'],
}


def fetch_image_from_url(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
        if r.status_code == 200 and len(r.content) > 5000:
            img = Image.open(io.BytesIO(r.content))
            if img.width >= 200 and img.height >= 200:
                if img.mode in ('RGBA', 'P', 'LA'):
                    img = img.convert('RGB')
                return img, r.content
    except Exception:
        pass
    return None, None


def extract_og_image(html, base_url):
    soup = BeautifulSoup(html, 'html.parser')
    # og:image
    for tag in soup.find_all('meta', property='og:image'):
        content = tag.get('content', '')
        if content:
            if content.startswith('/'):
                parsed = urlparse(base_url)
                content = f'{parsed.scheme}://{parsed.netloc}{content}'
            return content
    # twitter:image
    for tag in soup.find_all('meta', attrs={'name': 'twitter:image'}):
        content = tag.get('content', '')
        if content:
            return content
    # First large image in article/product
    for img_tag in soup.find_all('img'):
        src = img_tag.get('src', '') or img_tag.get('data-src', '')
        if src and ('product' in src.lower() or 'hero' in src.lower()):
            if src.startswith('/'):
                parsed = urlparse(base_url)
                src = f'{parsed.scheme}://{parsed.netloc}{src}'
            return src
    return None


def find_and_fetch(prod_id, queries):
    """Search DDG, find review pages, extract og:image, download it."""
    for query in queries:
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=5))
        except Exception:
            continue

        for r in results:
            url = r.get('href', '')
            if not url or url.startswith('http'):
                continue

            domain = urlparse(url).netloc.lower()
            # Skip non-preferred domains but don't be too restrictive
            if not any(pd in domain for pd in PREFERRED_DOMAINS):
                # Still try it as a fallback
                pass

            try:
                pr = requests.get(url, headers=HEADERS, timeout=10)
                if pr.status_code != 200:
                    continue

                og_url = extract_og_image(pr.text, url)
                if not og_url:
                    continue

                # Handle Samsung is/image URLs
                if 'samsung.com/is/image' in og_url:
                    # Try to get a larger variant
                    og_url = og_url.split('?')[0]

                img, content = fetch_image_from_url(og_url)
                if img:
                    # Verify image is large enough (not an icon)
                    file_size = len(content) if content else 0
                    if img.width >= 300 and img.height >= 300 and file_size > 10000:
                        return img
            except Exception:
                continue

    return None


class Command(BaseCommand):
    help = 'Fetch final 7 images from tech review pages'

    def handle(self, *args, **options):
        target = os.path.join(settings.MEDIA_ROOT, 'products')
        products = Product.objects.filter(id__in=list(SEARCH_QUERIES.keys())).order_by('id')
        ok = 0

        for prod in products:
            fname = f"product_{prod.id}.jpg"
            dest = os.path.join(target, fname)

            self.stdout.write(f"[{prod.id:2d}] {prod.brand} {prod.name[:30]:30s} ... ", ending='')
            self.stdout.flush()

            img = find_and_fetch(prod.id, SEARCH_QUERIES.get(prod.id, []))
            if img:
                img.save(dest, 'JPEG', quality=90, optimize=True)
                prod.image = f'products/{fname}'
                prod.save(update_fields=['image'])
                sz = os.path.getsize(dest)
                self.stdout.write(self.style.SUCCESS(f'OK {img.size[0]}x{img.size[1]} {sz:,}b'))
                ok += 1
            else:
                self.stdout.write(self.style.WARNING('NONE'))

        self.stdout.write(self.style.SUCCESS(f'\nDone! {ok} new images'))
