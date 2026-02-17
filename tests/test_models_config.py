"""Tests for salvo.models.config - ProjectConfig."""

import pytest
from pydantic import ValidationError


class TestProjectConfig:
    """Test ProjectConfig model."""

    def test_defaults(self):
        """ProjectConfig has sensible defaults."""
        from salvo.models import ProjectConfig

        config = ProjectConfig()
        assert config.default_adapter == "openai"
        assert config.default_model == "gpt-4o"
        assert config.scenarios_dir == "scenarios"
        assert config.ci_mode is False
        assert config.storage_dir == ".salvo"

    def test_custom_values(self):
        """ProjectConfig accepts custom values."""
        from salvo.models import ProjectConfig

        config = ProjectConfig(
            default_adapter="anthropic",
            default_model="claude-sonnet-4-5",
            scenarios_dir="tests/scenarios",
            ci_mode=True,
            storage_dir="data/runs",
        )
        assert config.default_adapter == "anthropic"
        assert config.default_model == "claude-sonnet-4-5"
        assert config.scenarios_dir == "tests/scenarios"
        assert config.ci_mode is True
        assert config.storage_dir == "data/runs"

    def test_rejects_unknown_keys(self):
        """ProjectConfig rejects unknown keys."""
        from salvo.models import ProjectConfig

        with pytest.raises(ValidationError, match="extra_forbidden"):
            ProjectConfig.model_validate({"unknown_field": True})
