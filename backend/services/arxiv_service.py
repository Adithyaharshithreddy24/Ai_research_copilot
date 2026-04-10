import arxiv
import os
import time
from typing import Dict, List, Tuple

# Simple in-memory controls to reduce upstream rate limiting.
QUERY_TTL_SECONDS = 15 * 60
CHAT_COOLDOWN_SECONDS = 30
REQUEST_GAP_SECONDS = 2.0
MAX_RETRIES = 3
ARXIV_429_COOLDOWN_SECONDS = int(os.getenv("ARXIV_429_COOLDOWN_SECONDS", "300"))

_query_cache: Dict[Tuple[str, int], Tuple[float, List[dict]]] = {}
_chat_state: Dict[str, Dict[str, object]] = {}
_arxiv_blocked_until: float = 0.0


def _normalize_query(query: str) -> str:
    return " ".join(query.lower().strip().split())


def _is_cache_valid(ts: float) -> bool:
    return (time.time() - ts) <= QUERY_TTL_SECONDS


def _fallback_from_chat(chat_id: str | None):
    if not chat_id:
        return None

    state = _chat_state.get(chat_id, {})
    last_success = state.get("last_success")

    if isinstance(last_success, list) and last_success:
        return last_success

    return None


def fetch_papers(query: str, max_results: int, chat_id: str | None = None):
    global _arxiv_blocked_until
    normalized_query = _normalize_query(query)
    cache_key = (normalized_query, max_results)
    now = time.time()

    cached = _query_cache.get(cache_key)
    if cached and _is_cache_valid(cached[0]):
        return cached[1]

    # Circuit-breaker: after HTTP 429, avoid hammering arXiv for a cooldown window.
    if now < _arxiv_blocked_until:
        fallback = _fallback_from_chat(chat_id)
        if fallback:
            return fallback
        return [
            {
                "title": "arXiv temporarily unavailable",
                "summary": "arXiv is rate-limited right now. Using fallback discovery during cooldown.",
                "authors": [],
                "pdf_url": "",
            }
        ]

    if chat_id:
        chat = _chat_state.setdefault(chat_id, {"last_call": 0.0, "last_success": []})
        elapsed = now - float(chat.get("last_call", 0.0))

        if elapsed < CHAT_COOLDOWN_SECONDS:
            fallback = _fallback_from_chat(chat_id)
            if fallback:
                return fallback

        chat["last_call"] = now

    backoff = 2.0

    for attempt in range(MAX_RETRIES):
        try:
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.Relevance,
            )
            client = arxiv.Client(
                page_size=max_results,
                delay_seconds=REQUEST_GAP_SECONDS,
                num_retries=2,
            )

            papers = []

            for result in client.results(search):
                papers.append(
                    {
                        "title": result.title,
                        "summary": result.summary,
                        "authors": [a.name for a in result.authors],
                        "pdf_url": result.pdf_url,
                    }
                )

            _query_cache[cache_key] = (time.time(), papers)
            if chat_id:
                _chat_state.setdefault(chat_id, {})["last_success"] = papers
            return papers

        except Exception as e:
            print(f"ARXIV ERROR (attempt {attempt + 1}/{MAX_RETRIES}):", e)
            error_text = str(e)

            if "HTTP 429" in error_text:
                _arxiv_blocked_until = time.time() + ARXIV_429_COOLDOWN_SECONDS
                break

            if attempt < MAX_RETRIES - 1:
                time.sleep(backoff)
                backoff *= 2

    fallback = _fallback_from_chat(chat_id)
    if fallback:
        return fallback

    return [
        {
            "title": "arXiv temporarily unavailable",
            "summary": "Rate limit hit. Showing no fresh results right now. Please try again shortly.",
            "authors": [],
            "pdf_url": "",
        }
    ]
