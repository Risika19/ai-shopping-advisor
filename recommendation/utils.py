"""
Recommendation Engine — Content-Based Filtering using TF-IDF and Cosine Similarity.
"""

import re
import logging
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from products.models import Product

logger = logging.getLogger(__name__)

BUDGET_PATTERNS = [
    r'(?:under|below|less\s*than|within|upto|up\s*to|max(?:imum)?)\s*[₹]?\s*([\d,]+)(?:\s*k\b)?',
    r'(?:under|below|less\s*than|within|upto|up\s*to|max(?:imum)?)\s*[₹]?\s*(\d+)\s*k\b',
    r'(?:budget|price)\s*(?:is|of)?\s*[₹]?\s*([\d,]+)(?:\s*k\b)?',
    r'(?:around|near|approximately|about)\s*[₹]?\s*([\d,]+)(?:\s*k\b)?',
    r'[₹]\s*([\d,]+)(?:\s*k\b)?',
    r'(?:^|\s)(\d{5,})\s*(?:rs|rupees|inr)?(?:\s|$)',
]

CATEGORY_KEYWORDS = {
    'laptop': 'Laptop',
    'laptops': 'Laptop',
    'notebook': 'Laptop',
    'mobile': 'Mobile',
    'phone': 'Mobile',
    'phones': 'Mobile',
    'smartphone': 'Mobile',
    'smartphones': 'Mobile',
    'headphone': 'Headphone',
    'headphones': 'Headphone',
    'earphone': 'Headphone',
    'earphones': 'Headphone',
    'earbuds': 'Headphone',
    'ear buds': 'Headphone',
    'watch': 'Smartwatch',
    'watches': 'Smartwatch',
    'smartwatch': 'Smartwatch',
    'smartwatches': 'Smartwatch',
}

BRAND_NAMES = [
    'apple', 'samsung', 'hp', 'h.p.', 'dell', 'lenovo', 'asus', 'acer',
    'xiaomi', 'redmi', 'realme', 'oneplus', 'one plus', 'oppo', 'vivo',
    'poco', 'iQOO', 'iqoo', 'nothing', 'google', 'sony', 'boat',
    'noise', 'jbl', 'sennheiser', 'bose', 'mi', 'microsoft', 'msi',
    'alienware', 'lg', 'marshall', 'beats', 'motorola', 'moto',
    'amazfit', 'fitbit', 'garmin', 'fire-boltt', 'fireboltt',
]

STOP_KEYWORDS = {'under', 'below', 'less', 'than', 'within', 'upto',
                 'up', 'to', 'max', 'maximum', 'budget', 'price', 'for',
                 'and', 'the', 'with', 'best', 'good', 'great', 'cheap',
                 'around', 'near', 'approximately', 'about', 'under',
                 'rupees', 'inr'}


def _clean_number(num_str):
    num_str = num_str.replace(',', '').strip()
    try:
        return int(num_str)
    except ValueError:
        return None


def extract_budget(text):
    text_lower = text.lower()

    k_multiplier = 1
    for pattern in BUDGET_PATTERNS:
        match = re.search(pattern, text_lower, re.IGNORECASE)
        if match:
            raw = match.group(1).replace(',', '').strip()
            try:
                value = int(raw)
            except ValueError:
                continue
            if 'k' in text_lower and value < 1000:
                value *= 1000
            if value < 100:
                continue
            return value

    match = re.search(r'(?:^|\s)(\d+)\s*k\b(?!\s*\d)', text_lower)
    if match:
        value = int(match.group(1)) * 1000
        if value >= 1000:
            return value

    return None


def extract_category(text):
    text_lower = text.lower()
    matches = []
    for keyword, category in CATEGORY_KEYWORDS.items():
        if keyword in text_lower:
            matches.append((len(keyword), category))
    if matches:
        matches.sort(key=lambda x: -x[0])
        return matches[0][1]
    return None


def extract_brand(text):
    text_lower = text.lower()
    matches = []
    for brand in BRAND_NAMES:
        escaped = re.escape(brand)
        if re.search(r'(?<![a-z])' + escaped + r'(?![a-z])', text_lower):
            title = brand.title()
            if brand == 'h.p.':
                title = 'Hp'
            matches.append((len(brand), title))
    if matches:
        matches.sort(key=lambda x: -x[0])
        return matches[0][1]
    return None


def extract_keywords(text, category=None, brand=None, budget=None):
    text_lower = text.lower()
    tokens = re.findall(r'[a-zA-Z]+', text_lower)
    stop_words = STOP_KEYWORDS | set()
    if category:
        stop_words.add(category.lower())
    if brand:
        stop_words.add(brand.lower())
    keywords = []
    for token in tokens:
        if token not in stop_words and len(token) > 2:
            keywords.append(token)
    return keywords


def build_feature_matrix(products):
    data = []
    for p in products:
        text = f"{p.name} {p.brand} {p.category} {p.description} {p.features} {p.processor}"
        data.append({
            'id': p.id,
            'text': text.lower(),
            'price': float(p.price),
            'category': p.category,
            'brand': p.brand,
            'rating': float(p.rating),
            'name': p.name,
        })
    return pd.DataFrame(data)


def get_recommendations(user_input, top_n=8):
    user_text = user_input.lower().strip()

    budget = extract_budget(user_text)
    category = extract_category(user_text)
    brand = extract_brand(user_text)
    keywords = extract_keywords(user_text, category, brand, budget)

    logger.info("=" * 60)
    logger.info("RECOMMENDATION ENGINE DEBUG")
    logger.info(f"User Query: {user_input}")
    logger.info(f"Extracted Category: {category}")
    logger.info(f"Extracted Brand: {brand}")
    logger.info(f"Extracted Budget: {budget}")
    logger.info(f"Extracted Keywords: {keywords}")

    all_products = Product.objects.all()
    total_count = all_products.count()
    logger.info(f"Total Products in DB: {total_count}")

    budget_exceeded = False
    candidate_products = all_products

    if category:
        candidate_products = candidate_products.filter(category__iexact=category)
        logger.info(f"After category filter ('{category}'): {candidate_products.count()}")

    if brand:
        candidate_products = candidate_products.filter(brand__iexact=brand)
        logger.info(f"After brand filter ('{brand}'): {candidate_products.count()}")

    budget_filtered = candidate_products
    if budget:
        budget_filtered = candidate_products.filter(price__lte=budget)
        count_budget = budget_filtered.count()
        logger.info(f"After budget filter (<= {budget}): {count_budget}")

        if count_budget == 0:
            budget_exceeded = True
            logger.warning("NO products found within budget. Falling back to closest alternatives.")
            budget_filtered = candidate_products.order_by('price')[:top_n]
        else:
            logger.info(f"Budget filter satisfied. Products within budget.")
    else:
        budget_filtered = candidate_products

    df = build_feature_matrix(budget_filtered)
    if df.empty:
        logger.warning("Empty feature matrix. No recommendations.")
        return Product.objects.none(), budget_exceeded

    logger.info(f"Products in feature matrix: {len(df)}")
    for _, row in df.iterrows():
        logger.info(f"  Product: {row['name']} | Category: {row['category']} | Price: {row['price']} | Brand: {row['brand']}")

    vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)
    all_texts = df['text'].tolist() + [user_text]
    tfidf_matrix = vectorizer.fit_transform(all_texts)

    user_vector = tfidf_matrix[-1]
    product_vectors = tfidf_matrix[:-1]

    similarities = cosine_similarity(user_vector, product_vectors).flatten()
    df['similarity'] = similarities

    df['bonus'] = 0.0

    if category:
        df['bonus'] += df['category'].str.lower().apply(
            lambda x: 0.10 if x == category.lower() else 0
        )

    if brand:
        df['bonus'] += df['brand'].str.lower().apply(
            lambda x: 0.08 if x == brand.lower() else 0
        )

    if keywords:
        def keyword_match(row_text):
            match_count = sum(1 for kw in keywords if kw in row_text)
            return min(match_count * 0.03, 0.20)
        df['bonus'] += df['text'].apply(keyword_match)

    rating_max = df['rating'].max()
    if rating_max > 0:
        df['rating_bonus'] = (df['rating'] / rating_max) * 0.10
    else:
        df['rating_bonus'] = 0

    df['score'] = df['similarity'] + df['bonus'] + df['rating_bonus']
    df = df.sort_values('score', ascending=False)

    top = df.head(top_n)
    recommended_ids = top['id'].tolist()

    logger.info(f"\nFinal Recommended Products (top {top_n}):")
    for _, row in top.iterrows():
        logger.info(f"  -> {row['name']} | "
                     f"Category: {row['category']} | "
                     f"Price: ₹{row['price']:,.0f} | "
                     f"Rating: {row['rating']} | "
                     f"Similarity: {row['similarity']:.4f} | "
                     f"Bonus: {row['bonus']:.4f} | "
                     f"RatingBonus: {row['rating_bonus']:.4f} | "
                     f"Score: {row['score']:.4f}")

    if budget:
        over_budget = top[top['price'] > budget]
        if not over_budget.empty:
            logger.error(f"BUG CHECK: {len(over_budget)} products exceed budget!")
            for _, row in over_budget.iterrows():
                logger.error(f"  OVER BUDGET: {row['name']} - ₹{row['price']:,.0f} > {budget}")
        else:
            logger.info(f"VERIFIED: All {len(top)} recommended products are within budget ₹{budget}")

    ids_order = {pid: idx for idx, pid in enumerate(recommended_ids)}
    products_qs = Product.objects.filter(id__in=recommended_ids)
    products_qs = sorted(products_qs, key=lambda p: ids_order.get(p.id, 9999))

    from django.db.models import Case, When, Value, IntegerField
    preserved = Case(*[When(id=pid, then=Value(idx)) for idx, pid in enumerate(recommended_ids)],
                     output_field=IntegerField())
    products_qs = Product.objects.filter(id__in=recommended_ids).order_by(preserved)

    return products_qs, budget_exceeded
