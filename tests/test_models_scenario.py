"""Tests for salvo.models.scenario - Scenario, ToolDef, ToolParameter, Assertion."""

import pytest
from pydantic import ValidationError


class TestScenarioCreation:
    """Test Scenario model creation and validation."""

    def test_valid_scenario_from_dict(self):
        """A valid scenario dict creates a Scenario instance."""
        from salvo.models import Scenario

        data = {
            "adapter": "openai",
            "model": "gpt-4o",
            "system_prompt": "You are a helpful assistant.",
            "prompt": "Fix the failing tests",
            "tools": [
                {
                    "name": "file_read",
                    "description": "Read a file",
                    "parameters": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"],
                    },
                }
            ],
            "assertions": [
                {"type": "tool_call", "tool": "file_read", "weight": 1.0}
            ],
            "threshold": 0.8,
        }
        scenario = Scenario.model_validate(data)
        assert scenario.model == "gpt-4o"
        assert scenario.adapter == "openai"
        assert scenario.prompt == "Fix the failing tests"
        assert scenario.threshold == 0.8
        assert len(scenario.tools) == 1
        assert len(scenario.assertions) == 1

    def test_extra_fields_rejected(self):
        """Unknown keys are rejected with extra='forbid'."""
        from salvo.models import Scenario

        data = {
            "modle": "gpt-4o",
            "model": "gpt-4o",
            "prompt": "test",
            "tools": [],
            "assertions": [],
        }
        with pytest.raises(ValidationError, match="extra_forbidden"):
            Scenario.model_validate(data)

    def test_threshold_below_zero_rejected(self):
        """Threshold must be >= 0.0."""
        from salvo.models import Scenario

        data = {
            "model": "gpt-4o",
            "prompt": "test",
            "tools": [],
            "assertions": [],
            "threshold": -0.1,
        }
        with pytest.raises(ValidationError):
            Scenario.model_validate(data)

    def test_threshold_above_one_rejected(self):
        """Threshold must be <= 1.0."""
        from salvo.models import Scenario

        data = {
            "model": "gpt-4o",
            "prompt": "test",
            "tools": [],
            "assertions": [],
            "threshold": 1.5,
        }
        with pytest.raises(ValidationError):
            Scenario.model_validate(data)

    def test_model_required(self):
        """model is a required field."""
        from salvo.models import Scenario

        data = {
            "prompt": "test",
            "tools": [],
            "assertions": [],
        }
        with pytest.raises(ValidationError):
            Scenario.model_validate(data)

    def test_prompt_required(self):
        """prompt is a required field."""
        from salvo.models import Scenario

        data = {
            "model": "gpt-4o",
            "tools": [],
            "assertions": [],
        }
        with pytest.raises(ValidationError):
            Scenario.model_validate(data)

    def test_system_prompt_and_prompt_both_populated(self):
        """Both system_prompt and prompt can be populated (SCEN-03)."""
        from salvo.models import Scenario

        data = {
            "model": "gpt-4o",
            "system_prompt": "You are a code reviewer.",
            "prompt": "Review this file",
            "tools": [],
            "assertions": [],
        }
        scenario = Scenario.model_validate(data)
        assert scenario.system_prompt == "You are a code reviewer."
        assert scenario.prompt == "Review this file"

    def test_empty_tools_and_assertions_valid(self):
        """Scenario with empty tools and assertions lists is valid."""
        from salvo.models import Scenario

        data = {
            "model": "gpt-4o",
            "prompt": "test",
            "tools": [],
            "assertions": [],
        }
        scenario = Scenario.model_validate(data)
        assert scenario.tools == []
        assert scenario.assertions == []


class TestToolDef:
    """Test ToolDef model."""

    def test_tooldef_creation(self):
        """ToolDef with name, description, parameters, mock_response."""
        from salvo.models import ToolDef

        data = {
            "name": "file_read",
            "description": "Read a file from disk",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
            "mock_response": "file contents here",
        }
        tool = ToolDef.model_validate(data)
        assert tool.name == "file_read"
        assert tool.description == "Read a file from disk"
        assert tool.mock_response == "file contents here"

    def test_tooldef_rejects_unknown_keys(self):
        """ToolDef rejects unknown keys."""
        from salvo.models import ToolDef

        data = {
            "name": "file_read",
            "description": "Read a file",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
            "unknown_field": True,
        }
        with pytest.raises(ValidationError, match="extra_forbidden"):
            ToolDef.model_validate(data)


class TestToolParameter:
    """Test ToolParameter model."""

    def test_tool_parameter_with_properties_and_required(self):
        """ToolParameter validates type='object' with properties and required."""
        from salvo.models import ToolParameter

        data = {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "encoding": {"type": "string"},
            },
            "required": ["path"],
        }
        param = ToolParameter.model_validate(data)
        assert param.type == "object"
        assert "path" in param.properties
        assert param.required == ["path"]


class TestAssertion:
    """Test Assertion model."""

    def test_assertion_all_fields(self):
        """Assertion creation with all supported fields."""
        from salvo.models import Assertion

        data = {
            "type": "tool_call",
            "weight": 2.0,
            "required": True,
            "tool": "file_read",
            "mode": "exact",
            "sequence": ["file_read", "file_write"],
            "value": "expected_value",
            "expression": "output.result",
            "operator": "equals",
        }
        assertion = Assertion.model_validate(data)
        assert assertion.type == "tool_call"
        assert assertion.weight == 2.0
        assert assertion.required is True
        assert assertion.tool == "file_read"
        assert assertion.mode == "exact"
        assert assertion.sequence == ["file_read", "file_write"]
        assert assertion.value == "expected_value"
        assert assertion.expression == "output.result"
        assert assertion.operator == "equals"

    def test_assertion_defaults(self):
        """Assertion defaults: weight=1.0, required=False."""
        from salvo.models import Assertion

        data = {"type": "tool_call"}
        assertion = Assertion.model_validate(data)
        assert assertion.weight == 1.0
        assert assertion.required is False

    def test_assertion_rejects_unknown_keys(self):
        """Assertion rejects unknown keys."""
        from salvo.models import Assertion

        data = {"type": "tool_call", "unknown_field": True}
        with pytest.raises(ValidationError, match="extra_forbidden"):
            Assertion.model_validate(data)


class TestScenarioPhase2Fields:
    """Test Phase 2 execution fields on Scenario model."""

    def _minimal(self, **overrides) -> dict:
        """Return minimal valid scenario dict with overrides applied."""
        base = {"model": "gpt-4o", "prompt": "test"}
        base.update(overrides)
        return base

    def test_scenario_default_max_turns(self):
        """max_turns defaults to 10."""
        from salvo.models import Scenario

        scenario = Scenario.model_validate(self._minimal())
        assert scenario.max_turns == 10

    def test_scenario_custom_max_turns(self):
        """max_turns can be set to a custom value."""
        from salvo.models import Scenario

        scenario = Scenario.model_validate(self._minimal(max_turns=25))
        assert scenario.max_turns == 25

    def test_scenario_max_turns_validation_ge_1(self):
        """max_turns rejects values less than 1."""
        from salvo.models import Scenario

        with pytest.raises(ValidationError):
            Scenario.model_validate(self._minimal(max_turns=0))

    def test_scenario_max_turns_validation_le_100(self):
        """max_turns rejects values greater than 100."""
        from salvo.models import Scenario

        with pytest.raises(ValidationError):
            Scenario.model_validate(self._minimal(max_turns=101))

    def test_scenario_max_turns_boundary_values(self):
        """max_turns accepts boundary values 1 and 100."""
        from salvo.models import Scenario

        s1 = Scenario.model_validate(self._minimal(max_turns=1))
        assert s1.max_turns == 1
        s100 = Scenario.model_validate(self._minimal(max_turns=100))
        assert s100.max_turns == 100

    def test_scenario_temperature_optional(self):
        """temperature defaults to None."""
        from salvo.models import Scenario

        scenario = Scenario.model_validate(self._minimal())
        assert scenario.temperature is None

    def test_scenario_temperature_set(self):
        """temperature can be set to a float value."""
        from salvo.models import Scenario

        scenario = Scenario.model_validate(self._minimal(temperature=0.7))
        assert scenario.temperature == 0.7

    def test_scenario_seed_optional(self):
        """seed defaults to None."""
        from salvo.models import Scenario

        scenario = Scenario.model_validate(self._minimal())
        assert scenario.seed is None

    def test_scenario_seed_set(self):
        """seed can be set to an integer value."""
        from salvo.models import Scenario

        scenario = Scenario.model_validate(self._minimal(seed=42))
        assert scenario.seed == 42

    def test_scenario_extras_default_empty(self):
        """extras defaults to an empty dict."""
        from salvo.models import Scenario

        scenario = Scenario.model_validate(self._minimal())
        assert scenario.extras == {}

    def test_scenario_extras_accepts_dict(self):
        """extras accepts a dictionary of provider-specific options."""
        from salvo.models import Scenario

        extras = {"top_p": 0.9, "presence_penalty": 0.5}
        scenario = Scenario.model_validate(self._minimal(extras=extras))
        assert scenario.extras == {"top_p": 0.9, "presence_penalty": 0.5}

    def test_scenario_round_trip_with_new_fields(self):
        """JSON serialize/deserialize preserves all Phase 2 fields."""
        from salvo.models import Scenario

        data = self._minimal(
            max_turns=50,
            temperature=0.3,
            seed=123,
            extras={"top_k": 40},
        )
        scenario = Scenario.model_validate(data)
        json_str = scenario.model_dump_json()
        restored = Scenario.model_validate_json(json_str)

        assert restored.max_turns == 50
        assert restored.temperature == 0.3
        assert restored.seed == 123
        assert restored.extras == {"top_k": 40}
        assert restored.model == "gpt-4o"
        assert restored.prompt == "test"
