"""Tests for scenario validation pipeline."""

import tempfile
from pathlib import Path

import pytest

from salvo.loader.validator import (
    ValidationErrorDetail,
    validate_scenario_file,
    validate_scenario_string,
)


class TestValidateScenarioString:
    """Tests for validate_scenario_string function."""

    def test_valid_scenario_returns_scenario_and_empty_errors(self):
        """Valid YAML returns a Scenario object and empty error list."""
        source = "model: gpt-4\nprompt: hello world\n"
        scenario, errors = validate_scenario_string(source)
        assert scenario is not None
        assert errors == []
        assert scenario.model == "gpt-4"
        assert scenario.prompt == "hello world"

    def test_missing_required_field_model(self):
        """Missing required field 'model' returns error with type='missing'."""
        source = "prompt: hello\n"
        scenario, errors = validate_scenario_string(source)
        assert scenario is None
        assert len(errors) >= 1
        model_errors = [e for e in errors if e.field == "model"]
        assert len(model_errors) == 1
        assert "missing" in model_errors[0].type

    def test_missing_required_field_prompt(self):
        """Missing required field 'prompt' returns error with type='missing'."""
        source = "model: gpt-4\n"
        scenario, errors = validate_scenario_string(source)
        assert scenario is None
        prompt_errors = [e for e in errors if e.field == "prompt"]
        assert len(prompt_errors) == 1
        assert "missing" in prompt_errors[0].type

    def test_unknown_field_with_suggestion(self):
        """Unknown field 'modle' returns extra_forbidden error with 'did you mean' suggestion."""
        source = "modle: gpt-4\nprompt: hello\n"
        scenario, errors = validate_scenario_string(source)
        assert scenario is None
        modle_errors = [e for e in errors if e.field == "modle"]
        assert len(modle_errors) == 1
        assert "extra" in modle_errors[0].type.lower() or "forbidden" in modle_errors[0].type.lower()
        assert modle_errors[0].suggestion is not None
        assert "model" in modle_errors[0].suggestion.lower()

    def test_wrong_type_returns_type_error_with_line(self):
        """Wrong type (threshold: 'high') returns type error with line number."""
        source = "model: gpt-4\nprompt: hello\nthreshold: high\n"
        scenario, errors = validate_scenario_string(source)
        assert scenario is None
        threshold_errors = [e for e in errors if e.field == "threshold"]
        assert len(threshold_errors) >= 1
        assert threshold_errors[0].line is not None

    def test_multiple_errors_returned_at_once(self):
        """Multiple errors (missing model AND unknown field) are returned all at once."""
        source = "modle: gpt-4\npromt: hello\n"
        scenario, errors = validate_scenario_string(source)
        assert scenario is None
        assert len(errors) >= 2

    def test_threshold_out_of_range(self):
        """Threshold out of range (1.5) returns value error."""
        source = "model: gpt-4\nprompt: hello\nthreshold: 1.5\n"
        scenario, errors = validate_scenario_string(source)
        assert scenario is None
        threshold_errors = [e for e in errors if e.field == "threshold"]
        assert len(threshold_errors) >= 1

    def test_nested_validation_error(self):
        """Tool missing 'name' field returns error with nested loc path."""
        source = "model: gpt-4\nprompt: hello\ntools:\n  - description: a tool\n"
        scenario, errors = validate_scenario_string(source)
        assert scenario is None
        # Error should reference the nested location
        nested_errors = [e for e in errors if "tools" in e.field]
        assert len(nested_errors) >= 1

    def test_valid_scenario_with_system_prompt(self):
        """Valid YAML with system_prompt and prompt both populated succeeds."""
        source = "model: gpt-4\nsystem_prompt: you are helpful\nprompt: hello\n"
        scenario, errors = validate_scenario_string(source)
        assert scenario is not None
        assert errors == []
        assert scenario.system_prompt == "you are helpful"

    def test_valid_yaml_line_numbers_in_errors(self):
        """Errors include line numbers from the source YAML."""
        source = "model: gpt-4\nprompt: hello\nthreshold: high\n"
        scenario, errors = validate_scenario_string(source)
        assert scenario is None
        # threshold is on line 3
        threshold_errors = [e for e in errors if e.field == "threshold"]
        assert threshold_errors[0].line == 3


class TestValidateScenarioFile:
    """Tests for validate_scenario_file function."""

    def test_validate_file_with_valid_scenario(self):
        """validate_scenario_file with valid temp file returns Scenario and no errors."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
            f.write("model: gpt-4\nprompt: hello\n")
            f.flush()
            scenario, errors = validate_scenario_file(Path(f.name))
        assert scenario is not None
        assert errors == []

    def test_validate_file_with_invalid_scenario(self):
        """validate_scenario_file with invalid temp file returns errors."""
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
            f.write("modle: gpt-4\n")
            f.flush()
            scenario, errors = validate_scenario_file(Path(f.name))
        assert scenario is None
        assert len(errors) >= 1

    def test_include_tag_resolves_external_file(self):
        """!include tag resolves shared tool file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Write shared tool file
            tool_file = tmpdir / "tools" / "search.yaml"
            tool_file.parent.mkdir(parents=True, exist_ok=True)
            tool_file.write_text(
                "name: search\ndescription: search the web\n"
            )

            # Write scenario that includes the tool
            scenario_file = tmpdir / "scenario.yaml"
            scenario_file.write_text(
                "model: gpt-4\n"
                "prompt: hello\n"
                "tools:\n"
                "  - !include tools/search.yaml\n"
            )

            scenario, errors = validate_scenario_file(scenario_file)
            assert scenario is not None
            assert errors == []
            assert len(scenario.tools) == 1
            assert scenario.tools[0].name == "search"
