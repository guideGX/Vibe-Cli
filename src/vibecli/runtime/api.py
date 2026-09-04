from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import threading
import time
from dataclasses import asdict
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from vibecli.agent import QueryEngine
from vibecli.bootstrap import build_tool_registry
from vibecli.config import VibeCliConfig
from vibecli.llm import create_llm_client
from vibecli.runtime.tasks import DurableTaskManager


class RuntimeApiServer:
    def __init__(
        self,