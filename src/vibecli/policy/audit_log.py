from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SENSITIVE_KEYS = ("token", "key", "password", "secret", "authorization", "bearer")


class AuditLog:
    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()

    def record(
        self,