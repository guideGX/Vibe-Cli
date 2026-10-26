from __future__ import annotations

import json
from pathlib import Path

from vibecli.config import config_to_public_dict, load_config


def test_defaults_when_nothing_is_configured(fake_home: Path, workspace: Path) -> None:
    config = load_config(project_root=workspace, env={})

    assert config.llm.provider == "deepseek"
    assert config.llm.model == "deepseek-v4-flash"
    assert config.llm.api_key == ""
    assert config.policy.hitl_mode == "auto"
    assert config.features.mcp is True


def test_generic_env_vars_override_defaults(fake_home: Path, workspace: Path) -> None:
    config = load_config(
        project_root=workspace,
        env={
            "VIBECLI_API_KEY": "sk-generic",
            "VIBECLI_PROVIDER": "kimi",
            "VIBECLI_MODEL": "moonshot-v1-8k",
            "VIBECLI_MAX_TOKENS": "2048",
            "VIBECLI_TEMPERATURE": "0.2",
            "VIBECLI_HITL": "always",
            "VIBECLI_RENDER_MODE": "plain",
            "VIBECLI_MCP": "false",
        },
    )

    assert config.llm.api_key == "sk-generic"
    assert config.llm.provider == "kimi"
    assert config.llm.model == "moonshot-v1-8k"
    assert config.llm.max_tokens == 2048
    assert config.llm.temperature == 0.2
    assert config.policy.hitl_mode == "always"
    assert config.render_mode == "plain"
    assert config.features.mcp is False


def test_provider_specific_key_is_picked_up(fake_home: Path, workspace: Path) -> None:
    config = load_config(
        project_root=workspace,
        env={"VIBECLI_PROVIDER": "deepseek", "DEEPSEEK_API_KEY": "sk-deepseek"},
    )

    assert config.llm.api_key == "sk-deepseek"


def test_provider_model_env_var_wins(fake_home: Path, workspace: Path) -> None:
    config = load_config(
        project_root=workspace,
        env={"VIBECLI_PROVIDER": "glm", "GLM_MODEL": "glm-4-plus"},
    )

    assert config.llm.model == "glm-4-plus"


def test_project_dotenv_is_loaded(fake_home: Path, workspace: Path) -> None:
    (workspace / ".env").write_text(
        'VIBECLI_PROVIDER=deepseek\nVIBECLI_MODEL="deepseek-v4-pro"\nDEEPSEEK_API_KEY=sk-dotenv\n',
        encoding="utf-8",
    )

    config = load_config(project_root=workspace, env={})

    assert config.llm.model == "deepseek-v4-pro"
    assert config.llm.api_key == "sk-dotenv"


def test_process_env_beats_project_dotenv(fake_home: Path, workspace: Path) -> None:
    (workspace / ".env").write_text("VIBECLI_MODEL=from-dotenv\n", encoding="utf-8")

    config = load_config(project_root=workspace, env={"VIBECLI_MODEL": "from-process"})

    assert config.llm.model == "from-process"


def test_project_config_overrides_user_config(fake_home: Path, workspace: Path) -> None:
    (fake_home / ".vibecli").mkdir()
    (fake_home / ".vibecli" / "config.json").write_text(
        json.dumps({"llm": {"model": "user-model"}, "policy": {"hitl_mode": "never"}}),
        encoding="utf-8",
    )
    (workspace / ".vibecli").mkdir()
    (workspace / ".vibecli" / "config.json").write_text(
        json.dumps({"llm": {"model": "project-model"}}),
        encoding="utf-8",
    )

    config = load_config(project_root=workspace, env={})

    assert config.llm.model == "project-model"
    assert config.policy.hitl_mode == "never"


def test_state_paths_are_expanded(fake_home: Path, workspace: Path) -> None:
    config = load_config(project_root=workspace, env={})

    # ``~`` must be expanded to an absolute path, never left literal.
    assert config.memory.long_term_db_path.endswith(str(Path(".vibecli") / "memory.db"))
    assert config.policy.audit_log_path.endswith(str(Path(".vibecli") / "audit.jsonl"))
    assert "~" not in config.memory.long_term_db_path
    assert Path(config.memory.long_term_db_path).is_absolute()


def test_public_dict_redacts_api_key(fake_home: Path, workspace: Path) -> None:
    config = load_config(project_root=workspace, env={"VIBECLI_API_KEY": "sk-secret"})

    public = config_to_public_dict(config)

    assert public["llm"]["api_key"] == "***"
    assert "sk-secret" not in json.dumps(public)
