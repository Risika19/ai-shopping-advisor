"""
Sentiment Analysis Module — Classifies review text using TextBlob.

How it works:
    TextBlob is an NLP library built on top of NLTK and Pattern.
    It provides two key metrics:
        - Polarity: -1 (most negative) to +1 (most positive), 0 = neutral
        - Subjectivity: 0 (factual/objective) to 1 (opinionated/subjective)

    Classification thresholds:
        Polarity > 0.2  → Positive
        Polarity < -0.2 → Negative
        Otherwise       → Neutral
"""

from textblob import TextBlob


def analyze_sentiment(text):
    """
    Analyze the sentiment of a given text string.

    Uses TextBlob to compute polarity and subjectivity scores,
    then maps the polarity to a human-readable label.

    Args:
        text (str): The review/comment text to analyze.

    Returns:
        dict: {
            'label': 'Positive' | 'Neutral' | 'Negative',
            'polarity': float (-1 to 1),
            'subjectivity': float (0 to 1)
        }

    Example:
        >>> analyze_sentiment("This product is amazing!")
        {'label': 'Positive', 'polarity': 0.75, 'subjectivity': 0.6}
    """
    blob = TextBlob(text)
    polarity = blob.sentiment.polarity
    subjectivity = blob.sentiment.subjectivity

    if polarity > 0.2:
        label = 'Positive'
    elif polarity < -0.2:
        label = 'Negative'
    else:
        label = 'Neutral'

    return {
        'label': label,
        'polarity': round(polarity, 3),
        'subjectivity': round(subjectivity, 3),
    }
