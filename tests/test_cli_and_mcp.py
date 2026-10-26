from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from vibecli import __version__
from vibecli.entrypoints.cli import app
from vibecli.mcp import load_mcp_server_specs, write_chrome_devtools_config
from vibecli.sdk import create_default_engine

runner = CliRunner()


def test_version_flag_prints_package_version() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert __version__ in result.output


def test_help_lists_subcommands() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in ("doctor", "serve", "mcp"):
        assert command in result.output


def test_doctor_reports_json(workspace: Path) -> None:
    result = runner.invoke(app, ["doctor", "--cwd", str(workspace)])

    assert result.exit_code == 0
    report = json.loads(result.output)
    assert report["cwd"] == str(workspace.resolve())
    assert report["provider"] == "deepseek"
    assert {"python", "uv", "node", "npx", "rg", "api_key", "model"} <= set(report)


def test_mcp_list_without_config(workspace: Path) -> None:
    result = runner.invoke(app, ["mcp", "list", "--cwd", str(workspace)])

    assert result.exit_code == 0
    assert "No MCP servers configured." in result.output


def test_init_chrome_writes_project_config(workspace: Path) -> None:
    result = runner.invoke(
        app, ["mcp", "init-chrome", "--scope", "project", "--cwd", str(workspace)]
    )

    assert result.exit_code == 0
    path = workspace / ".vibecli" / "mcp.json"
    assert path.exists()
    spec = json.loads(path.read_text(encoding="utf-8"))["mcpServers"]["chrome-devtools"]
    assert spec["command"] == "npx"
    assert spec["args"][:2] == ["-y", "chrome-devtools-mcp@latest"]
    assert "--no-usage-statistics" in spec["args"]


def test_init_chrome_writes_user_config(fake_home: Path) -> None:
    path = write_chrome_devtools_config(scope_root=None)

    assert path == fake_home / ".vibecli" / "mcp.json"


def test_init_chrome_flags_are_passed_through(workspace: Path) -> None:
    path = write_chrome_devtools_config(
        scope_root=workspace,
        browser_url="http://127.0.0.1:9222",
        headless=True,
        slim=True,
    )

    args = json.loads(path.read_text(encoding="utf-8"))["mcpServers"]["chrome-devtools"]["args"]
    assert "--headless" in args
    assert "--slim" in args
    assert "--browser-url=http://127.0.0.1:9222" in args


def test_init_chrome_merges_existing_servers(workspace: Path) -> None:
    (workspace / ".vibecli").mkdir()
    (workspace / ".vibecli" / "mcp.json").write_text(
        json.dumps({"mcpServers": {"other": {"command": "other-server"}}}),
        encoding="utf-8",
    )

    write_chrome_devtools_config(scope_root=workspace)

    servers = json.loads((workspace / ".vibecli" / "mcp.json").read_text(encoding="utf-8"))
    assert set(servers["mcpServers"]) == {"other", "chrome-devtools"}


def test_mcp_specs_merge_home_and_project(fake_home: Path, workspace: Path) -> None:
    (fake_home / ".vibecli").mkdir()
    (fake_home / ".vibecli" / "mcp.json").write_text(
        json.dumps({"mcpServers": {"shared": {"command": "user-version"}}}),
        encoding="utf-8",
    )
    (workspace / ".vibecli").mkdir()
    (workspace / ".vibecli" / "mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "shared": {"command": "project-version"},
                    "remote": {"url": "https://example.com/mcp", "type": "streamable_http"},
                }
            }
        ),
        encoding="utf-8",
    )

    specs = load_mcp_server_specs(workspace)

    assert specs["shared"].command == "project-version"
    assert specs["remote"].type == "streamable_http"
    assert specs["remote"].url == "https://example.com/mcp"


def test_mcp_specs_expand_project_dir(workspace: Path) -> None:
    (workspace / ".vibecli").mkdir()
    (workspace / ".vibecli" / "mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "fs": {
                        "command": "npx",
                        "args": ["server", "--root", "${PROJECT_DIR}"],
                        "env": {"ROOT": "${PROJECT_DIR}"},
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    specs = load_mcp_server_specs(workspace)

    assert specs["fs"].args[-1] == str(workspace.resolve())
    assert specs["fs"].env["ROOT"] == str(workspace.resolve())
    assert specs["fs"].type == "stdio"


def test_sdk_engine_is_wired_for_local_use(workspace: Path) -> None:
    engine = create_default_engine(cwd=str(workspace))

    assert engine.cwd == str(workspace.resolve())
    assert "read_file" in engine.tool_registry.list_names()
    assert engine.system_prompt
