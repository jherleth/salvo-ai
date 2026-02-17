"""Project configuration model for Salvo.

Captures salvo.yaml fields with sensible defaults for
project-level settings like adapter, model, and paths.
"""

from __future__ import annotations

from pydantic import BaseModel


class ProjectConfig(BaseModel):
    """Project-level configuration loaded from salvo.yaml."""

    model_config = {"extra": "forbid"}

    default_adapter: str = "openai"
    default_model: str = "gpt-4o"
    scenarios_dir: str = "scenarios"
    ci_mode: bool = False
    storage_dir: str = ".salvo"
