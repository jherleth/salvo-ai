"""Scenario data models for Salvo test definitions.

These models encode the user-facing YAML contract for defining
agent test scenarios, including tool definitions and assertions.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolParameter(BaseModel):
    """Parameters schema for a tool definition (JSON Schema subset)."""

    model_config = {"extra": "forbid"}

    type: Literal["object"] = "object"
    properties: dict[str, Any] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list)


class ToolDef(BaseModel):
    """Definition of a tool available to the agent during a scenario run."""

    model_config = {"extra": "forbid"}

    name: str
    description: str
    parameters: ToolParameter = Field(default_factory=ToolParameter)
    mock_response: str | dict[str, Any] | None = None


class Assertion(BaseModel):
    """A single assertion to evaluate against an agent run."""

    model_config = {"extra": "forbid"}

    type: str
    weight: float = 1.0
    required: bool = False
    tool: str | None = None
    mode: Literal["exact", "in_order", "any_order"] | None = None
    sequence: list[str] | None = None
    value: Any = None
    expression: str | None = None
    operator: str | None = None
    max_usd: float | None = None
    max_seconds: float | None = None


class Scenario(BaseModel):
    """A complete test scenario definition loaded from YAML.

    Represents the user-facing contract for defining agent test
    scenarios, including model configuration, prompts, available
    tools, and evaluation assertions.
    """

    model_config = {"extra": "forbid"}

    description: str = ""
    tags: dict[str, str] = Field(default_factory=dict)
    adapter: str = "openai"
    model: str
    system_prompt: str = ""
    prompt: str
    tools: list[ToolDef] = Field(default_factory=list)
    assertions: list[Assertion] = Field(default_factory=list)
    threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    max_turns: int = Field(default=10, ge=1, le=100)
    temperature: float | None = None
    seed: int | None = None
    extras: dict[str, Any] = Field(default_factory=dict)
