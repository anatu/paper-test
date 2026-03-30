"""Semantic Scholar API client with caching, rate limiting, and retry."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

BASE_URL = "https://api.semanticscholar.org/graph/v1"
RECOMMEND_URL = "https://api.semanticscholar.org/recommendations/v1/papers"

PAPER_FIELDS = "title,abstract,authors,year,citationCount,externalIds,venue"


@dataclass
class S2Paper:
    """Lightweight representation of a Semantic Scholar paper."""

    paper_id: str = ""
    title: str = ""
    abstract: str | None = None
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    citation_count: int | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    venue: str = ""

    @classmethod
    def from_api(cls, data: dict) -> S2Paper:
        """Parse a paper from S2 API response."""
        authors = [a.get("name", "") for a in (data.get("authors") or [])]
        ext = data.get("externalIds") or {}
        return cls(
            paper_id=data.get("paperId", ""),
            title=data.get("title", ""),
            abstract=data.get("abstract"),
            authors=authors,
            year=data.get("year"),
            citation_count=data.get("citationCount"),
            doi=ext.get("DOI"),
            arxiv_id=ext.get("ArXiv"),
            venue=data.get("venue", ""),
        )


class S2RateLimitError(Exception):
    """Raised on 429 responses."""


class S2ServerError(Exception):
    """Raised on 500/503 responses."""


class SemanticScholarClient:
    """Async-style client for the Semantic Scholar API.

    Despite the async interface of the pipeline, this uses synchronous httpx
    calls (matching the LLMClient pattern) with caching and retry.
    """

    def __init__(
        self,
        api_key: str | None = None,
        cache: object | None = None,
        cache_ttl_hours: int = 168,
    ):
        self._api_key = api_key
        self._cache = cache  # CacheStore instance
        self._cache_ttl = cache_ttl_hours
        headers = {"Accept": "application/json"}
        if api_key:
            headers["x-api-key"] = api_key
        self._client = httpx.Client(headers=headers, timeout=30.0)

    def search_paper(self, query: str, limit: int = 5) -> list[S2Paper]:
        """Search for papers by title/query string."""
        cache_key = f"s2:search:{_hash(query)}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return [S2Paper(**p) for p in cached]

        data = self._request(
            "GET",
            f"{BASE_URL}/paper/search",
            params={"query": query, "limit": limit, "fields": PAPER_FIELDS},
        )
        papers = [S2Paper.from_api(p) for p in (data.get("data") or [])]
        self._cache_set(cache_key, [_paper_dict(p) for p in papers], ttl_hours=24)
        return papers

    def get_paper(self, paper_id: str) -> S2Paper | None:
        """Get a paper by Semantic Scholar ID, DOI, or ArXiv ID."""
        cache_key = f"s2:paper:{paper_id}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return S2Paper(**cached)

        try:
            data = self._request(
                "GET",
                f"{BASE_URL}/paper/{paper_id}",
                params={"fields": PAPER_FIELDS},
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

        paper = S2Paper.from_api(data)
        self._cache_set(cache_key, _paper_dict(paper))
        return paper

    def get_paper_by_title(
        self, title: str, authors: list[str] | None = None, year: int | None = None
    ) -> S2Paper | None:
        """Search for a specific paper by title, optionally filtering by author/year."""
        results = self.search_paper(title, limit=5)
        if not results:
            return None

        title_lower = title.lower().strip()
        for paper in results:
            if _title_match(paper.title, title_lower):
                if year and paper.year and abs(paper.year - year) > 1:
                    continue
                if authors and not _author_overlap(paper.authors, authors):
                    continue
                return paper

        # Fallback: return first result if title is close enough
        if results and _fuzzy_title_match(results[0].title, title_lower):
            return results[0]
        return None

    def get_recommendations(self, paper_id: str, limit: int = 10) -> list[S2Paper]:
        """Get recommended related papers for a given paper."""
        cache_key = f"s2:recommend:{paper_id}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return [S2Paper(**p) for p in cached]

        try:
            data = self._request(
                "POST",
                RECOMMEND_URL,
                json_body={"positivePaperIds": [paper_id]},
                params={"limit": limit, "fields": PAPER_FIELDS},
            )
        except (httpx.HTTPStatusError, S2ServerError):
            logger.warning("S2 recommendations failed for %s", paper_id)
            return []

        papers = [S2Paper.from_api(p) for p in (data.get("recommendedPapers") or [])]
        self._cache_set(cache_key, [_paper_dict(p) for p in papers], ttl_hours=24)
        return papers

    @retry(
        retry=retry_if_exception_type((S2RateLimitError, S2ServerError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    def _request(
        self,
        method: str,
        url: str,
        params: dict | None = None,
        json_body: dict | None = None,
    ) -> dict:
        """Make an HTTP request with retry on transient errors."""
        response = self._client.request(method, url, params=params, json=json_body)
        if response.status_code == 429:
            raise S2RateLimitError("S2 rate limit hit")
        if response.status_code in (500, 503):
            raise S2ServerError(f"S2 server error: {response.status_code}")
        response.raise_for_status()
        return response.json()

    def _cache_get(self, key: str) -> list | dict | None:
        if self._cache is None:
            return None
        raw = self._cache.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    def _cache_set(self, key: str, value: list | dict, ttl_hours: int | None = None) -> None:
        if self._cache is None:
            return
        self._cache.set(key, json.dumps(value).encode(), ttl_hours=ttl_hours or self._cache_ttl)

    def close(self) -> None:
        self._client.close()


def _hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def _paper_dict(p: S2Paper) -> dict:
    return {
        "paper_id": p.paper_id,
        "title": p.title,
        "abstract": p.abstract,
        "authors": p.authors,
        "year": p.year,
        "citation_count": p.citation_count,
        "doi": p.doi,
        "arxiv_id": p.arxiv_id,
        "venue": p.venue,
    }


def _title_match(candidate: str, target: str) -> bool:
    """Check if titles are essentially the same (case-insensitive, stripped)."""
    return candidate.lower().strip().rstrip(".") == target.rstrip(".")


def _fuzzy_title_match(candidate: str, target: str) -> bool:
    """Check if titles overlap significantly (>80% word overlap)."""
    cand_words = set(candidate.lower().split())
    target_words = set(target.split())
    if not target_words:
        return False
    overlap = len(cand_words & target_words) / len(target_words)
    return overlap > 0.8


def _author_overlap(paper_authors: list[str], query_authors: list[str]) -> bool:
    """Check if at least one query author last name matches."""
    paper_lastnames = {_extract_lastname(a) for a in paper_authors if a}
    query_lastnames = {_extract_lastname(a) for a in query_authors if a}
    paper_lastnames.discard("")
    query_lastnames.discard("")
    return bool(paper_lastnames & query_lastnames)


def _extract_lastname(name: str) -> str:
    """Extract the last name from various name formats.

    Handles: "First Last", "Last, First", "Last, F."
    """
    name = name.strip().rstrip(".")
    if "," in name:
        # "Last, First" format
        return name.split(",")[0].strip().lower()
    parts = name.split()
    if parts:
        return parts[-1].strip().lower()
    return ""
