"""Project configuration model for Salvo.

Captures salvo.yaml fields with sensible defaults for
project-level settings like adapter, model, and paths.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


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


class ProjectConfig(BaseModel):
    """Project-level configuration loaded from salvo.yaml."""

    model_config = {"extra": "forbid"}

    default_adapter: str = "openai"
    default_model: str = "gpt-4o"
    scenarios_dir: str = "scenarios"
    ci_mode: bool = False
    storage_dir: str = ".salvo"
    judge: JudgeConfig = Field(default_factory=JudgeConfig)
