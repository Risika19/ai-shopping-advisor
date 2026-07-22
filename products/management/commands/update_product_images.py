"""
Production-ready product image downloader.

Strategy:
  1. DDG web search → find official product pages on trusted domains → extract og:image
     (trusted — only basic size check needed, it's the official product image)
  2. DDG image search → strict validation (reject logos, documents, anime, etc.)
  3. Direct known-source URLs (GSMArena)

All images get basic size validation. Only DDG image search results get strict
content validation since they can come from any source.
"""

import os
import io
import re
import math
from urllib.parse import urlparse, urljoin

import requests
from PIL import Image
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from django.conf import settings

from ddgs import DDGS

from products.models import Product


# ---------------------------------------------------------------------------
# Trusted source domains per category
# ---------------------------------------------------------------------------

TRUSTED_DOMAINS = {
    'Mobile': [
        'gsmarena.com', 'samsung.com', 'apple.com', 'oneplus.com',
        'mi.com', 'xiaomi.com', 'motorola.com', 'google.com',
        'nothing.tech', 'vivo.com', 'oppo.com', 'realme.com',
        'sony.com', 'asus.com',
    ],
    'Laptop': [
        'hp.com', 'dell.com', 'lenovo.com', 'asus.com', 'acer.com',
        'apple.com', 'microsoft.com', 'msi.com', 'samsung.com',
        'lg.com', 'notebookcheck.net',
    ],
    'Headphone': [
        'sony.com', 'jbl.com', 'marshall.com', 'sennheiser.com',
        'boat-lifestyle.com', 'nothing.tech', 'apple.com',
        'samsung.com', 'bose.com', 'oneplus.com',
    ],
    'Smartwatch': [
        'garmin.com', 'fitbit.com', 'samsung.com', 'apple.com',
        'amazfit.com', 'oneplus.com', 'google.com', 'xiaomi.com',
    ],
}

ALL_TRUSTED = sorted(set().union(*TRUSTED_DOMAINS.values()))

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/125.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,'
              'image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

TIMEOUT = 15
MIN_SIZE = 300


# ---------------------------------------------------------------------------
# Basic image check (applied to ALL images, even from trusted sources)
# ---------------------------------------------------------------------------

def basic_image_ok(img):
    """Minimum requirements for ANY product image — size and aspect ratio."""
    if img.mode != 'RGB':
        img = img.convert('RGB')
    w, h = img.size
    if w < MIN_SIZE or h < MIN_SIZE:
        return False
    aspect = max(w, h) / max(min(w, h), 1)
    if aspect > 3.5:
        return False
    return True


# ---------------------------------------------------------------------------
# Strict validation (only for DDG image search results — untrusted sources)
# ---------------------------------------------------------------------------

def _is_mostly_white(img, threshold=240, max_ratio=0.60):
    """Reject images that are >60% near-white (documents, blank posters)."""
    pixels = list(img.getdata())
    white = sum(1 for p in pixels if p[0] > threshold and p[1] > threshold and p[2] > threshold)
    return (white / len(pixels)) > max_ratio


def _is_low_variance(img, min_range=100):
    """Reject ultra-flat images (logos, banners, solid backgrounds)."""
    extrema = img.getextrema()
    total = 0
    for ch in extrema:
        mn, mx = ch
        total += mx - mn
    return (total / 3) < min_range


def _is_desaturated(img, min_sat=0.15):
    """Reject black-and-white or washed-out images (documents, B&W logos)."""
    hsv = img.convert('HSV')
    pixels = list(hsv.getdata())
    s = sum(p[1] for p in pixels)
    return (s / len(pixels) / 255.0) < min_sat


def _is_low_entropy(img, min_entropy=5.0):
    """Reject simple/low-detail images (flat vector graphics, simple logos)."""
    gray = img.convert('L')
    hist = gray.histogram()
    total = sum(hist)
    if total == 0:
        return True
    entropy = 0.0
    for c in hist:
        if c:
            p = c / total
            entropy -= p * math.log2(p)
    return entropy < min_entropy


def _is_extreme_brightness(img, lo=25, hi=245):
    """Reject nearly-black or nearly-white images."""
    gray = img.convert('L')
    pixels = list(gray.getdata())
    mean = sum(pixels) / len(pixels)
    return mean < lo or mean > hi


def strict_validate(img):
    """Full validation for images from untrusted sources.

    Rejects: logos, documents, screenshots, anime, cartoons, banners, posters.
    """
    if img.mode != 'RGB':
        img = img.convert('RGB')
    if _is_mostly_white(img):
        return False
    if _is_low_variance(img):
        return False
    if _is_desaturated(img):
        return False
    if _is_low_entropy(img):
        return False
    if _is_extreme_brightness(img):
        return False
    return True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fetch_page(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        if resp.status_code == 200 and 'text/html' in resp.headers.get('Content-Type', ''):
            return (resp.text, resp.url)
    except Exception:
        pass
    return (None, None)


def fetch_image(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        if resp.status_code != 200:
            return None
        if len(resp.content) < 8000:
            return None
        return Image.open(io.BytesIO(resp.content))
    except Exception:
        return None


def extract_og_image(html, page_url):
    """Return the best image URL from HTML (og:image > twitter:image > img tag)."""
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup.find_all('meta', property='og:image'):
        content = tag.get('content', '')
        if content:
            return urljoin(page_url, content)
    for tag in soup.find_all('meta', attrs={'name': 'twitter:image'}):
        content = tag.get('content', '')
        if content:
            return urljoin(page_url, content)
    for img_tag in soup.find_all('img'):
        src = img_tag.get('src', '') or img_tag.get('data-src', '')
        if src and any(k in src.lower() for k in ('product', 'hero', 'main', 'large', 'gallery')):
            return urljoin(page_url, src)
    return None


def domain_is_trusted(url, trusted_list):
    domain = urlparse(url).netloc.lower().replace('www.', '')
    return any(td in domain for td in trusted_list)


def name_in_url(url, product_name):
    """Check that key words from the product name appear in the URL.

    This helps ensure we landed on a *product page* and not just a brand homepage.
    """
    name_lower = product_name.lower()
    words = set(re.sub(r'[^a-z0-9]+', ' ', name_lower).split())
    # Only check the distinguishing words (skip very generic ones like 'pro', '5g', etc.)
    meaningful = [w for w in words if len(w) > 2]
    url_lower = url.lower()
    matches = sum(1 for w in meaningful if w in url_lower)
    # At least one meaningful product word should be in the URL
    return matches >= 1


# ---------------------------------------------------------------------------
# Search strategies
# ---------------------------------------------------------------------------

def strategy_web_search_og(product):
    """Strategy 1: DDG web → official product page on trusted domain → og:image.

    Returns (PIL Image, domain) or None.
    Images from this strategy are trusted — only basic size validation.
    """
    brand = product.brand.strip()
    name = product.name.strip()
    category = product.category.strip()
    trusted = TRUSTED_DOMAINS.get(category, ALL_TRUSTED)

    queries = [
        '%s %s official product' % (brand, name),
        '%s %s buy' % (brand, name),
        '%s %s %s' % (brand, name, category.lower()),
    ]

    for query in queries:
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=8))
        except Exception:
            continue

        for r in results:
            page_url = r.get('href', '')
            if not page_url or not domain_is_trusted(page_url, trusted):
                continue
            if not name_in_url(page_url, name):
                continue

            html, final_url = fetch_page(page_url)
            if not html:
                continue
            og_url = extract_og_image(html, final_url or page_url)
            if not og_url:
                continue

            img = fetch_image(og_url)
            if img and basic_image_ok(img):
                return (img, urlparse(final_url or page_url).netloc)

    return None


def strategy_ddg_images_trusted(product):
    """Strategy 2: DDG image search → only keep images with trusted source URLs.

    These go through STRICT validation since source pages may not be official.
    Returns PIL Image or None.
    """
    brand = product.brand.strip()
    name = product.name.strip()
    category = product.category.strip()
    trusted = TRUSTED_DOMAINS.get(category, ALL_TRUSTED)

    queries = [
        '%s %s %s' % (brand, name, category.lower()),
        '%s %s official product' % (brand, name),
    ]

    for query in queries:
        try:
            with DDGS() as ddgs:
                results = ddgs.images(query, max_results=20)
        except Exception:
            continue

        for r in results:
            img_url = r.get('image', '')
            src_url = (r.get('url', '') or r.get('source', '') or '').lower()
            if not img_url:
                continue
            # If the source page is trusted, we can be more lenient
            is_trusted = any(td in src_url for td in trusted)
            img = fetch_image(img_url)
            if not img or not basic_image_ok(img):
                continue
            if is_trusted:
                return img
            # Untrusted source → strict validation
            if strict_validate(img):
                return img

    return None


def strategy_known_urls(product):
    """Strategy 3: Direct known-source image URLs (GSMArena for phones)."""
    brand_lower = product.brand.lower()
    name_lower = product.name.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', name_lower).strip('-')
    brand_slug = re.sub(r'[^a-z0-9]+', '-', brand_lower).strip('-')

    if product.category == 'Mobile':
        known_prefixes = (
            'samsung-galaxy-', 'oneplus-', 'xiaomi-', 'redmi-',
            'google-pixel-', 'nothing-', 'vivo-', 'oppo-',
            'realme-', 'moto-', 'sony-', 'iqoo-', 'poco-',
            'asus-rog-', 'apple-iphone-',
        )
        gsma_slug = slug
        if not any(slug.startswith(p) for p in known_prefixes):
            gsma_slug = '%s-%s' % (brand_slug, slug)
        url = 'https://fdn2.gsmarena.net/vv/bigpic/%s/%s.jpg' % (brand_slug, gsma_slug)
        img = fetch_image(url)
        if img and basic_image_ok(img):
            return img

    return None


# ---------------------------------------------------------------------------
# Per-product orchestrator
# ---------------------------------------------------------------------------

def find_product_image(product):
    """Run strategies in order, return validated PIL Image or None."""
    # Strategy 1: Web search → og:image on trusted domain (trusted, basic validation)
    result = strategy_web_search_og(product)
    if result:
        img, domain = result
        return img

    # Strategy 2: DDG image search filtered by trusted source (strict validation)
    img = strategy_ddg_images_trusted(product)
    if img:
        return img

    # Strategy 3: Known direct URLs (GSMArena etc.)
    img = strategy_known_urls(product)
    if img:
        return img

    return None


# ---------------------------------------------------------------------------
# Current-image check
# ---------------------------------------------------------------------------

def current_image_ok(filepath):
    if not os.path.isfile(filepath):
        return False
    try:
        img = Image.open(filepath)
        if not basic_image_ok(img):
            return False
        # Additional check: file must exist and have reasonable size
        sz = os.path.getsize(filepath)
        return sz >= 8000
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Django management command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = 'Download official product images from trusted sources'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Re-download images even for products that already have a real image',
        )
        parser.add_argument(
            '--ids',
            type=str,
            default='',
            help='Comma-separated product IDs to process (e.g. --ids=1,2,3)',
        )

    def handle(self, *args, **options):
        force = options['force']
        ids_str = options.get('ids', '')
        target = os.path.join(settings.MEDIA_ROOT, 'products')
        os.makedirs(target, exist_ok=True)

        products = Product.objects.all().order_by('id')
        if ids_str:
            try:
                ids = [int(x.strip()) for x in ids_str.split(',') if x.strip()]
                products = Product.objects.filter(id__in=ids).order_by('id')
            except Exception:
                pass

        total = products.count()
        updated = 0
        skipped = 0
        failed = 0

        self.stdout.write('')
        self.stdout.write('=' * 60)
        self.stdout.write('  Product Image Updater')
        self.stdout.write('  Products: %d  Force: %s' % (total, 'ON' if force else 'OFF'))
        self.stdout.write('=' * 60)
        self.stdout.write('')

        for idx, prod in enumerate(products, 1):
            fname = 'product_%d.jpg' % prod.id
            dest = os.path.join(target, fname)

            needs_update = force
            if not needs_update:
                if not os.path.isfile(dest):
                    needs_update = True
                else:
                    try:
                        img = Image.open(dest)
                        if not basic_image_ok(img):
                            needs_update = True
                    except Exception:
                        needs_update = True

            if not needs_update:
                skipped += 1
                self.stdout.write(
                    '[%3d/%d] %-12s %-40s %s'
                    % (idx, total, prod.brand, prod.name[:40],
                       self.style.SUCCESS('[SKIP]'))
                )
                continue

            self.stdout.write('[%3d/%d] %-12s %-40s'
                              % (idx, total, prod.brand, prod.name[:40]))
            self.stdout.write('         Searching...')
            self.stdout.flush()

            try:
                img = find_product_image(prod)
                if img:
                    self.stdout.write('         Downloading...')
                    self.stdout.flush()
                    if img.mode in ('RGBA', 'P', 'LA'):
                        img = img.convert('RGB')
                    img.save(dest, 'JPEG', quality=92, optimize=True)
                    prod.image = 'products/%s' % fname
                    prod.save(update_fields=['image'])
                    self.stdout.write('         Replacing...')
                    self.stdout.write('         %s' % self.style.SUCCESS(
                        'Updated. %dx%d %s'
                        % (img.size[0], img.size[1], _fmt_size(os.path.getsize(dest)))
                    ))
                    updated += 1
                else:
                    failed += 1
                    self.stdout.write('         %s' % self.style.WARNING('Image Not Found'))
            except Exception as exc:
                failed += 1
                self.stdout.write('         %s' % self.style.ERROR('Error: %s' % exc))
            self.stdout.write('')

        self.stdout.write('=' * 60)
        if updated:
            self.stdout.write(self.style.SUCCESS('  Updated:  %d' % updated))
        if skipped:
            self.stdout.write(self.style.SUCCESS('  Skipped:  %d' % skipped))
        if failed:
            self.stdout.write(self.style.WARNING('  Failed:   %d' % failed))
        self.stdout.write(self.style.SUCCESS('  Total:    %d' % total))
        self.stdout.write('=' * 60)
        self.stdout.write('')


def _fmt_size(n):
    if n >= 1024 * 1024:
        return '%.1fMB' % (n / (1024 * 1024))
    if n >= 1024:
        return '%.1fKB' % (n / 1024)
    return '%dB' % n
