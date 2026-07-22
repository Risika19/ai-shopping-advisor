"""
Generate professional product card images for all products.

Creates category-specific device silhouettes (laptop, phone, headphone, watch)
using PIL drawing primitives, with brand colors, product name, price, and rating.

All images are 500x375 JPEG at high quality — no external image dependencies.
"""

import os
import math
from PIL import Image, ImageDraw, ImageFont
from django.core.management.base import BaseCommand
from django.conf import settings
from products.models import Product

CATEGORY_COLORS = {
    'Laptop':     {'bg': ('#0f0c29', '#302b63'), 'accent': '#00ffc8', 'device': '#1a1a3e'},
    'Mobile':     {'bg': ('#1a1a2e', '#16213e'), 'accent': '#4fc3f7', 'device': '#1a2a4e'},
    'Headphone':  {'bg': ('#141e30', '#243b55'), 'accent': '#ff6b6b', 'device': '#1e2d3d'},
    'Smartwatch': {'bg': ('#0d1117', '#161b22'), 'accent': '#58a6ff', 'device': '#161b22'},
}


def hex_to_rgb(h):
    return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)


def draw_gradient(draw, w, h, c1, c2):
    r1, g1, b1 = hex_to_rgb(c1)
    r2, g2, b2 = hex_to_rgb(c2)
    for y in range(h):
        t = y / h
        r = min(255, int(r1 + (r2 - r1) * t))
        g = min(255, int(g1 + (g2 - g1) * t))
        b = min(255, int(b1 + (b2 - b1) * t))
        draw.line([(0, y), (w, y)], fill=(r, g, b))


def draw_rounded_rect(draw, x, y, w, h, r, fill, outline=None, ow=2):
    draw.pieslice([x, y, x + 2 * r, y + 2 * r], 180, 270, fill=fill)
    draw.pieslice([x + w - 2 * r, y, x + w, y + 2 * r], 270, 360, fill=fill)
    draw.pieslice([x, y + h - 2 * r, x + 2 * r, y + h], 90, 180, fill=fill)
    draw.pieslice([x + w - 2 * r, y + h - 2 * r, x + w, y + h], 0, 90, fill=fill)
    draw.rectangle([x + r, y, x + w - r, y + h], fill=fill)
    draw.rectangle([x, y + r, x + w, y + h - r], fill=fill)
    if outline:
        draw.arc([x, y, x + 2 * r, y + 2 * r], 180, 270, fill=outline, width=ow)
        draw.arc([x + w - 2 * r, y, x + w, y + 2 * r], 270, 360, fill=outline, width=ow)
        draw.arc([x, y + h - 2 * r, x + 2 * r, y + h], 90, 180, fill=outline, width=ow)
        draw.arc([x + w - 2 * r, y + h - 2 * r, x + w, y + h], 0, 90, fill=outline, width=ow)
        draw.line([x + r, y, x + w - r, y], fill=outline, width=ow)
        draw.line([x + r, y + h, x + w - r, y + h], fill=outline, width=ow)
        draw.line([x, y + r, x, y + h - r], fill=outline, width=ow)
        draw.line([x + w, y + r, x + w, y + h - r], fill=outline, width=ow)


def draw_laptop(draw, cx, cy, device_color, accent):
    """Draw a stylized open laptop."""
    # Base (keyboard area)
    bw, bh = 200, 20
    draw_rounded_rect(draw, cx - bw // 2, cy + 10, bw, bh, 6, fill=device_color)
    # Screen
    sw, sh = 170, 130
    sx, sy = cx - sw // 2, cy - sh - 5
    draw_rounded_rect(draw, sx, sy, sw, sh, 8, fill=device_color)
    # Screen display (lighter)
    dsx, dsy, dsw, dsh = sx + 8, sy + 8, sw - 16, sh - 40
    draw_rounded_rect(draw, dsx, dsy, dsw, dsh, 4, fill='#2a2a4e')
    # Screen content - lines
    for i in range(3):
        ly = dsy + 20 + i * 20
        draw.line([(dsx + 10, ly), (dsx + dsw - 10, ly)], fill='#3a3a6e', width=2)
    # Keyboard keys
    for row in range(3):
        for col in range(8):
            kx = cx - 80 + col * 22
            ky = cy + 18 + row * 5
            draw.rectangle([kx, ky, kx + 18, ky + 3], fill='#3a3a4e')
    # Trackpad
    draw_rounded_rect(draw, cx - 20, cy + 18 + 16, 40, 12, 3, fill='#3a3a4e')


def draw_phone(draw, cx, cy, device_color, accent):
    """Draw a stylized smartphone."""
    pw, ph = 56, 120
    px, py = cx - pw // 2, cy - ph // 2
    draw_rounded_rect(draw, px, py, pw, ph, 10, fill=device_color, outline='#2a2a4e', ow=2)
    # Screen
    spx, spy, spw, sph = px + 5, py + 18, pw - 10, ph - 38
    draw_rounded_rect(draw, spx, spy, spw, sph, 4, fill='#2a2a5e')
    # App icons on screen
    icons = [(spx + 8, spy + 8), (spx + 8 + 28, spy + 8),
             (spx + 8, spy + 8 + 28), (spx + 8 + 28, spy + 8 + 28)]
    for ix, iy in icons:
        draw_rounded_rect(draw, ix, iy, 20, 20, 4, fill='#3a3a7e')
    # Camera dot
    draw.ellipse([cx - 3, py + 6, cx + 3, py + 12], fill='#1a1a2e')
    # Home indicator
    draw.rounded_rectangle([cx - 14, py + ph - 8, cx + 14, py + ph - 4], radius=3, fill='#3a3a4e')


def draw_headphone(draw, cx, cy, device_color, accent):
    """Draw stylized over-ear headphones."""
    # Headband
    band = [
        (cx - 40, cy + 20),
        (cx - 50, cy - 30),
        (cx, cy - 50),
        (cx + 50, cy - 30),
        (cx + 40, cy + 20),
    ]
    draw.line(band, fill=device_color, width=6, joint='curve')
    # Inner band
    band_inner = [
        (cx - 30, cy + 10),
        (cx - 38, cy - 22),
        (cx, cy - 38),
        (cx + 38, cy - 22),
        (cx + 30, cy + 10),
    ]
    draw.line(band_inner, fill='#2a2a4e', width=3, joint='curve')

    # Ear cups
    ec_w, ec_h = 40, 55
    for ex in [cx - 45, cx + 45]:
        draw_rounded_rect(draw, ex - ec_w // 2, cy - ec_h // 2, ec_w, ec_h, 10, fill=device_color)
        # Inner cup
        draw_rounded_rect(draw, ex - 15, cy - 15, 30, 30, 8, fill='#2a2a5e')
        # Cushion detail
        draw.ellipse([ex - 10, cy - 10, ex + 10, cy + 10], fill='#3a3a6e')

    # Audio wire
    draw.line([(cx, cy + 25), (cx, cy + 45)], fill=device_color, width=2)


def draw_watch(draw, cx, cy, device_color, accent):
    """Draw a stylized smartwatch."""
    # Band - left
    draw.rectangle([cx - 30, cy - 50, cx - 22, cy + 50], fill='#2a2a3e')
    draw.rectangle([cx + 22, cy - 50, cx + 30, cy + 50], fill='#2a2a3e')
    # Band detail lines
    for y in range(cy - 45, cy + 45, 8):
        draw.line([(cx - 29, y), (cx - 23, y)], fill='#3a3a4e', width=1)
        draw.line([(cx + 23, y), (cx + 29, y)], fill='#3a3a4e', width=1)

    # Watch body
    ww, wh = 50, 64
    wx, wy = cx - ww // 2, cy - wh // 2
    draw_rounded_rect(draw, wx, wy, ww, wh, 10, fill=device_color, outline='#2a2a4e', ow=2)
    # Screen
    swx, swy, sww, swh = wx + 5, wy + 6, ww - 10, wh - 20
    draw_rounded_rect(draw, swx, swy, sww, swh, 4, fill='#2a2a5e')
    # Watch face content - time
    draw.line([(swx + 8, swy + 15), (swx + sww - 8, swy + 15)], fill='#3a3a7e', width=2)
    draw.line([(swx + 8, swy + 25), (swx + sww - 15, swy + 25)], fill='#3a3a7e', width=2)
    draw.line([(swx + 8, swy + 35), (swx + sww - 8, swy + 35)], fill='#3a3a7e', width=1)
    # Crown
    draw.rectangle([wx + ww - 2, wy + 12, wx + ww + 6, wy + 22], fill=device_color)


DRAW_DEVICE = {
    'Laptop': draw_laptop,
    'Mobile': draw_phone,
    'Headphone': draw_headphone,
    'Smartwatch': draw_watch,
}


def generate_product_image(product, filepath):
    W, H = 500, 375
    meta = CATEGORY_COLORS.get(product.category, CATEGORY_COLORS['Laptop'])
    c1, c2 = meta['bg']
    accent = meta['accent']
    device_color = meta['device']

    img = Image.new('RGB', (W, H))
    draw = ImageDraw.Draw(img)

    draw_gradient(draw, W, H, c1, c2)

    try:
        fonts = {
            'brand': ImageFont.truetype("arial.ttf", 28),
            'name':  ImageFont.truetype("arial.ttf", 18),
            'price': ImageFont.truetype("arial.ttf", 24),
            'rating':ImageFont.truetype("arial.ttf", 16),
            'tag':   ImageFont.truetype("arial.ttf", 13),
        }
    except Exception:
        f = ImageFont.load_default()
        fonts = {'brand': f, 'name': f, 'price': f, 'rating': f, 'tag': f}

    CX = W // 2
    brand_y = 18

    # Category pill
    ct = product.category.upper()
    tw = len(ct) * 8
    pill_x1, pill_x2 = CX - tw // 2 - 8, CX + tw // 2 + 8
    draw_rounded_rect(draw, pill_x1, 8, pill_x2 - pill_x1, 22, 11, fill=accent + '55')
    draw.text((CX, 19), ct, fill='#ffffffcc', font=fonts['tag'], anchor='mt')

    # Brand name
    draw.text((CX, brand_y + 34), product.brand.upper(), fill='#ffffff', font=fonts['brand'], anchor='mt')

    # Product name
    name_disp = product.name[:32] + ('...' if len(product.name) > 32 else '')
    draw.text((CX, brand_y + 66), name_disp, fill='#cccccc', font=fonts['name'], anchor='mt')

    # Draw device silhouette
    device_y = 105
    draw_func = DRAW_DEVICE.get(product.category, draw_phone)
    draw_func(draw, CX, device_y + 60, device_color, accent)

    # Bottom area - price and rating on a subtle background bar
    bar_y = H - 50
    draw_rounded_rect(draw, 20, bar_y, W - 40, 40, 10, fill='#00000022')

    # Price
    price_text = f"₹ {int(product.price):,}"
    draw.text((40, bar_y + 20), price_text, fill=accent, font=fonts['price'], anchor='lm')

    # Rating
    stars = '★' * int(round(product.rating)) + '☆' * (5 - int(round(product.rating)))
    draw.text((W - 40, bar_y + 18), f"{stars}  {product.rating}", fill='#ffd700', font=fonts['rating'], anchor='rm')

    # Decorative tag line
    tag_text = f"{product.category}  •  {product.brand}"
    draw.text((CX, H - 8), tag_text, fill='#ffffff22', font=fonts['tag'], anchor='mb')

    img.save(filepath, 'JPEG', quality=92, optimize=True)
    return True


class Command(BaseCommand):
    help = 'Generate professional product card images with device silhouettes'

    def handle(self, *args, **options):
        target = os.path.join(settings.MEDIA_ROOT, 'products')
        os.makedirs(target, exist_ok=True)

        products = Product.objects.all().order_by('id')
        total = products.count()
        ok = 0

        for idx, prod in enumerate(products, 1):
            fname = f"product_{prod.id}.jpg"
            dest = os.path.join(target, fname)
            try:
                generate_product_image(prod, dest)
                prod.image = f'products/{fname}'
                prod.save(update_fields=['image'])
                ok += 1
                self.stdout.write(f"[{idx}/{total}] {prod.brand} {prod.name}")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"[{idx}/{total}] FAILED: {e}"))

        self.stdout.write(self.style.SUCCESS(f"\nDone! {ok}/{total} product images generated"))
