"""PapersWithCode API client — repository detection for academic papers."""

from __future__ import annotations

import hashlib
import json
import logging

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://paperswithcode.com/api/v1"


class PapersWithCodeClient:
    """Synchronous PapersWithCode API client with caching."""

    def __init__(self, cache: object | None = None, cache_ttl_hours: int = 168):
        self._cache = cache
        self._cache_ttl = cache_ttl_hours
        self._client = httpx.Client(
            headers={"Accept": "application/json"},
            timeout=30.0,
        )

    def search_repos_by_title(self, title: str) -> list[dict]:
        """Search for code repositories associated with a paper title.

        Returns a list of dicts with keys: url, framework, stars, description.
        """
        cache_key = f"pwc:search:{_hash(title)}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached if cached != "__NONE__" else []

        try:
            # Search for the paper first
            response = self._client.get(
                f"{BASE_URL}/papers/",
                params={"q": title, "items_per_page": 3},
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPStatusError, httpx.ConnectError) as e:
            logger.warning("PapersWithCode search failed: %s", e)
            return []

        results = data.get("results", [])
        if not results:
            self._cache_set(cache_key, "__NONE__")
            return []

        # Find the best matching paper and get its repos
        best_paper = _best_match(results, title)
        if not best_paper:
            self._cache_set(cache_key, "__NONE__")
            return []

        paper_id = best_paper.get("id", "")
        if not paper_id:
            self._cache_set(cache_key, "__NONE__")
            return []

        repos = self._get_paper_repos(paper_id)
        self._cache_set(cache_key, repos if repos else "__NONE__")
        return repos

    def _get_paper_repos(self, paper_id: str) -> list[dict]:
        """Get repositories for a specific paper ID."""
        try:
            response = self._client.get(
                f"{BASE_URL}/papers/{paper_id}/repositories/",
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPStatusError, httpx.ConnectError) as e:
            logger.warning("PapersWithCode repo lookup failed: %s", e)
            return []

        repos = []
        for item in data.get("results", []):
            repos.append({
                "url": item.get("url", ""),
                "framework": item.get("framework", ""),
                "stars": item.get("stars", 0),
                "description": item.get("description", ""),
                "is_official": item.get("is_official", False),
            })
        return repos

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


def _best_match(results: list[dict], query_title: str) -> dict | None:
    """Return the result whose title best matches the query."""
    query_lower = query_title.lower().strip().rstrip(".")
    for item in results:
        title = (item.get("title") or "").lower().strip().rstrip(".")
        if title == query_lower:
            return item
    # Fallback: first result with >80% word overlap
    if results:
        first_title = (results[0].get("title") or "").lower()
        query_words = set(query_lower.split())
        first_words = set(first_title.split())
        if query_words and len(query_words & first_words) / len(query_words) > 0.7:
            return results[0]
    return None


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]
