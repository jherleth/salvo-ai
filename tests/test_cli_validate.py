"""Tests for the salvo validate CLI command."""

import tempfile
from pathlib import Path

from typer.testing import CliRunner

from salvo.cli.main import app

runner = CliRunner()


class TestValidateCommand:
    """Tests for salvo validate CLI command."""

    def test_validate_valid_scenario_exits_zero(self):
        """salvo validate with valid scenario exits with code 0 and prints success."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
            f.write("model: gpt-4\nprompt: hello\n")
            f.flush()
            result = runner.invoke(app, ["validate", f.name])
        assert result.exit_code == 0
        assert "valid" in result.output.lower()

    def test_validate_invalid_scenario_exits_nonzero(self):
        """salvo validate with invalid scenario exits with non-zero code and prints errors."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
            f.write("modle: gpt-4\n")
            f.flush()
            result = runner.invoke(app, ["validate", f.name])
        assert result.exit_code != 0

    def test_validate_ci_mode_concise_format(self):
        """salvo validate --ci with invalid file prints concise format."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
            f.write("modle: gpt-4\n")
            f.flush()
            result = runner.invoke(app, ["validate", "--ci", f.name])
        assert result.exit_code != 0
        # CI format should contain the filename and -- separator
        assert "--" in result.output

    def test_validate_no_args_scans_scenarios_dir(self):
        """salvo validate with no arguments validates files in scenarios/ directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)
            scenarios_dir = tmpdir / "scenarios"
            scenarios_dir.mkdir()
            (scenarios_dir / "test.yaml").write_text("model: gpt-4\nprompt: hello\n")
            # Run from the temp dir
            import os
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                result = runner.invoke(app, ["validate"])
            finally:
                os.chdir(old_cwd)
        assert result.exit_code == 0

    def test_validate_nonexistent_file_prints_error(self):
        """salvo validate with nonexistent file prints clear error."""
        result = runner.invoke(app, ["validate", "/nonexistent/file.yaml"])
        assert result.exit_code != 0
        # Should contain some indication the file was not found
        assert "not found" in result.output.lower() or "error" in result.output.lower() or "no such file" in result.output.lower()
