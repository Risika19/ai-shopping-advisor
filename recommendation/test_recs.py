import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from recommendation.utils import (
    extract_budget, extract_category, extract_brand,
    extract_keywords, get_recommendations
)
from products.models import Product


PASS = 0
FAIL = 0


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name} {detail}")


print("=" * 70)
print("RECOMMENDATION ENGINE — COMPREHENSIVE TEST SUITE")
print("=" * 70)

print("\n--- Budget Extraction Tests ---")
tests = [
    ("under 50000", 50000),
    ("below 20000", 20000),
    ("less than 10000", 10000),
    ("within 30000", 30000),
    ("upto 45000", 45000),
    ("up to 25000", 25000),
    ("max 60000", 60000),
    ("maximum 55000", 55000),
    ("budget 40000", 40000),
    ("budget of 35000", 35000),
    ("around 15000", 15000),
    ("near 8000", 8000),
    ("approximately 70000", 70000),
    ("laptop under 50000 for gaming", 50000),
    ("under 50000", 50000),
    ("price is 25000", 25000),
    ("laptop under 50k", 50000),
    ("phone under 20k", 20000),
    ("under 15k", 15000),
    ("budget 30k laptop", 30000),
    ("no budget mentioned", None),
    ("cheap laptop", None),
    ("under 99", None),
    ("hp laptop under 60000", 60000),
    ("samsung phone under 30000", 30000),
    ("smartwatch below 15000", 15000),
    ("gaming laptop under 70000", 70000),
    ("headphones under 5000", 5000),
]
for query, expected in tests:
    result = extract_budget(query)
    check(f'extract_budget("{query}") -> {result}',
          result == expected,
          f'(expected {expected}, got {result})')

print("\n--- Category Extraction Tests ---")
cat_tests = [
    ("laptop for gaming", "Laptop"),
    ("best phone under 20000", "Mobile"),
    ("wireless earphones", "Headphone"),
    ("earbuds", "Headphone"),
    ("smartwatch", "Smartwatch"),
    ("gaming mobile", "Mobile"),
    ("laptops", "Laptop"),
    ("smartphones", "Mobile"),
    ("headphones", "Headphone"),
    ("watch", "Smartwatch"),
    ("no category here", None),
    ("hp laptop under 60000", "Laptop"),
    ("samsung phone under 30000", "Mobile"),
    ("gaming laptop under 70000", "Laptop"),
]
for query, expected in cat_tests:
    result = extract_category(query)
    check(f'extract_category("{query}") -> {result}',
          result == expected,
          f'(expected {expected}, got {result})')

print("\n--- Brand Extraction Tests ---")
brand_tests = [
    ("hp laptop", "Hp"),
    ("samsung phone", "Samsung"),
    ("dell laptop", "Dell"),
    ("apple macbook", "Apple"),
    ("asus laptop", "Asus"),
    ("lenovo thinkpad", "Lenovo"),
    ("oneplus phone", "Oneplus"),
    ("realme mobile", "Realme"),
    ("no brand", None),
    ("hp laptop under 60000", "Hp"),
    ("samsung phone under 30000", "Samsung"),
    ("gaming laptop under 70000", None),
    ("smartwatch below 15000", None),
    ("headphones under 5000", None),
    ("asus laptop", "Asus"),
    ("iQOO phone", "Iqoo"),
]
for query, expected in brand_tests:
    result = extract_brand(query)
    check(f'extract_brand("{query}") -> {result}',
          result == expected,
          f'(expected {expected}, got {result})')

print("\n--- Keyword Extraction Tests ---")
kw_tests = [
    ("gaming laptop under 50000", "Laptop", None, None, ["gaming"]),
    ("hp laptop for programming", "Laptop", "Hp", None, ["programming"]),
    ("camera phone", "Mobile", "Samsung", None, ["camera"]),
]
for query, cat, br, bg, expected_kws in kw_tests:
    result = extract_keywords(query, cat, br, bg)
    check(f'extract_keywords("{query}") -> {result}',
          all(kw in result for kw in expected_kws),
          f'(expected to contain {expected_kws}, got {result})')

print("\n=== Full Recommendation Engine Tests ===")
print("(uses actual database products)\n")


def test_recommendation(query, expected_max_price=None, expected_category=None, expected_brand=None):
    global PASS, FAIL
    recs, exceeded = get_recommendations(query)
    prices = [float(p.price) for p in recs]
    count = len(recs)
    max_p = max(prices) if prices else 0

    print(f'  Query: "{query}"')
    print(f'    Results: {count}, max price: Rs {max_p:,.0f}, exceeded: {exceeded}')

    if expected_max_price and prices:
        over = [float(p) for p in prices if float(p) > expected_max_price]
        if over:
            if exceeded:
                print(f'    NOTE: {len(over)} products exceed Rs {expected_max_price:,.0f} '
                      f'(budget exceeded fallback)')
                PASS += 1
            else:
                print(f'    FAIL: {len(over)} products exceed Rs {expected_max_price:,.0f}: '
                      f'{", ".join(f"Rs {x:,.0f}" for x in over)}')
                FAIL += 1
        else:
            print(f'    PASS: All {count} products within Rs {expected_max_price:,.0f}')
            PASS += 1

        for p in recs:
            pp = float(p.price)
            status = "OK" if pp <= expected_max_price else "OVER"
            print(f'      [{status}] {p.brand} {p.name} ({p.category}) Rs {pp:,.0f}')

    if expected_category and recs:
        all_match = all(p.category.lower() == expected_category.lower() for p in recs)
        if all_match:
            print(f'    PASS: All products match category "{expected_category}"')
            PASS += 1
        else:
            cats = set(p.category for p in recs)
            print(f'    FAIL: Not all products match category "{expected_category}": {cats}')
            FAIL += 1

    if expected_brand and recs:
        all_match = all(p.brand.lower() == expected_brand.lower() for p in recs)
        if all_match:
            print(f'    PASS: All products match brand "{expected_brand}"')
            PASS += 1
        else:
            brands = set(p.brand for p in recs)
            print(f'    FAIL: Not all products match brand "{expected_brand}": {brands}')
            FAIL += 1

    if exceeded:
        print(f'    NOTE: Budget exceeded flag is True')

    print()
    return recs, exceeded


# === STRICT BUDGET TESTS ===
print("=" * 70)
print("STRICT BUDGET ENFORCEMENT TESTS")
print("=" * 70)

test_recommendation('laptop under 50000', expected_max_price=50000, expected_category='Laptop')
test_recommendation('hp laptop under 60000', expected_max_price=60000, expected_category='Laptop', expected_brand='Hp')
test_recommendation('samsung phone under 25000', expected_max_price=25000, expected_category='Mobile', expected_brand='Samsung')
test_recommendation('gaming laptop under 70000', expected_max_price=70000, expected_category='Laptop')
test_recommendation('smartwatch below 15000', expected_max_price=15000, expected_category='Smartwatch')
test_recommendation('headphones under 5000', expected_max_price=5000, expected_category='Headphone')

# === CROSS-CATEGORY BUDGET TESTS ===
print("=" * 70)
print("CROSS-CATEGORY & EDGE CASE TESTS")
print("=" * 70)

test_recommendation('phone under 20000', expected_max_price=20000, expected_category='Mobile')
test_recommendation('laptop under 100000', expected_max_price=100000, expected_category='Laptop')
test_recommendation('watch under 10000', expected_max_price=10000, expected_category='Smartwatch')

# === TEST: VERY LOW BUDGET (should trigger fallback) ===
print("--- Testing Very Low Budget (fallback expected) ---")
recs, exceeded = test_recommendation('laptop under 1000', expected_max_price=1000, expected_category='Laptop')
check('Budget exceeded flag should be True for impossible budget', exceeded,
      '(budget_exceeded should be True)')

# === TEST: NO BUDGET QUERY ===
print("--- Testing Query Without Budget ---")
recs, exceeded = get_recommendations('gaming laptop')
check('Query without budget should return results', len(recs) > 0)

# === TEST: BUDGET EXCEEDED FALLBACK ===
print("--- Testing Budget Exceeded Fallback ---")
recs, exceeded = get_recommendations('laptop under 1000')
check('Fallback should return some products when budget too low', len(recs) > 0 or exceeded,
      '(either products or exceeded flag should be present)')

# === FINAL SUMMARY ===
print("=" * 70)
print(f"RESULTS: {PASS} passed, {FAIL} failed out of {PASS + FAIL} tests")
print("=" * 70)

if FAIL == 0:
    print("\n*** ALL TESTS PASSED! ***")
else:
    print(f"\n*** {FAIL} TEST(S) FAILED! ***")

sys.exit(0 if FAIL == 0 else 1)
