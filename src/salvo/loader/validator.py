"""Scenario validation pipeline combining YAML parsing with Pydantic validation.

Two-stage validation: first parse YAML with line tracking, then validate
against the Scenario Pydantic model. Errors from both stages are enriched
with source positions and collected for batch reporting.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from salvo.loader.yaml_parser import (
    YAMLParseError,
    parse_yaml_file,
    parse_yaml_with_lines,
)
from salvo.models.scenario import Scenario


# All valid top-level fields on the Scenario model, used for typo suggestions
VALID_SCENARIO_FIELDS: list[str] = list(Scenario.model_fields.keys())


@dataclass
class ValidationErrorDetail:
    """A single validation error with source position and context.

    Attributes:
        field: The field name or dotted path that caused the error.
        message: Human-readable error description.
        type: Pydantic error type string (e.g. 'missing', 'extra_forbidden').
        line: 1-indexed line number in the source YAML, or None if unknown.
        col: 1-indexed column number in the source YAML, or None if unknown.
        suggestion: 'Did you mean X?' suggestion for typos, or None.
        input_value: The invalid input value, if available.
    """

    field: str
    message: str
    type: str
    line: int | None = None
    col: int | None = None
    suggestion: str | None = None
    input_value: Any = field(default=None)


def _loc_to_field_path(loc: tuple[str | int, ...]) -> str:
    """Convert a Pydantic error loc tuple to a dotted field path."""
    return ".".join(str(part) for part in loc)


def _find_line_for_field(
    field_path: str,
    line_map: dict[str, tuple[int, int]],
) -> tuple[int | None, int | None]:
    """Look up the line number for a field path in the line map.

    Tries exact match first, then progressively shorter prefixes.
    """
    # Exact match
    if field_path in line_map:
        return line_map[field_path]

    # Try progressively shorter prefixes
    parts = field_path.split(".")
    while parts:
        prefix = ".".join(parts)
        if prefix in line_map:
            return line_map[prefix]
        parts.pop()

    return None, None


def _get_suggestion(field_name: str) -> str | None:
    """Get a 'did you mean?' suggestion for a mistyped field name."""
    matches = difflib.get_close_matches(
        field_name, VALID_SCENARIO_FIELDS, n=1, cutoff=0.6
    )
    if matches:
        return f"Did you mean '{matches[0]}'?"
    return None


def validate_scenario(
    raw_data: dict[str, Any],
    line_map: dict[str, tuple[int, int]],
    source: str,
    filename: str = "<string>",
) -> tuple[Scenario | None, list[ValidationErrorDetail]]:
    """Validate parsed YAML data against the Scenario model.

    Args:
        raw_data: Parsed YAML dictionary.
        line_map: Mapping of dotted key paths to (line, col) positions.
        source: Original YAML source string (for error context).
        filename: Filename for error messages.

    Returns:
        Tuple of (Scenario, []) on success, or (None, errors) on failure.
    """
    try:
        scenario = Scenario.model_validate(raw_data)
        return scenario, []
    except ValidationError as e:
        errors: list[ValidationErrorDetail] = []
        for err in e.errors():
            loc = err.get("loc", ())
            field_path = _loc_to_field_path(loc)
            error_type = err.get("type", "unknown")
            message = err.get("msg", "Validation error")
            input_value = err.get("input")

            # Look up the field name for line number resolution
            # For top-level fields, use the first element of loc
            line, col = _find_line_for_field(field_path, line_map)

            # Generate suggestion for unknown/extra fields
            suggestion = None
            if "extra" in error_type.lower() or "forbidden" in error_type.lower():
                top_field = str(loc[0]) if loc else field_path
                suggestion = _get_suggestion(top_field)

            errors.append(
                ValidationErrorDetail(
                    field=field_path,
                    message=message,
                    type=error_type,
                    line=line,
                    col=col,
                    suggestion=suggestion,
                    input_value=input_value,
                )
            )

        return None, errors


def validate_scenario_file(
    filepath: Path,
) -> tuple[Scenario | None, list[ValidationErrorDetail]]:
    """Validate a scenario YAML file.

    Reads the file, parses YAML with line tracking, and validates
    against the Scenario model. Returns all errors at once.

    Args:
        filepath: Path to the YAML scenario file.

    Returns:
        Tuple of (Scenario, []) on success, or (None, errors) on failure.
    """
    try:
        raw_data, line_map = parse_yaml_file(filepath)
    except YAMLParseError as e:
        return None, [
            ValidationErrorDetail(
                field="<yaml>",
                message=e.message,
                type="yaml_syntax_error",
                line=e.line,
                col=e.column,
            )
        ]

    if raw_data is None:
        return None, [
            ValidationErrorDetail(
                field="<yaml>",
                message="File is empty or contains only comments",
                type="empty_file",
            )
        ]

    source = filepath.read_text(encoding="utf-8")
    return validate_scenario(raw_data, line_map, source, filename=str(filepath))


def validate_scenario_string(
    source: str,
    filename: str = "<string>",
) -> tuple[Scenario | None, list[ValidationErrorDetail]]:
    """Validate a scenario from a YAML string.

    Parses YAML with line tracking and validates against the Scenario model.

    Args:
        source: YAML content as a string.
        filename: Filename for error messages.

    Returns:
        Tuple of (Scenario, []) on success, or (None, errors) on failure.
    """
    try:
        raw_data, line_map = parse_yaml_with_lines(source, filename=filename)
    except YAMLParseError as e:
        return None, [
            ValidationErrorDetail(
                field="<yaml>",
                message=e.message,
                type="yaml_syntax_error",
                line=e.line,
                col=e.column,
            )
        ]

    if raw_data is None:
        return None, [
            ValidationErrorDetail(
                field="<yaml>",
                message="Input is empty or contains only comments",
                type="empty_input",
            )
        ]

    return validate_scenario(raw_data, line_map, source, filename=filename)
