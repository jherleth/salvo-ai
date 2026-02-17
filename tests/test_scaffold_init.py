"""Tests for salvo init project scaffolding."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from salvo.cli.main import app
from salvo.models.config import ProjectConfig
from salvo.models.scenario import Scenario
from salvo.scaffold.init import ProjectExistsError, scaffold_project

runner = CliRunner()


class TestScaffoldProject:
    """Tests for the scaffold_project() function."""

    def test_creates_all_expected_files(self, tmp_path: Path) -> None:
        """scaffold_project creates salvo.yaml, example scenario, tool file, and .gitignore."""
        scaffold_project(tmp_path)

        assert (tmp_path / "salvo.yaml").exists()
        assert (tmp_path / "scenarios" / "example.yaml").exists()
        assert (tmp_path / "tools" / "example_tool.yaml").exists()
        assert (tmp_path / ".gitignore").exists()

    def test_salvo_yaml_is_valid_and_matches_config_schema(self, tmp_path: Path) -> None:
        """Generated salvo.yaml is valid YAML matching ProjectConfig."""
        scaffold_project(tmp_path)
        content = (tmp_path / "salvo.yaml").read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        config = ProjectConfig.model_validate(data)
        assert config.default_adapter == "openai"
        assert config.default_model == "gpt-4o"
        assert config.scenarios_dir == "scenarios"

    def test_example_yaml_is_valid_scenario(self, tmp_path: Path) -> None:
        """Generated example.yaml parses as a valid Scenario model."""
        scaffold_project(tmp_path)
        scenario_file = tmp_path / "scenarios" / "example.yaml"
        content = scenario_file.read_text(encoding="utf-8")

        # The example uses !include which resolves relative to the scenario
        # file's directory, so we must do the same in the test loader
        scenario_dir = scenario_file.parent

        class IncludeLoader(yaml.SafeLoader):
            pass

        def include_constructor(loader, node):
            """Resolve !include relative to scenario file directory."""
            include_path = (scenario_dir / loader.construct_scalar(node)).resolve()
            return yaml.safe_load(include_path.read_text(encoding="utf-8"))

        IncludeLoader.add_constructor("!include", include_constructor)

        data = yaml.load(content, Loader=IncludeLoader)
        scenario = Scenario.model_validate(data)
        assert scenario.description
        assert len(scenario.tools) >= 4
        assert len(scenario.assertions) >= 4
        assert scenario.threshold == 0.8

    def test_gitignore_contains_salvo_dir(self, tmp_path: Path) -> None:
        """.gitignore contains .salvo/ entry."""
        scaffold_project(tmp_path)
        content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
        assert ".salvo/" in content

    def test_raises_error_without_force(self, tmp_path: Path) -> None:
        """Running scaffold_project twice without --force raises ProjectExistsError."""
        scaffold_project(tmp_path)
        with pytest.raises(ProjectExistsError) as exc_info:
            scaffold_project(tmp_path)
        assert len(exc_info.value.conflicting_files) > 0

    def test_force_overwrites_existing(self, tmp_path: Path) -> None:
        """Running with force=True overwrites existing files."""
        scaffold_project(tmp_path)
        # Modify a file
        (tmp_path / "salvo.yaml").write_text("modified", encoding="utf-8")
        # Force should succeed
        scaffold_project(tmp_path, force=True)
        content = (tmp_path / "salvo.yaml").read_text(encoding="utf-8")
        assert "modified" not in content
        assert "default_adapter" in content

    def test_gitignore_append_preserves_existing(self, tmp_path: Path) -> None:
        """.gitignore with existing content gets .salvo/ appended, not replaced."""
        existing_content = "node_modules/\n*.pyc\n"
        (tmp_path / ".gitignore").write_text(existing_content, encoding="utf-8")
        scaffold_project(tmp_path)
        content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
        assert "node_modules/" in content
        assert "*.pyc" in content
        assert ".salvo/" in content

    def test_gitignore_no_duplicate(self, tmp_path: Path) -> None:
        """.gitignore with .salvo/ already present does not duplicate it."""
        existing_content = "node_modules/\n.salvo/\n"
        (tmp_path / ".gitignore").write_text(existing_content, encoding="utf-8")
        scaffold_project(tmp_path)
        content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
        assert content.count(".salvo/") == 1

    def test_returns_list_of_created_files(self, tmp_path: Path) -> None:
        """scaffold_project returns a list of created file paths."""
        created = scaffold_project(tmp_path)
        assert isinstance(created, list)
        assert len(created) >= 4  # 3 template files + .gitignore


class TestInitCLI:
    """Tests for the salvo init CLI command."""

    def test_init_default_directory(self, tmp_path: Path) -> None:
        """salvo init in a temp directory creates expected files."""
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 0
        assert (tmp_path / "salvo.yaml").exists()
        assert (tmp_path / "scenarios" / "example.yaml").exists()

    def test_init_force_flag(self, tmp_path: Path) -> None:
        """salvo init --force overwrites existing files."""
        runner.invoke(app, ["init", str(tmp_path)])
        result = runner.invoke(app, ["init", str(tmp_path), "--force"])
        assert result.exit_code == 0

    def test_init_specified_directory(self, tmp_path: Path) -> None:
        """salvo init /path/to/dir creates files in specified directory."""
        target = tmp_path / "myproject"
        target.mkdir()
        result = runner.invoke(app, ["init", str(target)])
        assert result.exit_code == 0
        assert (target / "salvo.yaml").exists()
        assert (target / "scenarios" / "example.yaml").exists()
        assert (target / "tools" / "example_tool.yaml").exists()

    def test_init_refuses_overwrite_without_force(self, tmp_path: Path) -> None:
        """salvo init refuses to overwrite without --force."""
        runner.invoke(app, ["init", str(tmp_path)])
        result = runner.invoke(app, ["init", str(tmp_path)])
        assert result.exit_code == 1

    def test_init_help(self) -> None:
        """salvo init --help prints usage."""
        result = runner.invoke(app, ["init", "--help"])
        assert result.exit_code == 0
        assert "Initialize" in result.output or "initialize" in result.output.lower()
