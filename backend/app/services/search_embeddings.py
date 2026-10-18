"""Gemini retrieval embeddings, called only by explicit semantic searches.

REST contract: https://ai.google.dev/api/embeddings
Vectors are validated/normalized before persistence, and never cross owners.
"""
import math

import httpx

from app.core.config import settings
from app.services.search_index import normalized_vector


class EmbeddingUnavailable(Exception):
    def __init__(self, message='Semantic search is temporarily unavailable.', *, code='embedding_unavailable', retry_after=None):
        super().__init__(message)
        self.code = code
        self.retry_after = retry_after


class GeminiSearchEmbedder:
    def __init__(self):
        self.model = settings.SEARCH_EMBEDDING_MODEL
        self.dimensions = settings.SEARCH_EMBEDDING_DIMENSIONS
        self.model_key = f'{self.model}:{self.dimensions}'

    def embed(self, texts, *, task):
        key = settings.GEMINI_API_KEY.get_secret_value().strip()
        if not key:
            raise EmbeddingUnavailable('Semantic search is not configured.')
        vectors = []
        try:
            with httpx.Client(timeout=settings.SEARCH_EMBEDDING_TIMEOUT_SECONDS) as client:
                for start in range(0, len(texts), 50):
                    batch = texts[start:start + 50]
                    response = client.post(
                        f'https://generativelanguage.googleapis.com/v1beta/models/{self.model}:batchEmbedContents',
                        headers={'x-goog-api-key': key}, json={'requests': [
                            {'model': f'models/{self.model}', 'content': {'parts': [{'text': text}]},
                             # batchEmbedContents currently honors these fields on each
                             # EmbedContentRequest; nesting them can silently return 3072 dimensions.
                             'taskType': task, 'outputDimensionality': self.dimensions}
                            for text in batch]})
                    if response.status_code == 429:
                        # Use only structured retry metadata; never expose provider messages or keys.
                        retry_after = 60
                        try:
                            details = response.json().get('error', {}).get('details', [])
                            for detail in details:
                                if detail.get('@type', '').endswith('RetryInfo'):
                                    delay = float(detail['retryDelay'].removesuffix('s'))
                                    if math.isfinite(delay):
                                        retry_after = max(1, min(3600, math.ceil(delay)))
                        except (KeyError, TypeError, ValueError, AttributeError):
                            pass
                        raise EmbeddingUnavailable('Embedding quota exceeded.', code='embedding_rate_limited', retry_after=retry_after)
                    response.raise_for_status()
                    values = response.json()['embeddings']
                    if len(values) != len(batch):
                        raise ValueError('Invalid embedding count.')
                    for value in values:
                        vector = normalized_vector(value['values'])
                        if len(vector) != self.dimensions:
                            raise ValueError('Invalid embedding dimensions.')
                        vectors.append(vector)
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            raise EmbeddingUnavailable('Semantic search is temporarily unavailable.') from None
        return vectors
