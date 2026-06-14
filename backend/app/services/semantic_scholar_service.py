import logging
import random
import time
from typing import Any, Optional

import requests

from ..core.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://api.semanticscholar.org/graph/v1"

FIELDS_SEARCH = ",".join([
    "title",
    "abstract",
    "year",
    "authors",
    "tldr",
    "externalIds",
    "citationCount",
    "url",
])

FIELDS_DETAIL = ",".join([
    "title",
    "abstract",
    "year",
    "authors",
    "tldr",
    "externalIds",
    "citationCount",
    "url",
    "references.paperId",
    "references.title",
    "references.year",
    "references.authors",
    "citations.paperId",
    "citations.title",
    "citations.year",
    "citations.authors",
])


class SemanticScholarService:
    def __init__(self):
        self.headers = {"x-api-key": settings.S2_API_KEY} if settings.S2_API_KEY else {}
        # enforce a minimum interval between requests to Semantic Scholar (seconds)
        self.min_request_interval = 1.0
        self._last_request_time = 0.0

    def _get(self, url: str, params: dict[str, Any], max_retries: int = 6) -> dict[str, Any]:
        for attempt in range(max_retries):
            # enforce global minimum delay between requests
            try:
                elapsed = time.time() - self._last_request_time
                if elapsed < self.min_request_interval:
                    time.sleep(self.min_request_interval - elapsed)
            except Exception:
                pass
            try:
                response = requests.get(url, params=params, headers=self.headers, timeout=15)

                if response.status_code == 429:
                    wait = (2 ** attempt) + random.uniform(0, 1)
                    logger.warning("Semantic Scholar rate limited, retrying in %.1fs", wait)
                    time.sleep(wait)
                    continue

                response.raise_for_status()
                # record successful request time
                try:
                    self._last_request_time = time.time()
                except Exception:
                    pass
                return response.json()
            except requests.exceptions.Timeout:
                logger.warning("Semantic Scholar timeout on attempt %s/%s", attempt + 1, max_retries)
                time.sleep(2 ** attempt)

        raise RuntimeError(f"Max retries exceeded for {url}")

    @staticmethod
    def _normalize_text_tldr(value: Any) -> str:
        if isinstance(value, dict):
            return str(value.get("text", "") or "").strip()
        if value is None:
            return ""
        return str(value).strip()

    @staticmethod
    def _normalize_authors(value: Any) -> list[str]:
        authors = []
        for author in value or []:
            if isinstance(author, dict):
                name = author.get("name")
            else:
                name = str(author)
            if name:
                authors.append(str(name).strip())
        return authors

    @staticmethod
    def _normalize_external_ids(value: Any) -> dict[str, Any]:
        return value or {}

    def search_by_title(self, title: str, limit: int = 3) -> list[dict[str, Any]]:
        data = self._get(
            f"{BASE_URL}/paper/search",
            {"query": title, "fields": FIELDS_DETAIL, "limit": limit},
        )
        return data.get("data", []) or []

    def get_paper_detail(self, paper_id: str) -> dict[str, Any]:
        return self._get(f"{BASE_URL}/paper/{paper_id}", {"fields": FIELDS_DETAIL})

    def resolve_paper(self, title: str) -> dict[str, Any]:
        candidates = self.search_by_title(title, limit=3)
        if not candidates:
            return {"search_result": None, "detail": None, "record": self._empty_record(title)}

        search_result = candidates[0]
        paper_id = search_result.get("paperId") or search_result.get("paper_id")
        
        record = self._build_record(search_result, None, title)
        return {"search_result": search_result, "detail": search_result, "record": record, "paper_id": paper_id, "source": search_result}

    def resolve_papers(self, titles: list[str], limit_each: int = 3, min_delay: float = 1.0) -> list[dict[str, Any]]:
        """
        Batch-resolve a list of titles. Respects a minimum delay between Semantic Scholar requests (default 1.0s).
        Returns a list of the same shape as resolve_paper (dict per title).
        """
        results = []
        last_call = 0.0
        for title in titles:
            # enforce minimum delay between calls to avoid rate limiting
            elapsed = time.time() - last_call
            if elapsed < min_delay:
                time.sleep(min_delay - elapsed)
            try:
                res = self.resolve_paper(title)
            except Exception as e:
                logger.warning("Batch resolve failed for title '%s': %s", title, e)
                res = {"search_result": None, "detail": None, "record": self._empty_record(title), "paper_id": None, "source": None}
            results.append(res)
            last_call = time.time()
        return results

    def _empty_record(self, title: str) -> dict[str, Any]:
        return {
            "ss_paper_id": None,
            "title": title,
            "year": None,
            "authors": [],
            "citation_count": None,
            "doi": None,
            "arxiv_id": None,
            "tldr": "",
            "abstract": "",
            "external_ids": {},
            "references": [],
            "citations": [],
            "url": None,
        }

    def _build_record(self, search_result: dict[str, Any], detail: Optional[dict[str, Any]], fallback_title: str) -> dict[str, Any]:
        source = detail or search_result or {}
        external_ids = self._normalize_external_ids(source.get("externalIds") or {})
        abstract = (source.get("abstract") or search_result.get("abstract") or "").strip()
        tldr = self._normalize_text_tldr(source.get("tldr") or search_result.get("tldr"))
        record = {
            "ss_paper_id": source.get("paperId") or search_result.get("paperId"),
            "title": source.get("title") or search_result.get("title") or fallback_title,
            "year": source.get("year") or search_result.get("year"),
            "authors": self._normalize_authors(source.get("authors") or search_result.get("authors")),
            "citation_count": source.get("citationCount") or search_result.get("citationCount"),
            "doi": external_ids.get("DOI"),
            "arxiv_id": external_ids.get("ArXiv"),
            "tldr": tldr,
            "abstract": abstract,
            "external_ids": external_ids,
            "references": source.get("references") or [],
            "citations": source.get("citations") or [],
            "url": source.get("url") or search_result.get("url"),
        }
        return record


semantic_scholar_service = SemanticScholarService()