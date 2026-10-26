from __future__ import annotations

import base64
from pathlib import Path

import pytest
from PIL import Image

from vibecli.image import parse_image_references


def make_png(path: Path, *, mode: str = "RGB", size: tuple[int, int] = (64, 32)) -> Path:
    image = Image.new(mode, size, (255, 0, 0, 0) if mode == "RGBA" else (255, 0, 0))
    image.save(path)
    return path


def test_message_without_references_is_untouched(workspace: Path) -> None:
    message = "summarize src/vibecli/agent/agent.py"

    assert parse_image_references(message, str(workspace)) == message


def test_local_image_is_inlined_as_data_url(workspace: Path) -> None:
    make_png(workspace / "shot.png")

    parts = parse_image_references("describe this @image:./shot.png please", str(workspace))

    assert isinstance(parts, list)
    assert parts[0] == {"type": "text", "text": "describe this "}
    assert parts[1]["type"] == "image_url"
    url = parts[1]["image_url"]["url"]
    assert url.startswith("data:image/")
    assert base64.b64decode(url.split(",", 1)[1])[:3] == b"\xff\xd8\xff"  # JPEG payload
    assert parts[1]["metadata"]["width"] == 64
    assert parts[1]["metadata"]["height"] == 32
    assert parts[2] == {"type": "text", "text": " please"}


def test_absolute_path_and_file_scheme_are_supported(workspace: Path) -> None:
    path = make_png(workspace / "abs.png")

    parts = parse_image_references(f"@image:{path}", str(workspace))

    assert isinstance(parts, list)
    assert parts[0]["type"] == "image_url"


def test_remote_image_is_passed_through(workspace: Path) -> None:
    parts = parse_image_references("@image:https://example.com/a.png", str(workspace))

    assert parts[0]["image_url"]["url"] == "https://example.com/a.png"


def test_transparent_png_is_flattened_onto_white(workspace: Path) -> None:
    make_png(workspace / "alpha.png", mode="RGBA")

    parts = parse_image_references("@image:alpha.png", str(workspace))
    payload = base64.b64decode(parts[0]["image_url"]["url"].split(",", 1)[1])
    decoded = Image.open(__import__("io").BytesIO(payload))

    assert decoded.mode == "RGB"
    assert decoded.getpixel((0, 0))[0] > 200  # white background, not transparent


def test_image_outside_workspace_is_rejected(workspace: Path) -> None:
    outside = workspace.parent / "secret.png"
    make_png(outside)

    with pytest.raises(ValueError):
        parse_image_references("@image:../secret.png", str(workspace))


def test_missing_image_raises(workspace: Path) -> None:
    with pytest.raises(FileNotFoundError):
        parse_image_references("@image:nope.png", str(workspace))


def test_large_image_is_downscaled(workspace: Path) -> None:
    make_png(workspace / "big.png", size=(4000, 2000))

    parts = parse_image_references("@image:big.png", str(workspace))

    assert parts[0]["metadata"]["width"] <= 1568
    assert parts[0]["metadata"]["height"] <= 1568
