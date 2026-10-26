from __future__ import annotations

import asyncio
from pathlib import Path

from vibecli.config import VibeCliConfig
from vibecli.textio import decode_bytes, decode_chain, is_utf8, read_text_file
from vibecli.tools.base import ToolContext
from vibecli.tools.builtins import grep, read_file, write_file


def make_context(workspace: Path) -> ToolContext:
    config = VibeCliConfig()
    config.llm.api_key = "test-key"
    return ToolContext(cwd=str(workspace), config=config)


def test_reads_gbk_file_without_mojibake(tmp_path: Path) -> None:
    path = tmp_path / "legacy.py"
    path.write_bytes("# 这是原有的中文注释\n".encode("gbk"))
    text, encoding = read_text_file(path)
    assert "这是原有的中文注释" in text
    assert not is_utf8(encoding)


def test_reads_utf8_file_as_utf8(tmp_path: Path) -> None:
    path = tmp_path / "modern.py"
    path.write_text("# 中文注释\n", encoding="utf-8")
    text, encoding = read_text_file(path)
    assert "中文注释" in text
    assert is_utf8(encoding)


def test_decode_chain_has_no_duplicate_entries() -> None:
    chain = decode_chain()
    assert chain[0] == "utf-8"
    assert len({item.lower() for item in chain}) == len(chain)


def test_mixed_stream_keeps_both_encodings() -> None:
    """一条命令里 Git Bash 写 UTF-8、cmd 写 GBK，两段都要能读。"""
    raw = "中文\n".encode() + b"Microsoft Windows [\xb0\xe6\xb1\xbe 10.0]\r\n"
    text, _ = decode_bytes(raw)
    assert "中文" in text
    assert "版本" in text
    assert "\ufffd" not in text


def test_decode_bytes_empty() -> None:
    assert decode_bytes(b"") == ("", "utf-8")


def test_read_file_annotates_non_utf8_source(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "legacy.py").write_bytes("# 中文\n".encode("gbk"))
    result = asyncio.run(read_file({"path": "legacy.py"}, make_context(workspace)))
    assert "[note]" in result.content
    assert "中文" in result.content


def test_read_file_has_no_note_for_utf8_source(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "modern.py").write_text("# 中文\n", encoding="utf-8")
    result = asyncio.run(read_file({"path": "modern.py"}, make_context(workspace)))
    assert "[note]" not in result.content
    assert "中文" in result.content


def test_grep_finds_cjk_inside_gbk_file(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "legacy.py").write_bytes("SECRET = '密钥'\n".encode("gbk"))
    result = asyncio.run(grep({"pattern": "密钥", "path": "."}, make_context(workspace)))
    assert "密钥" in result.content


def test_write_file_keeps_original_encoding(tmp_path: Path) -> None:
    """写回保持原编码，否则 GBK 文件会变成「内容是 UTF-8、声明是 GBK」。"""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    target = workspace / "legacy.py"
    target.write_bytes("# -*- coding: gbk -*-\n# 中文\n".encode("gbk"))
    result = asyncio.run(
        write_file(
            {"path": "legacy.py", "content": "# -*- coding: gbk -*-\n# 中文\n"},
            make_context(workspace),
        )
    )
    assert "kept cp936 encoding" in result.content
    assert "Diagnostics" not in result.content
    assert target.read_bytes().decode("gbk") == "# -*- coding: gbk -*-\n# 中文\n"


def test_write_file_falls_back_to_utf8_for_unrepresentable_text(tmp_path: Path) -> None:
    """GBK 表示不了 emoji，此时退回 UTF-8 并同步改掉 coding 声明。"""
    workspace = tmp_path / "ws"
    workspace.mkdir()
    target = workspace / "legacy.py"
    # 必须含非 ASCII 中文，否则纯 ASCII 字节同时是合法 UTF-8，探测不出 GBK
    target.write_bytes("# -*- coding: gbk -*-\n# 中文\nx = 1\n".encode("gbk"))
    result = asyncio.run(
        write_file(
            {"path": "legacy.py", "content": "# -*- coding: gbk -*-\n# 中文\nx = '🚀'\n"},
            make_context(workspace),
        )
    )
    assert "rewritten as UTF-8" in result.content
    written = target.read_text(encoding="utf-8")
    assert "🚀" in written
    assert "coding: utf-8" in written


def test_write_file_starts_new_files_as_utf8(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    result = asyncio.run(
        write_file({"path": "fresh.py", "content": "# 中文\n"}, make_context(workspace))
    )
    assert "[note]" not in result.content
    assert (workspace / "fresh.py").read_text(encoding="utf-8") == "# 中文\n"
