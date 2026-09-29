from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from vibecli import __version__
from vibecli.agent import QueryEngine
from vibecli.bootstrap import build_tool_registry