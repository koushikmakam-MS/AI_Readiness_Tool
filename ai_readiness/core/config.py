"""Configuration loading and management."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Optional

import yaml

from ai_readiness.checkers.base import BaseChecker

DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "default_config.yaml"
USER_CONFIG_DIR = Path.home() / ".ai-readiness"
USER_CONFIG_PATH = USER_CONFIG_DIR / "config.yaml"


def load_config(config_path: Optional[Path] = None) -> dict[str, Any]:
    """Load configuration, merging defaults with user/project overrides."""
    # Start with defaults
    config = _load_yaml(DEFAULT_CONFIG_PATH)

    # Merge user-level config
    if USER_CONFIG_PATH.exists():
        user_config = _load_yaml(USER_CONFIG_PATH)
        config = _deep_merge(config, user_config)

    # Merge explicit config path (highest priority)
    if config_path and config_path.exists():
        override = _load_yaml(config_path)
        config = _deep_merge(config, override)

    return config


def get_llm_config(config: dict[str, Any]) -> dict[str, Any]:
    """Extract LLM configuration."""
    return config.get("llm", {})


def get_dimension_configs(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Extract dimension configurations."""
    return config.get("dimensions", {})


def load_checker_class(dotted_path: str) -> type[BaseChecker]:
    """Dynamically load a checker class from a dotted module path.

    Example: 'ai_readiness.checkers.documentation.DocumentationChecker'
    """
    module_path, class_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    if not (isinstance(cls, type) and issubclass(cls, BaseChecker)):
        raise TypeError(f"{dotted_path} is not a BaseChecker subclass")
    return cls


def init_user_config(api_key: Optional[str] = None) -> Path:
    """Create the user config file with optional API key."""
    USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    config = {
        "llm": {
            "enabled": True,
            "provider": "openai",
            "model": "gpt-4o",
        }
    }
    if api_key:
        config["llm"]["api_key"] = api_key

    USER_CONFIG_PATH.write_text(yaml.dump(config, default_flow_style=False), encoding="utf-8")
    return USER_CONFIG_PATH


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file, returning empty dict on failure."""
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return {}


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge two dicts, with override taking precedence."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
