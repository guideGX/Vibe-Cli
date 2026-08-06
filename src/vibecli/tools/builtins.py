from __future__ import annotations

import asyncio
import glob as glob_module
import os
import re
from pathlib import Path
from typing import Any

from vibecli.lsp import diagnose_file
from vibecli.memory import MemoryManager
from vibecli.policy import CommandGuard, PathGuard
from vibecli.rag import CodeIndex
from vibecli.skill import SkillRegistry
from vibecli.snapshot import SnapshotService
from vibecli.tools.base import Tool, ToolContext, ToolResult, object_schema
from vibecli.web import fetch_url, search_web


def get_builtin_tools() -> list[Tool]:
    tools = [
        Tool(
            name="read_file",
            description="Read a text file from the current workspace.",
            parameters=object_schema(
                {