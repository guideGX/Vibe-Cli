from __future__ import annotations

import html
import re
from dataclasses import dataclass
from urllib.parse import parse_qs, quote, unquote, urlparse

import httpx


@dataclass(slots=True)
class SearchResult:
    title: str
    url: str
    snippet: str


async def search_web(query: str, max_results: int = 5, timeout: float = 15.0) -> list[SearchResult]:
    url = f"https://duckduckgo.com/html/?q={quote(query)}"
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.get(url, headers={"user-agent": "VibeCLI-Python/0.1.0"})
        response.raise_for_status()
    return _parse_duckduckgo(response.text)[:max_results]


def _parse_duckduckgo(raw_html: str) -> list[SearchResult]:
    results: list[SearchResult] = []
    pattern = re.compile(
        r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>([\s\S]*?)</a>'
        r"[\s\S]*?"