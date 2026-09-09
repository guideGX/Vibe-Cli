from __future__ import annotations

import html
import ipaddress
import re
import socket
from urllib.parse import urlparse

import httpx


class NetworkPolicyError(ValueError):
    pass


async def fetch_url(url: str, max_length: int = 10_000, timeout: float = 15.0) -> str:
    _validate_public_url(url)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.get(url, headers={"user-agent": "VibeCLI-Python/0.1.0"})
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        text = response.text
        if "html" in content_type:
            text = extract_text_from_html(text)
        if len(text) > max_length:
            text = text[:max_length] + "\n... [truncated]"
        return text or "(empty page)"


def extract_text_from_html(raw_html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", raw_html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _validate_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise NetworkPolicyError("only http/https URLs are allowed")
    if not parsed.hostname: