"""YAML parser with line tracking for rich error reporting.

Provides a custom PyYAML loader that captures source line numbers
for every key in the parsed document, enabling error messages that
point to the exact location in the user's YAML file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class YAMLParseError(Exception):
    """Raised when YAML syntax cannot be parsed.

    Attributes:
        line: 1-indexed line number where the error occurred.
        column: 1-indexed column number where the error occurred.
        message: Human-readable description of the syntax error.
        filename: Name of the file being parsed, or '<string>'.
    """

    def __init__(
        self,
        message: str,
        line: int | None = None,
        column: int | None = None,
        filename: str = "<string>",
    ) -> None:
        self.message = message
        self.line = line
        self.column = column
        self.filename = filename
        super().__init__(message)


class LineTrackingLoader(yaml.SafeLoader):
    """YAML SafeLoader subclass that captures line numbers for all keys.

    Builds a hierarchical line_map dict mapping dotted key paths to
    (line, column) tuples with 1-indexed positions.
    """

    def __init__(self, stream: str, filename: str = "<string>") -> None:
        super().__init__(stream)
        self.line_map: dict[str, tuple[int, int]] = {}
        self._filename = filename
        self._base_dir: Path | None = None
        self._prefix_stack: list[str] = []

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[str, Any]:
        """Override to capture line numbers for every key in the mapping."""
        self.flatten_mapping(node)
        pairs = []
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)

            if isinstance(key, str) and key_node.start_mark is not None:
                line = key_node.start_mark.line + 1  # 1-indexed
                col = key_node.start_mark.column + 1  # 1-indexed
                if self._prefix_stack:
                    full_key = ".".join(self._prefix_stack) + "." + key
                else:
                    full_key = key
                self.line_map[full_key] = (line, col)

            # Push key onto prefix stack before constructing the value
            # so nested mappings/sequences get the correct path prefix
            if isinstance(key, str) and isinstance(
                value_node, (yaml.MappingNode, yaml.SequenceNode)
            ):
                self._prefix_stack.append(key)
                value = self.construct_object(value_node, deep=deep)
                self._prefix_stack.pop()
            else:
                value = self.construct_object(value_node, deep=deep)

            pairs.append((key, value))

        return dict(pairs)

    def construct_sequence(self, node: yaml.SequenceNode, deep: bool = False) -> list[Any]:
        """Override to track list item indices in the key path."""
        result = []
        for idx, child_node in enumerate(node.value):
            if isinstance(child_node, yaml.MappingNode):
                # Push index prefix for nested mapping keys
                if self._prefix_stack:
                    self._prefix_stack.append(str(idx))
                else:
                    self._prefix_stack.append(str(idx))
                item = self.construct_mapping(child_node, deep=deep)
                self._prefix_stack.pop()
                result.append(item)
            else:
                result.append(self.construct_object(child_node, deep=deep))
        return result

    def construct_yaml_map(self, node: yaml.MappingNode) -> Any:
        """Top-level mapping constructor that delegates to construct_mapping."""
        data = self.construct_mapping(node, deep=True)
        yield data

    def construct_yaml_seq(self, node: yaml.SequenceNode) -> Any:
        """Top-level sequence constructor that delegates to construct_sequence."""
        data = self.construct_sequence(node, deep=True)
        yield data


# Override the default constructors for mapping and sequence
LineTrackingLoader.add_constructor(
    "tag:yaml.org,2002:map",
    LineTrackingLoader.construct_yaml_map,
)

LineTrackingLoader.add_constructor(
    "tag:yaml.org,2002:seq",
    LineTrackingLoader.construct_yaml_seq,
)


def _include_constructor(loader: LineTrackingLoader, node: yaml.ScalarNode) -> Any:
    """Handle !include tags by loading the referenced YAML file.

    The path is resolved relative to the base directory (the directory
    of the scenario file being parsed).
    """
    relative_path = loader.construct_scalar(node)
    if loader._base_dir is not None:
        filepath = loader._base_dir / relative_path
    else:
        filepath = Path(relative_path)

    with open(filepath) as f:
        return yaml.safe_load(f)


LineTrackingLoader.add_constructor("!include", _include_constructor)


def parse_yaml_with_lines(
    source: str,
    filename: str = "<string>",
    base_dir: Path | None = None,
) -> tuple[dict | None, dict[str, tuple[int, int]]]:
    """Parse a YAML string and return (data, line_map).

    Args:
        source: YAML content as a string.
        filename: Filename for error messages.
        base_dir: Base directory for resolving !include paths.

    Returns:
        A tuple of (parsed_data, line_map) where line_map maps
        dotted key paths to (line, column) tuples (1-indexed).
        Returns (None, {}) for empty or comment-only YAML.

    Raises:
        YAMLParseError: If the YAML contains syntax errors.
    """
    try:
        loader = LineTrackingLoader(source, filename=filename)
        if base_dir is not None:
            loader._base_dir = base_dir
        try:
            data = loader.get_single_data()
        finally:
            loader.dispose()
    except yaml.YAMLError as e:
        line = None
        column = None
        if hasattr(e, "problem_mark") and e.problem_mark is not None:
            line = e.problem_mark.line + 1
            column = e.problem_mark.column + 1
        raise YAMLParseError(
            message=str(e),
            line=line,
            column=column,
            filename=filename,
        ) from e

    if data is None or not isinstance(data, dict):
        return None, {}

    return data, loader.line_map


def parse_yaml_file(filepath: Path) -> tuple[dict | None, dict[str, tuple[int, int]]]:
    """Parse a YAML file and return (data, line_map).

    Args:
        filepath: Path to the YAML file.

    Returns:
        A tuple of (parsed_data, line_map).

    Raises:
        YAMLParseError: If the file contains YAML syntax errors.
        FileNotFoundError: If the file does not exist.
    """
    content = filepath.read_text(encoding="utf-8")
    return parse_yaml_with_lines(
        content,
        filename=str(filepath),
        base_dir=filepath.parent,
    )
