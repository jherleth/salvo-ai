"""Project configuration model for Salvo.

Captures salvo.yaml fields with sensible defaults for
project-level settings like adapter, model, and paths.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class RecordingConfig(BaseModel):
    """Configuration for trace recording behavior.

    Controls recording mode (full vs metadata_only) and custom
    redaction patterns that extend the built-in set.
    """

    model_config = {"extra": "forbid"}

    mode: Literal["full", "metadata_only"] = "full"
    custom_redaction_patterns: list[str] = Field(default_factory=list)


class JudgeConfig(BaseModel):
    """Configuration for LLM judge evaluation defaults.

    Controls the adapter, model, vote count, and generation parameters
    used for judge assertions. Per-assertion overrides take precedence.
    """

    model_config = {"extra": "forbid"}

    adapter: str = "openai"
    model: str = "gpt-4o-mini"
    k: int = Field(default=3, ge=1, le=21)
    temperature: float = 0.0
    max_tokens: int = 1024
    default_threshold: float = Field(default=0.8, ge=0.0, le=1.0)


class ProjectConfig(BaseModel):
    """Project-level configuration loaded from salvo.yaml."""

    model_config = {"extra": "forbid"}

    default_adapter: str = "openai"
    default_model: str = "gpt-4o"
    scenarios_dir: str = "scenarios"
    ci_mode: bool = False
    storage_dir: str = ".salvo"
    judge: JudgeConfig = Field(default_factory=JudgeConfig)
    recording: RecordingConfig = Field(default_factory=RecordingConfig)


def find_project_root(start: Path | None = None) -> Path:
    """Walk up from start (default: cwd) looking for salvo.yaml or .salvo/.

    Args:
        start: Starting path (file or directory). Defaults to cwd.

    Returns:
        Path to the project root directory containing salvo.yaml or .salvo/,
        or cwd if neither is found.
    """
    current = (start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent
    while current != current.parent:
        if (current / "salvo.yaml").exists() or (current / ".salvo").exists():
            return current
        current = current.parent
    return Path.cwd()


def load_project_config(project_root: Path | None = None) -> ProjectConfig:
    """Load ProjectConfig from salvo.yaml. Returns defaults if not found.

    Args:
        project_root: Path to the project root directory. If None,
            uses find_project_root() to locate it.

    Returns:
        Validated ProjectConfig instance.
    """
    if project_root is None:
        project_root = find_project_root()
    config_path = project_root / "salvo.yaml"
    if not config_path.exists():
        return ProjectConfig()
    import yaml

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if raw is None:
        return ProjectConfig()
    return ProjectConfig.model_validate(raw)
