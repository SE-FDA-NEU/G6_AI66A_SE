"""Gemini retrieval embeddings, called only by explicit semantic searches.

REST contract: https://ai.google.dev/api/embeddings
Vectors are validated/normalized before persistence, and never cross owners.
"""
import httpx

from app.core.config import settings
from app.services.search_index import normalized_vector


class EmbeddingUnavailable(Exception):
    pass


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
                             'embedContentConfig': {'taskType': task, 'outputDimensionality': self.dimensions}}
                            for text in batch]})
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
