from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx

from vibecli.types import Message


@dataclass(slots=True)
class OpenAICompatibleClient:
    provider_name: str
    model: str
    api_key: str
    base_url: str
    max_tokens: int = 8192
    temperature: float = 0.7
    timeout: float = 120.0
    max_context_window: int = 128_000