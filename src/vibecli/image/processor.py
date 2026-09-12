from __future__ import annotations

import base64
import io
import mimetypes
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

from PIL import Image

IMAGE_PATTERN = re.compile(r"@image:([^\s]+)")


def parse_image_references(message: str, cwd: str) -> str | list[dict]:
    matches = list(IMAGE_PATTERN.finditer(message))
    if not matches:
        return message

    parts: list[dict] = []
    cursor = 0
    for match in matches:
        before = message[cursor : match.start()]
        if before:
            parts.append({"type": "text", "text": before})