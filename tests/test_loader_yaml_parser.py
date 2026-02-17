"""Tests for YAML parser with line tracking."""

import pytest

from salvo.loader.yaml_parser import YAMLParseError, parse_yaml_with_lines


class TestParseYamlWithLines:
    """Tests for parse_yaml_with_lines function."""

    def test_returns_data_and_line_map_from_valid_yaml(self):
        """parse_yaml_with_lines returns (data_dict, line_map) from valid YAML."""
        source = "model: gpt-4\nprompt: hello\n"
        data, line_map = parse_yaml_with_lines(source)
        assert isinstance(data, dict)
        assert isinstance(line_map, dict)
        assert data["model"] == "gpt-4"
        assert data["prompt"] == "hello"

    def test_line_map_contains_correct_line_numbers_for_top_level_keys(self):
        """line_map contains correct 1-indexed line numbers for top-level keys."""
        source = "model: gpt-4\nprompt: hello\nthreshold: 0.9\n"
        data, line_map = parse_yaml_with_lines(source)
        # Line numbers should be 1-indexed
        assert line_map["model"][0] == 1
        assert line_map["prompt"][0] == 2
        assert line_map["threshold"][0] == 3

    def test_line_map_tracks_nested_keys(self):
        """line_map tracks nested keys with dotted path format."""
        source = (
            "model: gpt-4\n"
            "tools:\n"
            "  - name: search\n"
            "    description: search the web\n"
        )
        data, line_map = parse_yaml_with_lines(source)
        assert "tools" in line_map
        # Nested keys under list items should be tracked with dotted paths
        assert "tools.0.name" in line_map
        assert "tools.0.description" in line_map

    def test_yaml_syntax_error_raises_yaml_parse_error(self):
        """YAML syntax errors raise YAMLParseError with line/column info."""
        source = "model: gpt-4\nprompt: [invalid\n"
        with pytest.raises(YAMLParseError) as exc_info:
            parse_yaml_with_lines(source)
        err = exc_info.value
        assert err.line is not None
        assert err.column is not None
        assert err.message

    def test_empty_yaml_input(self):
        """Empty YAML input returns (None, {})."""
        data, line_map = parse_yaml_with_lines("")
        assert data is None
        assert line_map == {}

    def test_yaml_with_only_comments(self):
        """YAML with only comments returns (None, {})."""
        source = "# this is a comment\n# another comment\n"
        data, line_map = parse_yaml_with_lines(source)
        assert data is None
        assert line_map == {}

    def test_yaml_parse_error_has_filename(self):
        """YAMLParseError includes filename when provided."""
        source = "model: gpt-4\nprompt: [invalid\n"
        with pytest.raises(YAMLParseError) as exc_info:
            parse_yaml_with_lines(source, filename="test.yaml")
        assert exc_info.value.filename == "test.yaml"
