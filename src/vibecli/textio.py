"""文本编码探测。

CLI 里所有「拿到外部字节」的地方都走这里，而不是各自假设 UTF-8。

为什么需要这个模块：Windows 上同一个进程可能同时面对三种编码 ——
Git Bash 写的 UTF-8、cmd 内建命令写的 GBK（系统 ANSI 代码页）、用户遗留
项目里存的 GBK 源文件。任何一个调用点单独写 ``decode("utf-8")`` 都会在
其中两种上出错，而 ``errors="replace"`` 又让出错这件事变得无声无息。
"""

from __future__ import annotations

import locale
from functools import lru_cache
from pathlib import Path

_UTF8_ALIASES = {"utf-8", "utf8", "ascii", "us-ascii", "utf-8-sig"}


def _ansi_encoding() -> str | None:
    """系统 ANSI 代码页（简体中文 Windows 上是 cp936）。

    刻意不用 ``locale.getpreferredencoding()``：在 ``PYTHONUTF8=1``（uv 默认
    开启）或 ``-X utf8`` 下它返回 "utf-8"，把真正要兜的代码页盖掉，导致
    「用 locale 兜底 GBK」的写法实际是空转。``locale.getencoding()`` 不受
    UTF-8 模式影响，Python 3.11+ 才有。
    """
    getter = getattr(locale, "getencoding", None)
    try:
        return getter() if getter else locale.getpreferredencoding(False)
    except (LookupError, ValueError):  # pragma: no cover - 平台兜底
        return None


@lru_cache(maxsize=1)
def decode_chain() -> tuple[str, ...]:
    """编码尝试顺序：UTF-8 优先，其次系统 ANSI 代码页，再兜常见中文编码。

    cp936 / big5 无条件入链，**不限 Windows**：GBK 文件完全可能出现在
    Linux 上（从 Windows 拷来的代码库、跨平台共享仓库）。把它们限定在
    Windows 等于重复「GBK 只在 Windows 出现」这个假设 —— 正是本项目要修
    的那类错。CI 的 ubuntu runner 第一次跑就抓出了这个。
    """
    chain: list[str] = ["utf-8"]
    fallbacks = [_ansi_encoding(), "cp936", "big5"]
    for encoding in fallbacks:
        if encoding and encoding.lower() not in {item.lower() for item in chain}:
            chain.append(encoding)
    return tuple(chain)


def is_utf8(encoding: str) -> bool:
    return encoding.lower() in _UTF8_ALIASES


def decode_line(line: bytes) -> tuple[str, str]:
    """解一行，返回 (文本, 实际使用的编码)。"""
    for encoding in decode_chain():
        try:
            return line.decode(encoding), encoding
        except (UnicodeDecodeError, LookupError):
            continue
    return line.decode("utf-8", errors="replace"), "utf-8"


def decode_bytes(raw: bytes) -> tuple[str, str]:
    """解码字节流，返回 (文本, 主要编码)。

    逐行判断而不是整段猜一个编码：同一条命令的输出里可能既有 Git Bash 写出
    的 UTF-8（``echo 中文``），又有 cmd 内建命令写出的 GBK（``cmd /c ver``），
    整段按 UTF-8 解会连带把后面那段毁成替换字符。GBK 与 UTF-8 的多字节序列
    都不含 ``\\n``，所以按行独立判断是安全的。
    """
    if not raw:
        return "", "utf-8"
    decoded: list[str] = []
    used = "utf-8"
    for line in raw.split(b"\n"):
        text, encoding = decode_line(line)
        decoded.append(text)
        if is_utf8(used) and not is_utf8(encoding):
            used = encoding
    return "\n".join(decoded), used


def read_text_file(path: Path) -> tuple[str, str]:
    """读文件，返回 (文本, 使用的编码)。"""
    return decode_bytes(path.read_bytes())


def read_text_quietly(path: Path) -> str:
    """只需要内容、不关心编码时的薄封装。"""
    return read_text_file(path)[0]
