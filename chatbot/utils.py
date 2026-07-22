import re
import logging
from decimal import Decimal
from django.db.models import Q, Min
from products.models import Product
from .services import rank_by_similarity, find_similar_products

logger = logging.getLogger(__name__)

# ============================================================
# INTENT DEFINITIONS
# ============================================================
INTENT_GREETING = 'greeting'
INTENT_GOODBYE = 'goodbye'
INTENT_THANKS = 'thanks'
INTENT_HELP = 'help'
INTENT_RECOMMENDATION = 'recommendation'
INTENT_COMPARISON = 'comparison'
INTENT_PRODUCT_DETAILS = 'product_details'
INTENT_GENERAL = 'general'

# ============================================================
# PURE SOCIAL PATTERNS — only match if no product terms present
# ============================================================
GREETING_PATTERNS = [
    r'^\s*(hi|hello|hey|howdy|greetings)[.!?]*\s*$',
    r'^\s*(good\s*morning|good\s*afternoon|good\s*evening)[.!?]*\s*$',
    r'^\s*(how\s*are\s*you|how\'?s\s*it\s*going|what\'?s\s*up)[.!?]*\s*$',
    r'^\s*(hi|hello|hey)\s*(there|everyone|bot)[.!?]*\s*$',
]
GOODBYE_PATTERNS = [
    r'^\s*(bye|goodbye|see\s*you|take\s*care|cya|see\s*ya)[.!?]*\s*$',
    r'^\s*(have\s*a\s*great\s*day|thanks?\s*bye)[.!?]*\s*$',
]
THANKS_PATTERNS = [
    r'^\s*(thanks?|thank\s*you|appreciate\s*it|thx|ty)[.!?]*\s*$',
    r'^\s*(thanks?\s*a\s*lot|thank\s*you\s*so\s*much)[.!?]*\s*$',
]
HELP_PATTERNS = [
    r'^\s*(help|what\s*can\s*you\s*do|how\s*(?:does\s*this|do\s*you)\s*work|capabilities|features?)[.!?]*\s*$',
]
COMPARISON_KEYWORDS = ['compare', 'vs', 'versus', 'difference between', 'which is better']
PRODUCT_DETAILS_KEYWORDS = ['tell me about', 'details of', 'details about', 'info about', 'information about',
                             'specs of', 'specifications of', 'show me', 'describe']

# ============================================================
# PRODUCT KEYWORDS — if any of these appear, it's not a social intent
# ============================================================
PRODUCT_KEYWORDS = [
    'laptop', 'mobile', 'phone', 'smartphone', 'notebook',
    'headphone', 'earphone', 'earbuds', 'watch', 'smartwatch',
    'buy', 'purchase', 'price', 'cost', 'budget', 'under',
    'rupees', 'rs', 'recommend', 'suggest', 'show', 'find',
    'need', 'want', 'looking', 'search', 'gaming', 'cheap',
    'best', 'top', 'compare', 'vs', 'versus',
    'ram', 'gb', 'storage', 'processor', 'intel', 'amd',
    'snapdragon', 'battery', 'camera', 'display', 'amoled',
    '5g', '4g',
]

# ============================================================
# CATEGORY MAPPING
# ============================================================
CATEGORY_KEYWORDS = {
    'laptop': 'Laptop', 'laptops': 'Laptop', 'notebook': 'Laptop',
    'mobile': 'Mobile', 'phone': 'Mobile', 'phones': 'Mobile',
    'smartphone': 'Mobile', 'smartphones': 'Mobile',
    'headphone': 'Headphone', 'headphones': 'Headphone',
    'earphone': 'Headphone', 'earphones': 'Headphone',
    'earbuds': 'Headphone', 'ear buds': 'Headphone',
    'watch': 'Smartwatch', 'watches': 'Smartwatch',
    'smartwatch': 'Smartwatch', 'smartwatches': 'Smartwatch',
}
CATEGORY_ALIASES = {
    'iphone': 'Mobile', 'ipad': 'Laptop',
}

# ============================================================
# BRAND MAPPING with fuzzy aliases
# ============================================================
BRAND_MAP = {
    'apple': 'Apple', 'iphone': 'Apple', 'macbook': 'Apple', 'mac': 'Apple',
    'samsung': 'Samsung', 'galaxy': 'Samsung',
    'oneplus': 'OnePlus', 'one plus': 'OnePlus',
    'xiaomi': 'Xiaomi', 'redmi': 'Xiaomi', 'mi': 'Xiaomi', 'poco': 'Xiaomi',
    'realme': 'Realme',
    'oppo': 'Oppo',
    'vivo': 'Vivo',
    'nothing': 'Nothing',
    'google': 'Google', 'pixel': 'Google',
    'motorola': 'Motorola', 'moto': 'Motorola',
    'sony': 'Sony', 'xperia': 'Sony',
    'lg': 'LG',
    'hp': 'HP', 'h.p.': 'HP', 'hewlett packard': 'HP',
    'dell': 'Dell',
    'lenovo': 'Lenovo', 'thinkpad': 'Lenovo', 'ideapad': 'Lenovo', 'legion': 'Lenovo',
    'asus': 'Asus', 'rog': 'Asus',
    'acer': 'Acer', 'predator': 'Acer',
    'msi': 'MSI',
    'microsoft': 'Microsoft', 'surface': 'Microsoft',
    'alienware': 'Alienware',
    'boat': 'boAt', 'noise': 'Noise', 'jbl': 'JBL',
    'sennheiser': 'Sennheiser', 'bose': 'Bose', 'marshall': 'Marshall',
    'beats': 'Beats',
    'amazfit': 'Amazfit', 'fitbit': 'Fitbit', 'garmin': 'Garmin',
    'fire-boltt': 'Fire-Boltt', 'fireboltt': 'Fire-Boltt',
}

# ============================================================
# SPECIFICATION EXTRACTION
# ============================================================
BUDGET_PATTERNS = [
    r'(?:under|below|less\s*than|within|upto|up\s*to|max(?:imum)?|around|near|approximately|about)\s*(?:₹|rs\.?\s*)?(\d[\d,]*)\s*(?:k\b)?',
    r'(?:budget|price)\s*(?:is|of|:)?\s*(?:₹|rs\.?\s*)?(\d[\d,]*)\s*(?:k\b)?',
    r'(?:for|at)\s*(?:₹|rs\.?\s*)?(\d[\d,]+)\s*(?:k\b)?',
    r'(?:^|\s)(\d{5,})\s*(?:rs|rupees|inr)?(?:\s|$)',
    r'(?:^|\s)(\d{1,3}(?:,\d{3})*)\s*(?:rs|rupees|inr)?(?:\s|$)',
    r'[₹]\s*(\d[\d,]*)(?:\s*k\b)?',
]

RAM_PATTERNS = [
    r'(\d+)\s*(?:GB|gb)\s*(?:RAM|ram|memory|of\s*ram|of\s*RAM)',
    r'(\d+)\s*[Gg][Bb]\s*(?!.*(?:storage|ssd|hdd|rom))',
]

STORAGE_PATTERNS = [
    r'(\d+)\s*(?:GB|gb|TB|tb)\s*(?:SSD|ssd|storage|rom|internal|HDD|hdd)',
    r'(\d+)\s*(?:[Gg][Bb]|[Tt][Bb])\s*(?:storage|ssd|hdd|rom)',
]

PROCESSOR_PATTERNS = [
    (r'\bi[3579][-\s]?\d{4,5}[A-Z]?\b', 'i7'),
    (r'\b(?:intel\s*)?core\s*i[3579]\b', 'i5'),
    (r'\bi[3579]\b', 'i5'),
    (r'\bryzen\s*[3579]\b', 'Ryzen 7'),
    (r'\bsnapdragon\s*(?:8\s*(?:gen\s*[12]|elite)|8\s*gen\s*[123])\b', 'Snapdragon 8 Gen'),
    (r'\bsnapdragon\s*\d+\s*(?:gen\s*\d+)?\b', 'Snapdragon'),
    (r'\b(?:mediatek|dimensity)\s*\d+\b', 'Dimensity'),
    (r'\bapple\s*m([1234])\b', 'M1'),
    (r'\bm([1234])\s*(?:pro|max|ultra)?\b', 'M'),
    (r'\bexynos\s*\d+\b', 'Exynos'),
    (r'\btensor\b', 'Tensor'),
]

DISPLAY_PATTERNS = [
    (r'\b(?:super\s*)?amoled\b', 'AMOLED'),
    (r'\bolded\b', 'OLED'),
    (r'\blcd\b', 'LCD'),
    (r'\bips\b', 'IPS'),
    (r'\bretina\b', 'Retina'),
    (r'\bliquid\s*retina\b', 'Liquid Retina'),
    (r'\bmini\s*led\b', 'Mini LED'),
]

SCREEN_SIZE_PATTERNS = [
    r'(\d+(?:\.\d+)?)\s*(?:-?\s*)?(?:inch|inches|"|″)',
]

BATTERY_PATTERNS = [
    r'(\d{3,4})\s*m[AH]ah',
    r'(\d{3,4})mah',
]

CAMERA_PATTERNS = [
    r'(\d+)\s*(?:MP|megapixel|megapixels)',
    r'(\d+)\s*mp',
]

OS_PATTERNS = [
    r'\b(android|iOS|macOS|windows|ipados)\b',
]

RATING_PATTERNS = [
    r'(\d+(?:\.\d+)?)\s*(?:star|rating|★|⭐)',
    r'(?:rating|rated)\s*(?:of|:)?\s*(\d+(?:\.\d+)?)\s*(?:\/5|out\s*of\s*5)?',
    r'(?:above|over|min)\s*(\d+(?:\.\d+)?)\s*(?:star|rating)',
    r'(?:rating|rated)\s+(?:above|over|min|>=?)\s+(\d+(?:\.\d+)?)',
]

COLOR_PATTERNS = [
    r'\b(black|white|silver|gray|grey|gold|rose\s*gold|blue|red|green|purple|pink|space\s*gray|midnight|starlight|graphite|sierra\s*blue|alpine\s*green|deep\s*purple)\b',
]

CONNECTIVITY_PATTERNS = [
    r'\b(5G|4G|LTE|WiFi\s*6|wifi\s*6e|bluetooth|nfc|usb\s*c)\b',
]

REFRESH_RATE_PATTERNS = [
    r'(\d+)\s*(?:Hz|hz|refresh\s*rate)',
]


# ============================================================
# INTENT DETECTION (improved — social only if pure)
# ============================================================

def _has_product_keywords(text):
    text_lower = text.lower()
    for kw in PRODUCT_KEYWORDS:
        if kw in text_lower:
            return True
    return False


def detect_intent(message):
    text_lower = message.lower().strip()
    has_products = _has_product_keywords(text_lower)

    if not has_products:
        for p in GREETING_PATTERNS:
            if re.search(p, text_lower, re.IGNORECASE):
                return INTENT_GREETING
        for p in GOODBYE_PATTERNS:
            if re.search(p, text_lower, re.IGNORECASE):
                return INTENT_GOODBYE
        for p in THANKS_PATTERNS:
            if re.search(p, text_lower, re.IGNORECASE):
                return INTENT_THANKS
        for p in HELP_PATTERNS:
            if re.search(p, text_lower, re.IGNORECASE):
                return INTENT_HELP

    for kw in COMPARISON_KEYWORDS:
        if kw in text_lower:
            return INTENT_COMPARISON

    for kw in PRODUCT_DETAILS_KEYWORDS:
        if kw in text_lower:
            return INTENT_PRODUCT_DETAILS

    if has_products:
        return INTENT_RECOMMENDATION

    extra_keywords = ['find', 'search', 'looking for', 'need', 'want', 'suggest',
                      'recommend', 'show', 'list', 'looking', 'wanted', 'recommendation']
    for kw in extra_keywords:
        if kw in text_lower:
            return INTENT_RECOMMENDATION

    return INTENT_GENERAL


# ============================================================
# FIELD EXTRACTION
# ============================================================

def _extract_budget(text):
    text_lower = text.lower()
    for pattern in BUDGET_PATTERNS:
        match = re.search(pattern, text_lower)
        if match:
            raw = match.group(1).replace(',', '')
            try:
                val = int(raw)
                if val < 100:
                    continue
                if 'k' in text_lower[match.end()-1:match.end()+2]:
                    val *= 1000
                return val
            except ValueError:
                continue
    return None


def _extract_number(text):
    nums = re.findall(r'\b(\d{4,})\b', text)
    if nums:
        return int(nums[0])
    return None


def _extract_category(text):
    text_lower = text.lower()
    for keyword, category in CATEGORY_KEYWORDS.items():
        if re.search(r'\b' + re.escape(keyword) + r'\b', text_lower):
            return category
    for alias, category in CATEGORY_ALIASES.items():
        if re.search(r'\b' + re.escape(alias) + r'\b', text_lower):
            return category
    return None


def _extract_brand(text):
    text_lower = text.lower()
    matches = []
    for alias, brand in BRAND_MAP.items():
        pattern = r'(?<![a-z0-9])' + re.escape(alias) + r'(?![a-z0-9])'
        if re.search(pattern, text_lower):
            matches.append((len(alias), brand))
    if not matches:
        for alias, brand in BRAND_MAP.items():
            if len(alias) >= 4 and alias in text_lower:
                matches.append((len(alias), brand))
    if matches:
        best = max(matches, key=lambda x: x[0])
        return best[1]
    return None


def _extract_all_specs(text):
    text_lower = text.lower()
    specs = {}

    # RAM
    ram_matches = []
    for p in RAM_PATTERNS:
        for m in re.finditer(p, text_lower):
            try:
                v = m.group(1)
                ram_matches.append((len(m.group()), v))
            except (IndexError, ValueError):
                continue
    if ram_matches:
        best = max(ram_matches, key=lambda x: x[0])
        specs['ram'] = f"{best[1]}GB"

    # Storage
    storage_matches = []
    for p in STORAGE_PATTERNS:
        for m in re.finditer(p, text_lower):
            try:
                v = m.group(1)
                unit = 'TB' if 'tb' in m.group().lower() else 'GB'
                storage_matches.append((len(m.group()), v, unit))
            except (IndexError, ValueError):
                continue
    if storage_matches:
        best = max(storage_matches, key=lambda x: x[0])
        specs['storage'] = f"{best[1]}{best[2]}"

    # Processor
    for pattern, default in PROCESSOR_PATTERNS:
        m = re.search(pattern, text_lower, re.IGNORECASE)
        if m:
            specs['processor'] = m.group(0).strip().title()[:50]
            break

    # Display type
    for pattern, value in DISPLAY_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            specs['display'] = value
            break

    # Screen size
    for p in SCREEN_SIZE_PATTERNS:
        m = re.search(p, text_lower)
        if m:
            specs['screen_size'] = m.group(1)
            break

    # Battery
    for p in BATTERY_PATTERNS:
        m = re.search(p, text_lower)
        if m:
            specs['battery'] = f"{m.group(1)}mAh"
            break

    # Camera
    for p in CAMERA_PATTERNS:
        m = re.search(p, text_lower)
        if m:
            specs['camera'] = f"{m.group(1)}MP"
            break

    # OS
    for p in OS_PATTERNS:
        m = re.search(p, text_lower)
        if m:
            specs['os'] = m.group(1).strip().title()
            break

    # Color
    for p in COLOR_PATTERNS:
        m = re.search(p, text_lower)
        if m:
            specs['color'] = m.group(1).strip().title()
            break

    # Connectivity
    for p in CONNECTIVITY_PATTERNS:
        m = re.search(p, text_lower)
        if m:
            specs['connectivity'] = m.group(1).upper()
            break

    # Refresh rate
    for p in REFRESH_RATE_PATTERNS:
        m = re.search(p, text_lower)
        if m:
            specs['refresh_rate'] = f"{m.group(1)}Hz"
            break

    # Rating
    for p in RATING_PATTERNS:
        m = re.search(p, text_lower)
        if m:
            try:
                v = float(m.group(1))
                if v > 5:
                    v = v / 10
                specs['rating'] = min(v, 5.0)
            except ValueError:
                continue
            break

    return specs


def _extract_filters(message):
    filters = {}
    filters['budget'] = _extract_budget(message)
    filters['category'] = _extract_category(message)
    filters['brand'] = _extract_brand(message)
    specs = _extract_all_specs(message)
    filters.update(specs)
    return {k: v for k, v in filters.items() if v is not None}


# ============================================================
# PURPOSE MAPPING — chips shown when user hasn't specified a preference
# ============================================================

PURPOSE_CHIPS = [
    ('📷 Camera', 'camera'),
    ('🎮 Gaming', 'gaming'),
    ('🔋 Battery', 'battery'),
    ('⚡ Fast Charging', 'fast charging'),
    ('💾 8GB RAM', '8GB RAM'),
    ('💾 12GB RAM', '12GB RAM'),
    ('💽 256GB Storage', '256GB storage'),
    ('📱 AMOLED Display', 'AMOLED'),
    ('💼 Office Use', 'office'),
    ('🎓 Student', 'student'),
    ('🚀 Performance', 'performance'),
]

PURPOSE_FILTERS = {
    'gaming': {'ram': '16GB', 'storage': '512GB'},
    'camera': {'camera': '48MP'},
    'battery': {'battery': '5000mAh'},
    'performance': {'ram': '16GB'},
    'fast charging': {'battery': '5000mAh'},
}


class ConversationContext:
    """Structured multi-turn conversation state stored in ChatSession.context."""

    FIELDS = ['category', 'budget', 'brand', 'ram', 'storage', 'processor',
              'display', 'battery', 'camera', 'purpose', 'waiting_for',
              'has_shown_products']

    def __init__(self, session=None):
        self.session = session
        self.data = dict(session.context or {}) if session else {}

    def get(self, key, default=None):
        return self.data.get(key, default)

    def __setitem__(self, key, value):
        if value is not None:
            self.data[key] = value

    def __getitem__(self, key):
        return self.data[key]

    def __contains__(self, key):
        return key in self.data

    def merge(self, filters):
        for key, value in filters.items():
            if value is not None:
                self.data[key] = value

    def save(self):
        if self.session:
            self.session.context = self.data
            self.session.save(update_fields=['context'])

    def clear(self):
        self.data = {}
        self.save()

    def to_filters(self):
        return {k: v for k, v in self.data.items()
                if k not in ('waiting_for', 'has_shown_products', 'purpose') and v is not None}

    @property
    def can_search(self):
        return bool(self.get('category')) and (
            bool(self.get('budget')) or
            any(self.get(k) for k in ('ram', 'storage', 'processor', 'brand', 'purpose'))
        )


# ============================================================
# PRODUCT FILTERING (ORM-first — category isolation enforced)
# ============================================================

def filter_products(filters):
    qs = Product.objects.all()
    applied = {}

    cat = filters.get('category')
    if cat:
        qs = qs.filter(category__iexact=cat)
        applied['category'] = cat

    brand = filters.get('brand')
    if brand:
        qs = qs.filter(brand__iexact=brand)
        applied['brand'] = brand

    budget = filters.get('budget')
    if budget:
        qs = qs.filter(price__lte=budget)
        applied['budget'] = budget

    ram = filters.get('ram', '')
    if ram:
        num = re.sub(r'[^0-9]', '', ram)
        if num:
            qs = qs.filter(ram__icontains=f'{num}GB')
            applied['ram'] = ram

    storage = filters.get('storage', '')
    if storage:
        val = re.sub(r'[^0-9A-Za-z]', '', storage)
        if val:
            qs = qs.filter(
                Q(storage__icontains=val) |
                Q(storage__icontains=val.replace('GB', ' GB '))
            )
            applied['storage'] = storage

    processor = filters.get('processor', '')
    if processor:
        for term in processor.lower().split():
            if len(term) > 1:
                qs = qs.filter(
                    Q(processor__icontains=term) |
                    Q(name__icontains=term) |
                    Q(description__icontains=term)
                )
        applied['processor'] = processor

    display = filters.get('display', '')
    if display:
        qs = qs.filter(Q(display__icontains=display) | Q(features__icontains=display))
        applied['display'] = display

    screen_size = filters.get('screen_size', '')
    if screen_size:
        qs = qs.filter(Q(display__icontains=screen_size) | Q(description__icontains=screen_size))
        applied['screen_size'] = screen_size

    battery = filters.get('battery', '')
    if battery:
        num = re.sub(r'[^0-9]', '', battery)
        if num:
            qs = qs.filter(battery__icontains=num)
            applied['battery'] = battery

    camera = filters.get('camera', '')
    if camera:
        num = re.sub(r'[^0-9]', '', camera)
        if num:
            qs = qs.filter(camera__icontains=f'{num}MP')
            applied['camera'] = camera

    rating = filters.get('rating')
    if rating is not None:
        qs = qs.filter(rating__gte=rating)
        applied['rating'] = rating

    connectivity = filters.get('connectivity', '')
    if connectivity:
        qs = qs.filter(
            Q(description__icontains=connectivity) |
            Q(name__icontains=connectivity) |
            Q(features__icontains=connectivity)
        )
        applied['connectivity'] = connectivity

    os_val = filters.get('os', '')
    if os_val:
        qs = qs.filter(
            Q(description__icontains=os_val) |
            Q(name__icontains=os_val) |
            Q(features__icontains=os_val)
        )
        applied['os'] = os_val

    color = filters.get('color', '')
    if color:
        qs = qs.filter(
            Q(description__icontains=color) |
            Q(name__icontains=color) |
            Q(features__icontains=color)
        )
        applied['color'] = color

    refresh_rate = filters.get('refresh_rate', '')
    if refresh_rate:
        qs = qs.filter(
            Q(display__icontains=refresh_rate) |
            Q(features__icontains=refresh_rate)
        )
        applied['refresh_rate'] = refresh_rate

    return qs.distinct(), applied


# ============================================================
# RELAXED SEARCH — find closest alternatives within same category
# ============================================================

def _relaxed_search(filters, applied, max_results=6):
    category = filters.get('category')
    if not category:
        return None, "No products found matching your search."

    base_qs = Product.objects.filter(category__iexact=category)
    if not base_qs.exists():
        return None, f"No {category} products found in our catalog."

    budget = filters.get('budget')
    brand = filters.get('brand')

    relaxed = base_qs
    kept_filters = []

    if budget:
        budget_qs = base_qs.filter(price__lte=budget)
        if budget_qs.exists():
            relaxed = budget_qs
            kept_filters.append(f"under ₹{int(budget):,}")
        else:
            min_price = base_qs.aggregate(m=Min('price'))['m']
            if min_price:
                max_budget = int(float(min_price) * 1.5)
                relaxed = base_qs.filter(price__lte=max_budget)

    if brand:
        brand_qs = relaxed.filter(brand__iexact=brand)
        if brand_qs.exists():
            relaxed = brand_qs
            kept_filters.append(brand)

    ram = filters.get('ram', '')
    if ram:
        num = re.sub(r'[^0-9]', '', ram)
        if num:
            for try_val in [num, str(int(num) - 4), str(int(num) - 2)]:
                if int(try_val) <= 0:
                    continue
                ram_qs = relaxed.filter(ram__icontains=f'{try_val}GB')
                if ram_qs.exists():
                    relaxed = ram_qs
                    kept_filters.append(f"{try_val}GB RAM")
                    break

    storage = filters.get('storage', '')
    if storage:
        val = re.sub(r'[^0-9]', '', storage)
        if val:
            storage_qs = relaxed.filter(
                Q(storage__icontains=val) |
                Q(storage__icontains=f'{val}GB')
            )
            if not storage_qs.exists():
                for try_val in [str(int(int(val)/2)), str(int(int(val)*0.75))]:
                    try_qs = relaxed.filter(
                        Q(storage__icontains=try_val) |
                        Q(storage__icontains=f'{try_val}GB')
                    )
                    if try_qs.exists():
                        storage_qs = try_qs
                        kept_filters.append(f"{try_val}GB storage")
                        break
            if storage_qs.exists():
                relaxed = storage_qs

    processor = filters.get('processor', '')
    if processor:
        proc_qs = relaxed.filter(
            Q(processor__icontains=processor.lower()[:10]) |
            Q(name__icontains=processor.lower()[:10])
        )
        if proc_qs.exists():
            relaxed = proc_qs
            kept_filters.append(processor)

    return relaxed.distinct().order_by('-rating', 'price')[:max_results], None


# ============================================================
# FORMATTING
# ============================================================

def _format_price(price):
    try:
        return f"₹{int(price):,}"
    except (ValueError, TypeError):
        return f"₹{price}"


def _get_specs_list(product):
    specs = []
    if product.ram:
        specs.append(f"RAM: {product.ram}")
    if product.storage:
        specs.append(f"Storage: {product.storage}")
    if product.processor:
        specs.append(f"{product.processor}")
    if product.display:
        specs.append(f"Display: {product.display}")
    if product.battery:
        specs.append(f"Battery: {product.battery}")
    if product.camera:
        specs.append(f"Camera: {product.camera}")
    return specs


def generate_product_card(product):
    specs = _get_specs_list(product)
    specs_str = " | ".join(specs)
    image_url = product.image.url if product.image else '/static/images/placeholder.svg'
    rating_display = f'★ {product.rating}/5' if product.rating else ''

    return f'''
    <div class="product-card d-flex align-items-start gap-3 p-3 mb-3 rounded" style="background:#2b2f35;">
        <img src="{image_url}" alt="{product.name}"
             style="width:100px;height:100px;object-fit:cover;border-radius:8px;flex-shrink:0;"
             onerror="this.style.display='none';this.nextElementSibling.style.display='flex'">
        <div style="display:none;width:100px;height:100px;background:#3a3f47;border-radius:8px;align-items:center;justify-content:center;flex-shrink:0;">
            <i class="bi bi-box-seam text-muted fs-1"></i>
        </div>
        <div class="flex-grow-1" style="min-width:0;">
            <div class="d-flex justify-content-between align-items-start gap-2 flex-wrap">
                <h6 class="mb-1 text-white" style="font-size:0.95rem;">{product.brand} {product.name}</h6>
                <div class="h5 mb-0 text-nowrap" style="color:#0d6efd;font-weight:700;">{_format_price(product.price)}</div>
            </div>
            <div class="d-flex flex-wrap gap-1 mb-2">
                <span class="badge bg-secondary">{product.brand}</span>
                <span class="badge bg-info">{product.category}</span>
                {f'<span class="badge bg-warning text-dark">{rating_display}</span>' if rating_display else ''}
            </div>
            <div class="small mb-2" style="color:#adb5bd;line-height:1.5;">
                {specs_str}
            </div>
            <div class="d-flex gap-2 flex-wrap">
                <a href="/products/{product.pk}/" class="btn btn-sm btn-outline-primary" target="_blank">View Details</a>
                <a href="/orders/cart/add/{product.pk}/" class="btn btn-sm btn-outline-light">Add to Cart</a>
                <a href="/orders/buy-now/{product.pk}/" class="btn btn-sm btn-success">Buy Now</a>
            </div>
        </div>
    </div>'''


def generate_comparison_table(products):
    if not products or len(products) < 2:
        return None

    rows = [
        ('Price', lambda p: _format_price(p.price)),
        ('RAM', lambda p: p.ram or '—'),
        ('Storage', lambda p: p.storage or '—'),
        ('Processor', lambda p: p.processor or '—'),
        ('Display', lambda p: p.display or '—'),
        ('Battery', lambda p: p.battery or '—'),
        ('Camera', lambda p: p.camera or '—'),
        ('Rating', lambda p: f'★ {p.rating}/5' if p.rating else '—'),
    ]

    html = '<div class="table-responsive mb-3"><table class="table table-bordered table-dark mb-0" style="font-size:0.85rem;">'
    html += '<thead><tr><th style="width:100px;">Specification</th>'
    for p in products:
        html += f'<th style="text-align:center;">{p.brand} {p.name}</th>'
    html += '</tr></thead><tbody>'
    for label, fn in rows:
        html += f'<tr><td style="font-weight:600;">{label}</td>'
        for p in products:
            html += f'<td style="text-align:center;">{fn(p)}</td>'
        html += '</tr>'
    html += '</tbody></table></div>'
    return html


# ============================================================
# RESPONSE BUILDERS
# ============================================================

def _conversational_response(intent):
    responses = {
        INTENT_GREETING: (
            "Hello! 👋<br><br>"
            "How can I help you today?<br><br>"
            "You can ask things like:<br>"
            "• 📱 Best phone under ₹30,000<br>"
            "• 💻 Laptop with 16GB RAM<br>"
            "• 📱 Samsung phone under ₹25,000<br>"
            "• 📊 Compare iPhone vs Samsung"
        ),
        INTENT_GOODBYE: (
            "Thank you for visiting <strong>ShopAI</strong>! 😊<br><br>"
            "Have a wonderful day! 🛍️<br><br>"
            "Come back anytime you need shopping help!"
        ),
        INTENT_THANKS: (
            "You're welcome! 😊<br><br>"
            "Happy shopping! If you need anything else, I'm here to help."
        ),
        INTENT_HELP: (
            "Here's what I can help you with:<br><br>"
            "🔍 <strong>Find Products</strong> — \"Show me gaming laptops under ₹70,000\"<br>"
            "📊 <strong>Compare Products</strong> — \"Compare iPhone 15 and Galaxy S24\"<br>"
            "💰 <strong>Budget Shopping</strong> — \"Best phones under ₹25,000\"<br>"
            "📋 <strong>Spec Search</strong> — \"8GB RAM laptop with 512GB SSD\"<br>"
            "🏷️ <strong>Brand Search</strong> — \"Samsung phones with AMOLED display\"<br><br>"
            "<em>Just type what you're looking for!</em>"
        ),
    }
    return responses.get(intent)


def _general_response(message):
    msg = (
        "<strong>I'm not sure I understood that.</strong><br><br>"
        "Here are some things you can ask me:<br>"
        "• 💻 Suggest a laptop under ₹60,000<br>"
        "• 📱 Best Samsung phone with 8GB RAM<br>"
        "• 🎧 Wireless earbuds under ₹3,000<br>"
        "• 📊 Compare iPhone 15 and Galaxy S24<br>"
        "• ℹ️ What can you help me with?"
    )
    return msg, False


def _refinement_chips(chips):
    if not chips:
        return ''
    html = '<div class="refinement-chips" style="display:flex;flex-wrap:wrap;gap:6px;margin-top:8px;">'
    for label, value in chips:
        html += f'<span class="chip refinement-chip" data-value="{value}" style="cursor:pointer;padding:6px 14px;border-radius:16px;border:1px solid var(--border-dim,#333);background:var(--bg-card,#1e1e28);color:var(--text-main,#e8e8ed);font-size:12px;transition:all .2s;">{label}</span>'
    html += '</div>'
    return html


def _highlight_strengths(product):
    parts = []
    if product.rating and product.rating >= 4.5:
        parts.append(f"<strong>rating of {product.rating}/5</strong>")
    if product.processor:
        parts.append(f"a powerful <strong>{product.processor}</strong> processor")
    if product.ram:
        parts.append(f"<strong>{product.ram}</strong> RAM")
    if product.battery:
        parts.append(f"a long-lasting <strong>{product.battery}</strong> battery")
    if product.camera:
        parts.append(f"an impressive <strong>{product.camera}</strong> camera")
    if product.display:
        parts.append(f"a stunning <strong>{product.display}</strong> display")
    if product.storage:
        parts.append(f"<strong>{product.storage}</strong> storage")
    return ', '.join(parts) or "great specifications"


def _generate_follow_up(products, context):
    """Generate a natural follow-up question and refinement chips after showing products."""
    count = len(products)
    if count == 0:
        return ''

    if count == 1:
        p = products[0]
        strengths = _highlight_strengths(p)
        html = (
            f'<br><br><div style="background:var(--bg-card,#1a1a22);border:1px solid var(--accent);'
            f'border-radius:12px;padding:14px;margin-top:8px;">'
            f'<strong>🎯 Perfect Match!</strong><br><br>'
            f'<strong>{p.brand} {p.name}</strong> is your ideal choice! It offers {strengths}.'
            f'<br><br>What would you like to do next?</div>'
        )
        chips = [
            ('📋 View Details', f'tell me about {p.name}'),
            ('🛒 Add to Cart', f'add {p.name} to cart'),
            ('💰 Show Cheaper', 'cheaper'),
            ('🔄 Compare Others', 'compare alternatives'),
        ]
        html += _refinement_chips(chips)
        return html

    if not context.get('purpose'):
        html = '<br><br><strong>To find your perfect match, what matters most to you?</strong>'
        html += _refinement_chips(PURPOSE_CHIPS)
        return html

    available_brands = sorted(set(p.brand for p in products if p.brand))
    chips = []
    if len(available_brands) > 1 and not context.get('brand'):
        for brand in available_brands[:3]:
            chips.append((f'🏷️ {brand}', f'only {brand}'))

    more_chips = [
        ('💰 Cheaper Options', 'cheaper'),
        ('💾 More RAM', 'more RAM'),
        ('💽 More Storage', 'more storage'),
        ('📷 Better Camera', 'better camera'),
        ('⭐ Higher Rating', 'better rating'),
    ]
    if chips:
        html = '<br><br><strong>Narrow down by brand:</strong>'
        html += _refinement_chips(chips)

    html += '<br><br><strong>Or refine further:</strong>'
    html += _refinement_chips(more_chips)
    html += '<br><br><em>Just type what you\'re looking for — I\'ll keep refining!</em>'
    return html


def _get_purpose_chips():
    return PURPOSE_CHIPS


def _format_with_follow_up(products, applied, filters, context, query=''):
    if not products:
        return _no_results_fallback(filters)

    if query:
        products = rank_by_similarity(query, products)

    intent_like = 'Here are' if context.get('has_shown_products') else 'Here are'
    intro = _build_intro(products, applied)
    cards = ''.join(generate_product_card(p) for p in products[:6])

    result = intro + cards

    if len(products) > 6:
        q = ' '.join(str(v) for v in filters.values() if v)
        result += f'<div class="mt-2"><a href="/products/?q={q}" class="btn btn-sm btn-outline-info" target="_blank">View all {len(products)} matching products →</a></div>'

    follow_up = _generate_follow_up(products, context)
    result += follow_up

    return result, True


def _build_intro(products, applied):
    cat = applied.get('category', '')
    brand = applied.get('brand', '')
    budget = applied.get('budget')
    ram = applied.get('ram', '')
    storage = applied.get('storage', '')

    count = len(products)

    if count == 1:
        return "<strong>Based on your preferences, here's the perfect match:</strong><br><br>"

    if budget and cat:
        intro = f"<strong>Great choices! Here are {cat} options under ₹{int(budget):,}:</strong><br><br>"
    elif budget:
        intro = f"<strong>Here are products under ₹{int(budget):,}:</strong><br><br>"
    elif brand and cat:
        intro = f"<strong>Here are {brand} {cat} options you might like:</strong><br><br>"
    elif cat:
        intro = f"<strong>Great {cat} options for you:</strong><br><br>"
    else:
        intro = f"<strong>Here's what I found for you:</strong><br><br>"

    intro += f"<small class='text-muted'>Found {count} product{'s' if count != 1 else ''}</small><br>"
    return intro


def _no_results_fallback(filters):
    category = filters.get('category', '')
    ram = filters.get('ram', '')

    relaxed_products, err = _relaxed_search(filters, {})
    if relaxed_products:
        ram_note = ''
        if ram:
            ram_note = f" with {ram}"
        label = category or 'your search'
        msg = (
            f"<strong>I couldn't find an exact match for {label}{ram_note}.</strong><br><br>"
            f"Here are the closest {label} alternatives :<br><br>"
        )
        cards = ''.join(generate_product_card(p) for p in relaxed_products[:6])
        return msg + cards, True

    if category:
        cat_products = Product.objects.filter(category__iexact=category).order_by('-rating', 'price')[:6]
        if cat_products:
            msg = (
                f"<strong>No {category} match your exact requirements.</strong><br><br>"
                f"Here are our top-rated {category} products:<br><br>"
            )
            cards = ''.join(generate_product_card(p) for p in cat_products)
            return msg + cards, True

    msg = "<strong>I couldn't find any matching products.</strong><br><br>"
    msg += "Try different keywords, adjust your budget, or browse a different category."
    return msg, True


def _ask_budget(context):
    cat = context.get('category', 'product')
    return f"Great choice! 🎯<br><br>What's your budget for the {cat}? Just tell me a number like 30000 or 50000.", True


def _ask_category(context):
    other = []
    if context.get('budget'):
        other.append(f"budget of ₹{int(context['budget']):,}")
    if context.get('ram'):
        other.append(f"{context['ram']} RAM")
    if context.get('storage'):
        other.append(f"{context['storage']} storage")
    other_text = ' with ' + ', '.join(other) if other else ''

    return (
        f"I see you're looking for{other_text}.<br><br>"
        f"What type of product are you looking for?<br><br>"
        f"📱 Mobile / Phone<br>"
        f"💻 Laptop<br>"
        f"🎧 Headphone / Earbuds<br>"
        f"⌚ Smartwatch<br><br>"
        f"<em>Just type the product type you're interested in!</em>"
    ), True


# ============================================================
# REFINEMENT DETECTION — handle follow-up messages after products are shown
# ============================================================

def _handle_refinement(message, context):
    """Detect and apply refinement intent from a follow-up message. Returns True if a refinement was applied."""
    text_lower = message.lower().strip()

    # Cheaper options
    if any(kw in text_lower for kw in ['cheaper', 'cheap', 'lower price', 'less expensive', 'affordable', 'budget friendly']):
        budget = context.get('budget')
        if budget:
            context['budget'] = int(budget * 0.7)
        else:
            products = Product.objects.filter(category__iexact=context.get('category', ''))
            if products.exists():
                avg = sum(float(p.price) for p in products if p.price) / max(products.count(), 1)
                context['budget'] = int(avg * 0.6)
            else:
                context['budget'] = 15000
        return True

    # Cheaper alternatives / compare alternatives
    if any(kw in text_lower for kw in ['compare alternatives', 'other options', 'alternatives']):
        budget = context.get('budget')
        if budget:
            context['budget'] = int(budget * 1.2)
        context.pop('brand', None)
        context.pop('ram', None)
        context.pop('storage', None)
        context.pop('camera', None)
        return True

    # More RAM
    if any(kw in text_lower for kw in ['more ram', 'higher ram', 'increase ram', '16gb ram']):
        context['ram'] = '16GB'
        return True
    if any(kw in text_lower for kw in ['12gb ram']):
        context['ram'] = '12GB'
        return True
    if any(kw in text_lower for kw in ['8gb ram']):
        context['ram'] = '8GB'
        return True

    # More storage
    if any(kw in text_lower for kw in ['more storage', 'higher storage', 'more space', '1tb', '512gb storage']):
        context['storage'] = '512GB'
        return True
    if any(kw in text_lower for kw in ['256gb storage']):
        context['storage'] = '256GB'
        return True

    # Only [brand]
    brand_match = re.search(r'(?:only|just|show|from|filter)\s*(?:from\s*)?(\w+(?:\s+\w+)?)', text_lower)
    if brand_match:
        potential = brand_match.group(1)
        brand = _extract_brand(potential)
        if brand:
            context['brand'] = brand
            return True

    # Better camera
    if any(kw in text_lower for kw in ['better camera', 'good camera', 'best camera', 'great camera']):
        context['camera'] = '48MP'
        return True

    # Higher rating
    if any(kw in text_lower for kw in ['better rating', 'top rated', 'best rated', 'highly rated', 'higher rated']):
        context['rating'] = 4.5
        return True

    # AMOLED / OLED display
    if any(kw in text_lower for kw in ['amoled', 'oled display', 'amoled display']):
        context['display'] = 'AMOLED'
        return True

    # Purpose keywords
    purpose_map = {
        'fast charging': 'fast charging',
        'battery life': 'battery',
        'gaming': 'gaming', 'game': 'gaming',
        'camera': 'camera', 'photography': 'camera', 'photo': 'camera',
        'battery': 'battery',
        'performance': 'performance', 'fast': 'performance',
        'office': 'office', 'work': 'office', 'professional': 'office',
        'student': 'student', 'college': 'student',
    }
    sorted_kws = sorted(purpose_map.keys(), key=len, reverse=True)
    for kw in sorted_kws:
        if kw in text_lower:
            purpose = purpose_map[kw]
            context['purpose'] = purpose
            context.merge(PURPOSE_FILTERS.get(purpose, {}))
            return True

    # Extract specs from message (covers chip values like "8GB RAM", "256GB storage", etc.)
    specs = _extract_all_specs(message)
    if specs:
        context.merge(specs)
        return True

    return False


def extract_comparison_products(message):
    text = message
    found = []
    all_products = list(Product.objects.all())

    # Try to find brand+model patterns
    words = text.split()
    for i, w in enumerate(words):
        for p in all_products:
            name_lower = f"{p.brand} {p.name}".lower()
            if p.brand.lower() in text.lower() and p.name.lower() in text.lower():
                if p not in found:
                    found.append(p)
                    break

    if len(found) >= 2:
        return found[:2]

    # Try fuzzy matching on brand names
    for p in all_products:
        if p not in found:
            brand_aliases = [k for k, v in BRAND_MAP.items() if v == p.brand]
            for alias in brand_aliases:
                if alias in text.lower():
                    if p not in found:
                        found.append(p)
                        break
        if len(found) >= 2:
            break

    return found[:2]


def _comparison_response(message):
    products = extract_comparison_products(message)

    if len(products) < 2:
        msg = (
            "<strong>I'd be happy to compare products!</strong><br><br>"
            "Please mention two products like:<br>"
            "• \"Compare iPhone 15 and Galaxy S24\"<br>"
            "• \"HP Victus vs Lenovo LOQ\"<br>"
            "• \"Which is better between MacBook Air and Dell XPS?\""
        )
        return msg, False

    table = generate_comparison_table(products)
    msg = f"<strong>Comparison: {products[0].brand} {products[0].name} vs {products[1].brand} {products[1].name}</strong><br><br>{table}"
    return msg, True


def _product_details_response(message):
    text_lower = message.lower()
    brand = _extract_brand(message)
    category = _extract_category(message)

    qs = Product.objects.all()
    if brand:
        qs = qs.filter(brand__iexact=brand)
    if category:
        qs = qs.filter(category__iexact=category)

    # Try to match product name in message
    name_match = None
    for p in qs:
        if p.name.lower() in text_lower or text_lower.split()[-1].lower() in p.name.lower():
            name_match = p
            break

    if not name_match and qs.exists():
        name_match = qs.first()

    if not name_match:
        msg = (
            "<strong>I couldn't find that product.</strong><br><br>"
            "Please specify a product name like:<br>"
            "• \"Tell me about Galaxy S24\"<br>"
            "• \"Show me MacBook Air M3\"<br>"
            "• \"Details of iPhone 15\""
        )
        return msg, False

    p = name_match
    specs = []
    if p.ram: specs.append(f"<strong>RAM:</strong> {p.ram}")
    if p.storage: specs.append(f"<strong>Storage:</strong> {p.storage}")
    if p.processor: specs.append(f"<strong>Processor:</strong> {p.processor}")
    if p.display: specs.append(f"<strong>Display:</strong> {p.display}")
    if p.battery: specs.append(f"<strong>Battery:</strong> {p.battery}")
    if p.camera: specs.append(f"<strong>Camera:</strong> {p.camera}")
    if p.rating: specs.append(f"<strong>Rating:</strong> ★ {p.rating}/5")
    specs_str = '<br>'.join(specs)

    price_str = f"₹{int(p.price):,}" if p.price else 'N/A'
    img = p.image.url if p.image else '/static/images/placeholder.svg'
    desc = p.description or ''

    msg = f"""
    <div class="product-detail-card p-3 mb-3 rounded" style="background:#2b2f35;">
        <div class="d-flex flex-wrap gap-3 align-items-start">
            <img src="{img}" alt="{p.name}" style="width:150px;height:150px;object-fit:cover;border-radius:12px;flex-shrink:0;">
            <div style="flex:1;min-width:200px;">
                <h5 class="text-white mb-1">{p.brand} {p.name}</h5>
                <div class="d-flex gap-2 mb-2 flex-wrap">
                    <span class="badge bg-secondary">{p.brand}</span>
                    <span class="badge bg-info">{p.category}</span>
                    {f'<span class="badge bg-warning text-dark">★ {p.rating}/5</span>' if p.rating else ''}
                </div>
                <h4 style="color:#0d6efd;font-weight:700;">{price_str}</h4>
                <p style="color:#adb5bd;font-size:13px;">{desc[:200]}</p>
            </div>
        </div>
        <hr style="border-color:#3a3f47;">
        <h6 class="text-white mb-2">📋 Specifications</h6>
        <div style="color:#adb5bd;font-size:13px;line-height:2;">{specs_str}</div>
        <hr style="border-color:#3a3f47;">
        <div class="d-flex gap-2 flex-wrap">
            <a href="/products/{p.pk}/" class="btn btn-primary btn-sm" target="_blank">View Full Details</a>
            <a href="/orders/cart/add/{p.pk}/" class="btn btn-outline-light btn-sm">Add to Cart</a>
            <a href="/orders/buy-now/{p.pk}/" class="btn btn-success btn-sm">Buy Now</a>
        </div>
    </div>
    <div class="mt-2">
        <small class="text-muted">🔍 Similar products you might like:</small>
    </div>
    """
    similar = find_similar_products(f"{p.brand} {p.name} {p.category}", category=p.category, max_results=3)
    for sp in similar:
        if sp.pk != p.pk:
            msg += generate_product_card(sp)

    return msg, True


def generate_title(message):
    text_lower = message.lower()

    if re.search(r'\bcompare\b', text_lower) or re.search(r'\bvs\b', text_lower):
        return "Product Comparison"

    category = _extract_category(message)
    brand = _extract_brand(message)
    ram = _extract_all_specs(message).get('ram', '')

    if brand and category:
        return f"{brand} {category}"
    if category and ram:
        return f"{ram} {category}"

    if 'gaming' in text_lower:
        cat = category or 'Products'
        return f"Gaming {cat}"

    if category:
        return f"{category} Recommendation"
    if brand:
        return f"{brand} Products"

    if 'under' in text_lower:
        budget = _extract_budget(message)
        if budget:
            cat = category or 'Products'
            return f"{cat} under ₹{int(budget):,}"

    raw = message.strip()[:40]
    if len(raw) > 30:
        raw = raw[:30] + '...'
    return raw


# ============================================================
# MAIN ASSISTANT FUNCTION
# ============================================================

def ask_assistant(user_message, session=None, user=None):
    message = user_message.strip()
    if not message:
        return "Please enter a message.", False

    intent = detect_intent(message)
    logger.info(f"Intent: {intent} | msg: {message[:80]}")

    # Pure social intents — never show products
    if intent == INTENT_GREETING:
        return _conversational_response(INTENT_GREETING), True
    if intent == INTENT_GOODBYE:
        return _conversational_response(INTENT_GOODBYE), True
    if intent == INTENT_THANKS:
        return _conversational_response(INTENT_THANKS), True
    if intent == INTENT_HELP:
        return _conversational_response(INTENT_HELP), True

    # Comparison
    if intent == INTENT_COMPARISON:
        return _comparison_response(message)

    # Product Details
    if intent == INTENT_PRODUCT_DETAILS:
        return _product_details_response(message)

    # Use structured conversation context
    ctx = ConversationContext(session)

    # Check if this is a refinement after products were shown
    if ctx.get('has_shown_products'):
        refined = _handle_refinement(message, ctx)
        if refined:
            ctx.save()
            filters = ctx.to_filters()
            products, applied = filter_products(filters)
            if products.exists():
                resp, ok = _format_with_follow_up(products, applied, filters, ctx, query=message)
                _log_search_analytics(message, filters, products.count(), user)
                return resp, ok
            relaxed, err = _relaxed_search(filters, applied)
            if relaxed:
                resp, ok = _format_with_follow_up(relaxed, applied, filters, ctx, query=message)
                _log_search_analytics(message, filters, relaxed.count(), user)
                return resp, ok
            ctx.clear()
            return _no_results_fallback(filters)

    # Extract filters from current message
    new_filters = _extract_filters(message)

    # Handle waiting_for (bot asked a question in previous turn)
    waiting_for = ctx.get('waiting_for')
    if waiting_for:
        ctx.data.pop('waiting_for', None)
    if waiting_for and not new_filters.get(waiting_for):
        if waiting_for == 'budget':
            num = _extract_number(message)
            if num:
                new_filters['budget'] = num
        elif waiting_for == 'category':
            cat = _extract_category(message)
            if cat:
                new_filters['category'] = cat
        elif waiting_for == 'brand':
            brand = _extract_brand(message)
            if brand:
                new_filters['brand'] = brand

    # Merge new filters into context
    ctx.merge(new_filters)

    if ctx.can_search:
        filters = ctx.to_filters()
        products, applied = filter_products(filters)

        if products.exists():
            ctx['has_shown_products'] = True
            ctx.save()
            resp, ok = _format_with_follow_up(products, applied, filters, ctx, query=message)
            _log_search_analytics(message, filters, products.count(), user)
            return resp, ok

        # No exact matches — try relaxed search
        relaxed, err = _relaxed_search(filters, applied)
        if relaxed:
            ctx['has_shown_products'] = True
            ctx.save()
            resp, ok = _format_with_follow_up(relaxed, applied, filters, ctx, query=message)
            _log_search_analytics(message, filters, relaxed.count(), user)
            return resp, ok

        resp, ok = _no_results_fallback(filters)
        ctx.clear()
        _log_search_analytics(message, filters, 0, user)
        return resp, ok

    # Not enough info — ask for more
    if ctx.get('category'):
        ctx['waiting_for'] = 'budget'
        resp = _ask_budget(ctx)
    elif ctx.get('budget') or ctx.get('ram') or ctx.get('storage') or ctx.get('processor') or ctx.get('brand'):
        ctx['waiting_for'] = 'category'
        resp = _ask_category(ctx)
    else:
        return _general_response(message)

    ctx.save()
    return resp


def _log_search_analytics(message, filters, count, user):
    try:
        SearchAnalytics.objects.create(
            query=message[:200],
            category=filters.get('category', '') or '',
            brand=filters.get('brand', '') or '',
            budget=filters.get('budget'),
            ram=filters.get('ram', ''),
            storage=filters.get('storage', ''),
            processor=filters.get('processor', ''),
            results_count=count,
            user=user if user and user.is_authenticated else None,
        )
    except Exception as e:
        logger.error(f"Analytics error: {e}")


from .models import SearchAnalytics
