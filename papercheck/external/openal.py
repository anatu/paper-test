"""OpenAlex API client — broad-coverage fallback for citation verification."""

from __future__ import annotations

import hashlib
import json
import logging

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.openalex.org"

# Polite pool: include mailto for higher rate limits
_USER_AGENT = "papercheck/0.1.0 (mailto:papercheck@example.com)"


class OpenAlexClient:
    """Synchronous OpenAlex API client with caching."""

    def __init__(self, cache: object | None = None, cache_ttl_hours: int = 720):
        self._cache = cache
        self._cache_ttl = cache_ttl_hours
        self._client = httpx.Client(
            headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
            timeout=30.0,
        )

    def search_by_title(self, title: str) -> dict | None:
        """Search OpenAlex for a paper by title. Returns best match or None."""
        cache_key = f"openalex:search:{_hash(title)}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached if cached != "__NONE__" else None

        try:
            response = self._client.get(
                f"{BASE_URL}/works",
                params={"filter": f"title.search:{title}", "per_page": 3},
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPStatusError, httpx.ConnectError):
            logger.warning("OpenAlex lookup failed for: %s", title[:80])
            return None

        results = data.get("results", [])
        if not results:
            self._cache_set(cache_key, "__NONE__")
            return None

        best = _best_match(results, title)
        if best:
            self._cache_set(cache_key, best)
        else:
            self._cache_set(cache_key, "__NONE__")
        return best

    def _cache_get(self, key: str):
        if self._cache is None:
            return None
        raw = self._cache.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    def _cache_set(self, key: str, value, ttl_hours: int | None = None) -> None:
        if self._cache is None:
            return
        self._cache.set(key, json.dumps(value).encode(), ttl_hours=ttl_hours or self._cache_ttl)

    def close(self) -> None:
        self._client.close()


def _normalize_work(work: dict) -> dict:
    """Extract key fields from an OpenAlex work."""
    authorships = work.get("authorships", [])
    authors = [a.get("author", {}).get("display_name", "") for a in authorships]

    return {
        "title": work.get("title", ""),
        "authors": authors,
        "year": work.get("publication_year"),
        "doi": (work.get("doi") or "").replace("https://doi.org/", ""),
        "venue": (work.get("primary_location") or {}).get("source", {}).get("display_name", "") if work.get("primary_location") else "",
        "openalex_id": work.get("id", ""),
        "cited_by_count": work.get("cited_by_count", 0),
    }


def _best_match(results: list[dict], query_title: str) -> dict | None:
    """Return the result whose title best matches the query."""
    query_lower = query_title.lower().strip().rstrip(".")
    for work in results:
        title = (work.get("title") or "").lower().strip().rstrip(".")
        if title == query_lower:
            return _normalize_work(work)
    # Fallback: first result if title has significant word overlap
    if results:
        first_title = (results[0].get("title") or "").lower()
        query_words = set(query_lower.split())
        first_words = set(first_title.split())
        if query_words and len(query_words & first_words) / len(query_words) > 0.8:
            return _normalize_work(results[0])
    return None


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]
