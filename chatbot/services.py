import re
import logging
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from products.models import Product

logger = logging.getLogger(__name__)


def build_product_corpus(products):
    corpus = []
    for p in products:
        text = ' '.join([
            p.name or '',
            p.brand or '',
            p.category or '',
            p.processor or '',
            p.display or '',
            p.description or '',
            p.features or '',
            f"ram {p.ram}" if p.ram else '',
            f"storage {p.storage}" if p.storage else '',
            f"battery {p.battery}" if p.battery else '',
            f"camera {p.camera}" if p.camera else '',
        ])
        corpus.append(text.lower())
    return corpus


def rank_by_similarity(query, products):
    if not products or not query:
        return products

    try:
        corpus = build_product_corpus(products)
        documents = [query.lower()] + corpus

        vectorizer = TfidfVectorizer(
            max_features=500,
            stop_words='english',
            ngram_range=(1, 2),
        )
        tfidf_matrix = vectorizer.fit_transform(documents)
        query_vec = tfidf_matrix[0:1]
        doc_vecs = tfidf_matrix[1:]

        similarities = cosine_similarity(query_vec, doc_vecs).flatten()

        scored = list(zip(products, similarities))
        scored.sort(key=lambda x: (-x[1], -float(x[0].rating or 0), float(x[0].price or 0)))

        return [p for p, s in scored]
    except Exception as e:
        logger.error(f"TF-IDF ranking error: {e}")
        return products.order_by('-rating', 'price')


def find_similar_products(query, category=None, max_results=6):
    qs = Product.objects.all()
    if category:
        qs = qs.filter(category__iexact=category)
    products = list(qs)
    if not products:
        return []
    ranked = rank_by_similarity(query, products)
    return ranked[:max_results]
