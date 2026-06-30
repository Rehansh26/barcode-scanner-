"""
Lightweight bag-of-words / TF-IDF utilities for Barcode Inventory.

No external ML dependencies (no numpy / scikit-learn) by design - this stays a small,
readable implementation so the retrieval mechanics are easy to follow end to end.
It backs two features:

  1. The global search bar (inventory.views.search_results) - ranks Items, Categories,
     and Locations against a free-text query.
  2. The RAG retrieval step for the AI chat assistant
     (inventory.tasks.generate_chat_response_task) - finds the most relevant
     inventory records to ground an Ollama answer in real data instead of letting
     the model guess.
"""
import math
import re
from collections import Counter

from .models import Category, Item, Location

_STOPWORDS = {
    'a', 'an', 'the', 'and', 'or', 'of', 'in', 'on', 'at', 'to', 'for',
    'is', 'are', 'was', 'were', 'be', 'been', 'this', 'that', 'with',
    'do', 'does', 'i', 'have', 'has', 'my', 'me', 'it', 'us', 'we',
    'what', 'which', 'who', 'about', 'tell', 'show', 'all', 'any', 'please',
}

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text):
    """Lowercase + strip punctuation + drop stopwords -> list of word tokens."""
    if not text:
        return []
    tokens = _TOKEN_RE.findall(text.lower())
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 1]


def bag_of_words(tokens):
    """tokens -> {word: count} term-frequency vector."""
    return Counter(tokens)


class Document:
    """A single searchable/retrievable record: an Item, Category, or Location."""

    def __init__(self, doc_type, object_id, label, text, meta=None):
        self.doc_type = doc_type
        self.object_id = object_id
        self.label = label
        self.text = text
        self.tokens = tokenize(text)
        self.bow = bag_of_words(self.tokens)
        self.meta = meta or {}


def item_document(item):
    text_parts = [
        item.item_name,
        item.description,
        item.barcode_value,
        item.status.replace('_', ' '),
        item.category.name if item.category else '',
        item.location.name if item.location else '',
    ]
    return Document(
        doc_type='item',
        object_id=item.id,
        label=item.item_name,
        text=' '.join(p for p in text_parts if p),
        meta={
            'barcode_value': item.barcode_value,
            'status': item.status,
            'status_display': item.get_status_display(),
            'quantity': item.quantity,
            'category': item.category.name if item.category else None,
            'location': item.location.name if item.location else None,
        },
    )


def category_document(category):
    item_names = ', '.join(category.items.values_list('item_name', flat=True)[:25])
    return Document(
        doc_type='category',
        object_id=category.id,
        label=category.name,
        text=f"{category.name} category {category.description} {item_names}",
        meta={'item_count': category.items.count()},
    )


def location_document(location):
    item_names = ', '.join(location.items.values_list('item_name', flat=True)[:25])
    return Document(
        doc_type='location',
        object_id=location.id,
        label=location.name,
        text=f"{location.name} location {location.description} {item_names}",
        meta={'item_count': location.items.count()},
    )


def build_corpus():
    """Build a bag-of-words document for every Item, Category, and Location."""
    docs = [item_document(i) for i in Item.objects.select_related('category', 'location').all()]
    docs += [category_document(c) for c in Category.objects.all()]
    docs += [location_document(l) for l in Location.objects.all()]
    return docs


def _idf(corpus):
    """Inverse-document-frequency for every term across the corpus."""
    n_docs = len(corpus) or 1
    doc_freq = Counter()
    for doc in corpus:
        doc_freq.update(doc.bow.keys())
    return {term: math.log((1 + n_docs) / (1 + df)) + 1 for term, df in doc_freq.items()}


def _tfidf_vector(bow, idf):
    return {term: count * idf.get(term, 0.0) for term, count in bow.items()}


def _cosine(vec_a, vec_b):
    common = set(vec_a) & set(vec_b)
    dot = sum(vec_a[t] * vec_b[t] for t in common)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)


# Loose keyword -> status code hints so "low stock" / "out of stock" / "discontinued"
# reliably surface the right items even when TF-IDF alone scores them low.
_STATUS_HINTS = [
    ({'discontinued'}, Item.STATUS_DISCONTINUED),
    ({'out'}, Item.STATUS_OUT_OF_STOCK),
    ({'low'}, Item.STATUS_LOW_STOCK),
]


def status_hint(query):
    """Loose keyword match, e.g. 'low stock' / 'out of stock' -> a status code, or None."""
    tokens = set(re.findall(r"[a-z]+", query.lower()))
    for trigger, status in _STATUS_HINTS:
        if trigger & tokens:
            return status
    return None


def search(query, corpus=None, top_k=20, doc_types=None, boost_status=True):
    """
    Rank corpus documents against a free-text query using TF-IDF + cosine similarity.
    Returns a list of (Document, score) tuples sorted by score descending.
    """
    corpus = corpus if corpus is not None else build_corpus()
    if doc_types:
        corpus = [d for d in corpus if d.doc_type in doc_types]

    query_tokens = tokenize(query)
    idf = _idf(corpus)
    scored = []

    if query_tokens:
        query_vec = _tfidf_vector(bag_of_words(query_tokens), idf)
        for doc in corpus:
            doc_vec = _tfidf_vector(doc.bow, idf)
            score = _cosine(query_vec, doc_vec)
            if score > 0:
                scored.append((doc, score))
        scored.sort(key=lambda pair: pair[1], reverse=True)

    if boost_status:
        hinted = status_hint(query)
        if hinted:
            seen_ids = {doc.object_id for doc, _ in scored if doc.doc_type == 'item'}
            for doc in corpus:
                if doc.doc_type == 'item' and doc.meta.get('status') == hinted and doc.object_id not in seen_ids:
                    scored.append((doc, 0.001))

    return scored[:top_k]


def retrieve_context_for_question(question, top_k=8):
    """RAG retrieval step: top matching Items for a natural-language question."""
    corpus = build_corpus()
    return search(question, corpus=corpus, top_k=top_k, doc_types={'item'})
