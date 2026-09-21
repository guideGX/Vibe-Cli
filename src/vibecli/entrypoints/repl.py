from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from vibecli import __version__
from vibecli.agent import Agent, AgentOrchestrator, PlanExecuteAgent
from vibecli.bootstrap import build_tool_registry
from vibecli.config import VibeCliConfig, config_to_public_dict
from vibecli.llm import create_llm_client
from vibecli.memory import MemoryManager
from vibecli.policy import AuditLog
from vibecli.prompt import PromptAssembler
from vibecli.rag import CodeIndex
from vibecli.render import RichRenderer
from vibecli.runtime import DurableTaskManager
from vibecli.skill import SkillRegistry
from vibecli.snapshot import SnapshotService
from vibecli.tools import ToolRegistry

SLASH_COMMANDS = [
    "/help",