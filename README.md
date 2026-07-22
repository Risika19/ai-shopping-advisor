# AI Shopping Advisor

An intelligent e-commerce product recommendation system built with Django, Machine Learning, and OpenAI.

## Features

- **AI Shopping Assistant** — Natural language chat powered by OpenAI GPT-4o-mini. Ask "I need a laptop under ₹60,000" and get personalized recommendations.
- **Smart Recommendations** — Content-based filtering engine using TF-IDF vectorization and Cosine Similarity (scikit-learn).
- **Product Catalog** — Browse 80+ products across Laptops, Mobiles, Headphones, and Smartwatches with search, category/brand/price filters.
- **Side-by-Side Comparison** — Compare up to 4 products on all specs (Price, RAM, Storage, Processor, Battery, Display, Camera, Rating).
- **Sentiment Analysis** — User reviews classified as Positive/Neutral/Negative using TextBlob.
- **User Dashboard** — Recently viewed products, favorites, recommendation history.
- **Authentication** — Registration, login, logout, profile management with Bootstrap 5 UI.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 6.0, Python 3.13 |
| Frontend | Bootstrap 5.3, Bootstrap Icons |
| Database | SQLite |
| ML/AI | scikit-learn (TF-IDF, Cosine Similarity), Pandas, NumPy |
| NLP | TextBlob, spaCy, NLTK |
| AI Chat | OpenAI GPT-4o-mini |
| Storage | python-dotenv for env vars |

## Project Structure

```
ai_shopping_advisor/
├── accounts/              # User authentication app
│   ├── templates/accounts/
│   │   ├── login.html
│   │   ├── register.html
│   │   └── profile.html
│   ├── forms.py           # UserRegisterForm, UserUpdateForm
│   ├── views.py           # register(), profile()
│   └── urls.py
├── products/              # Product catalog app
│   ├── templates/products/
│   │   ├── product_list.html
│   │   ├── product_detail.html
│   │   └── compare.html
│   ├── templatetags/
│   │   └── product_extras.py  # Custom template filter (split)
│   ├── management/commands/
│   │   └── load_products.py   # CSV data loader
│   ├── models.py          # Product, Review
│   ├── forms.py           # ReviewForm
│   ├── views.py           # product_list, product_detail, compare
│   ├── sentiment.py       # TextBlob sentiment analysis
│   ├── admin.py
│   └── urls.py
├── recommendation/        # ML recommendation engine
│   ├── templates/recommendation/
│   │   └── recommend.html
│   ├── utils.py           # TF-IDF + Cosine Similarity engine
│   ├── views.py           # recommend()
│   └── urls.py
├── chatbot/               # OpenAI-powered chat
│   ├── templates/chatbot/
│   │   └── chatbot.html
│   ├── utils.py           # OpenAI API integration
│   ├── views.py           # chatbot_view()
│   └── urls.py
├── dashboard/             # User dashboard
│   ├── templates/dashboard/
│   │   └── dashboard.html
│   ├── models.py          # RecentlyViewed, Favorite, RecommendationHistory
│   ├── views.py           # dashboard(), add_favorite()
│   ├── admin.py
│   └── urls.py
├── config/                # Django project config
│   ├── settings.py        # All project settings
│   ├── urls.py            # Root URL routing
│   ├── views.py           # Home page view
│   ├── wsgi.py
│   └── asgi.py
├── templates/             # Shared templates
│   ├── base.html          # Base template with navbar, footer, Bootstrap 5
│   └── home.html          # Landing page
├── static/                # Static files (CSS, JS, images)
├── media/                 # Uploaded product images
├── dataset/               # Product CSV data
│   └── products.csv       # 83 products across 4 categories
├── manage.py              # Django CLI
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (API keys)
└── .gitignore
```

## Installation

### 1. Clone & Setup

```bash
cd ai_shopping_advisor
python -m venv venv

# Windows
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Set Environment Variables

Create `.env` file in the root directory:

```env
SECRET_KEY=django-insecure-your-secret-key
DEBUG=True
OPENAI_API_KEY=sk-your-openai-api-key
```

### 3. Load Data & Run

```bash
python manage.py migrate
python manage.py load_products
python manage.py runserver
```

Visit `http://127.0.0.1:8000`

## ML Algorithm Details

### Content-Based Filtering (`recommendation/utils.py`)

**TF-IDF (Term Frequency-Inverse Document Frequency)**
- Converts product text (name, brand, description, features, processor) into numerical vectors
- Words appearing frequently in a product but rarely across all products get higher weight
- `TfidfVectorizer` from scikit-learn with `stop_words='english'` and `max_features=1000`

**Cosine Similarity**
- Measures the cosine of the angle between the user's query vector and each product vector
- Range: 0 (completely different) to 1 (identical)
- Products with highest similarity scores are recommended

**Keyword Category Bonus**
- Boosts score by +0.05 when the query matches a known product category (laptop, mobile, headphone, smartwatch)

### Sentiment Analysis (`products/sentiment.py`)

**TextBlob**
- NLP library built on NLTK and Pattern
- Returns `polarity` (-1 to 1) and `subjectivity` (0 to 1)
- Thresholds: > 0.2 = Positive, < -0.2 = Negative, else Neutral

## API Integration

### OpenAI (`chatbot/utils.py`)
- Uses `openai.OpenAI()` client (latest SDK v2.x)
- Model: `gpt-4o-mini` (fast, cost-effective)
- System prompt includes product database context (first 30 products)
- Temperature 0.7 for balanced creativity
- Max 500 tokens per response
- Error handling for missing/invalid API keys

## Testing

```bash
python manage.py test
```

20 tests covering:
- User registration and authentication
- Product model CRUD and search/filter
- Recommendation engine relevance
- Chatbot error handling
- Dashboard tracking and favorites

## Django Concepts Used

| Concept | Implementation |
|---|---|
| **MVT Architecture** | Models (Product, Review), Views (function-based), Templates (Django Template Language) |
| **URL Routing** | `include()` in root `urls.py`, app-level `urls.py` files |
| **Class-based vs Function-based Views** | `LoginView` (CBV) for auth, custom FBVs for business logic |
| **Decorators** | `@login_required` for protected views |
| **Session Management** | Comparison list stored in `request.session` |
| **Messages Framework** | `messages.success/warning/info()` with Bootstrap alerts |
| **Custom Management Commands** | `load_products` command to import CSV data |
| **Custom Template Tags** | `split` filter in `product_extras.py` |
| **Model Relationships** | `ForeignKey` (Review → Product, Favorite → User) |
| **Admin Customization** | `list_display`, `list_filter`, `search_fields` |
| **Static & Media Files** | `STATIC_URL`, `MEDIA_URL` configured in settings |
