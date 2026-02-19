"""Tests for salvo.models.config - ProjectConfig, find_project_root, load_project_config."""

from pathlib import Path

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


class TestJudgeConfigDefaultThreshold:
    """Test JudgeConfig.default_threshold field."""

    def test_default_threshold_defaults_to_08(self):
        """JudgeConfig.default_threshold defaults to 0.8."""
        from salvo.models.config import JudgeConfig

        judge = JudgeConfig()
        assert judge.default_threshold == 0.8

    def test_default_threshold_validates_range(self):
        """JudgeConfig.default_threshold rejects values outside [0.0, 1.0]."""
        from salvo.models.config import JudgeConfig

        with pytest.raises(ValidationError):
            JudgeConfig(default_threshold=1.5)
        with pytest.raises(ValidationError):
            JudgeConfig(default_threshold=-0.1)

    def test_default_threshold_custom_value(self):
        """JudgeConfig.default_threshold accepts valid custom value."""
        from salvo.models.config import JudgeConfig

        judge = JudgeConfig(default_threshold=0.5)
        assert judge.default_threshold == 0.5


class TestFindProjectRoot:
    """Test find_project_root function."""

    def test_returns_cwd_when_nothing_found(self, tmp_path: Path):
        """Returns cwd when no salvo.yaml or .salvo/ found in parents."""
        from salvo.models.config import find_project_root

        # Deep nested directory with nothing
        deep = tmp_path / "a" / "b" / "c"
        deep.mkdir(parents=True)
        result = find_project_root(deep)
        assert result == Path.cwd()

    def test_finds_salvo_yaml_in_parent(self, tmp_path: Path):
        """Finds salvo.yaml in parent directory."""
        from salvo.models.config import find_project_root

        (tmp_path / "salvo.yaml").write_text("default_model: gpt-4o\n")
        child = tmp_path / "scenarios"
        child.mkdir()
        result = find_project_root(child)
        assert result == tmp_path.resolve()

    def test_finds_dot_salvo_in_parent(self, tmp_path: Path):
        """Finds .salvo/ directory in parent."""
        from salvo.models.config import find_project_root

        (tmp_path / ".salvo").mkdir()
        child = tmp_path / "sub"
        child.mkdir()
        result = find_project_root(child)
        assert result == tmp_path.resolve()

    def test_handles_file_path_input(self, tmp_path: Path):
        """Uses parent when start is a file path."""
        from salvo.models.config import find_project_root

        (tmp_path / "salvo.yaml").write_text("default_model: gpt-4o\n")
        file_path = tmp_path / "scenario.yaml"
        file_path.write_text("model: gpt-4o\nprompt: test\n")
        result = find_project_root(file_path)
        assert result == tmp_path.resolve()


class TestLoadProjectConfig:
    """Test load_project_config function."""

    def test_returns_defaults_when_no_salvo_yaml(self, tmp_path: Path):
        """Returns default ProjectConfig when salvo.yaml does not exist."""
        from salvo.models.config import ProjectConfig, load_project_config

        config = load_project_config(tmp_path)
        assert isinstance(config, ProjectConfig)
        assert config.default_adapter == "openai"
        assert config.default_model == "gpt-4o"

    def test_loads_valid_salvo_yaml_with_judge(self, tmp_path: Path):
        """Loads salvo.yaml including judge section."""
        from salvo.models.config import load_project_config

        yaml_content = (
            "default_adapter: anthropic\n"
            "default_model: claude-sonnet-4-5\n"
            "judge:\n"
            "  adapter: anthropic\n"
            "  model: claude-haiku-4-5\n"
            "  k: 5\n"
            "  temperature: 0.1\n"
            "  default_threshold: 0.7\n"
        )
        (tmp_path / "salvo.yaml").write_text(yaml_content)
        config = load_project_config(tmp_path)
        assert config.default_adapter == "anthropic"
        assert config.default_model == "claude-sonnet-4-5"
        assert config.judge.adapter == "anthropic"
        assert config.judge.model == "claude-haiku-4-5"
        assert config.judge.k == 5
        assert config.judge.temperature == 0.1
        assert config.judge.default_threshold == 0.7

    def test_empty_salvo_yaml_returns_defaults(self, tmp_path: Path):
        """Empty salvo.yaml returns default ProjectConfig."""
        from salvo.models.config import ProjectConfig, load_project_config

        (tmp_path / "salvo.yaml").write_text("")
        config = load_project_config(tmp_path)
        assert isinstance(config, ProjectConfig)
        assert config.default_adapter == "openai"


class TestRunStoreWithStorageDir:
    """Test RunStore with custom storage_dir."""

    def test_custom_storage_dir(self, tmp_path: Path):
        """RunStore uses specified storage_dir instead of .salvo."""
        from salvo.storage.json_store import RunStore

        store = RunStore(tmp_path, storage_dir="custom_data")
        store.ensure_dirs()
        assert (tmp_path / "custom_data" / "runs").is_dir()
        assert (tmp_path / "custom_data" / "traces").is_dir()
        assert not (tmp_path / ".salvo").exists()

    def test_default_storage_dir(self, tmp_path: Path):
        """RunStore without storage_dir uses .salvo."""
        from salvo.storage.json_store import RunStore

        store = RunStore(tmp_path)
        store.ensure_dirs()
        assert (tmp_path / ".salvo" / "runs").is_dir()
