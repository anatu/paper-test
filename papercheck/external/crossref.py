"""CrossRef API client — DOI resolution and bibliographic lookup (fallback)."""

from __future__ import annotations

import hashlib
import json
import logging

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

BASE_URL = "https://api.crossref.org/works"

# Polite pool: include mailto in User-Agent for higher rate limits
_USER_AGENT = "papercheck/0.1.0 (mailto:papercheck@example.com)"


class CrossRefClient:
    """Synchronous CrossRef API client with caching."""

    def __init__(self, cache: object | None = None, cache_ttl_hours: int = 720):
        self._cache = cache
        self._cache_ttl = cache_ttl_hours
        self._client = httpx.Client(
            headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
            timeout=30.0,
        )

    def lookup_by_title(self, title: str, author: str | None = None) -> dict | None:
        """Search CrossRef by bibliographic query. Returns best match or None."""
        query = title
        if author:
            query = f"{title} {author}"

        cache_key = f"crossref:search:{_hash(query)}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached if cached != "__NONE__" else None

        try:
            data = self._request(params={"query.bibliographic": query, "rows": 3})
        except (httpx.HTTPStatusError, httpx.ConnectError):
            logger.warning("CrossRef lookup failed for: %s", title[:80])
            return None

        items = data.get("message", {}).get("items", [])
        if not items:
            self._cache_set(cache_key, "__NONE__")
            return None

        best = _best_match(items, title)
        if best:
            self._cache_set(cache_key, best)
        else:
            self._cache_set(cache_key, "__NONE__")
        return best

    def lookup_by_doi(self, doi: str) -> dict | None:
        """Resolve a DOI to bibliographic metadata."""
        cache_key = f"crossref:doi:{doi}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached if cached != "__NONE__" else None

        try:
            response = self._client.get(f"{BASE_URL}/{doi}")
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPStatusError, httpx.ConnectError):
            self._cache_set(cache_key, "__NONE__")
            return None

        item = data.get("message", {})
        result = _normalize_item(item)
        self._cache_set(cache_key, result)
        return result

    @retry(
        retry=retry_if_exception_type(httpx.HTTPStatusError),
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5),
    )
    def _request(self, params: dict) -> dict:
        response = self._client.get(BASE_URL, params=params)
        response.raise_for_status()
        return response.json()

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


def _normalize_item(item: dict) -> dict:
    """Extract key fields from a CrossRef work item."""
    titles = item.get("title", [])
    authors_raw = item.get("author", [])
    authors = []
    for a in authors_raw:
        given = a.get("given", "")
        family = a.get("family", "")
        authors.append(f"{given} {family}".strip())

    published = item.get("published-print") or item.get("published-online") or {}
    date_parts = published.get("date-parts", [[None]])
    year = date_parts[0][0] if date_parts and date_parts[0] else None

    return {
        "title": titles[0] if titles else "",
        "authors": authors,
        "year": year,
        "doi": item.get("DOI", ""),
        "venue": (item.get("container-title") or [""])[0],
        "type": item.get("type", ""),
    }


def _best_match(items: list[dict], query_title: str) -> dict | None:
    """Return the item whose title best matches the query, or None."""
    query_lower = query_title.lower().strip().rstrip(".")
    for item in items:
        titles = item.get("title", [])
        for t in titles:
            if t.lower().strip().rstrip(".") == query_lower:
                return _normalize_item(item)
    # Fallback: return first item if score is high enough
    if items and items[0].get("score", 0) > 50:
        return _normalize_item(items[0])
    return None


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]
