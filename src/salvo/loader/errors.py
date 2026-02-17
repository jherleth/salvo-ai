"""Error formatter with dual-mode output (rich human and CI concise).

Produces Rust/Elm-style annotated error messages in human mode and
concise file:line:col -- message format in CI mode.
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from salvo.loader.validator import ValidationErrorDetail


# Map Pydantic error types to error codes
ERROR_CODES: dict[str, str] = {
    "extra_forbidden": "E001",
    "missing": "E002",
    "value_error": "E003",
    "type_error": "E004",
    "string_type": "E004",
    "int_type": "E004",
    "float_type": "E004",
    "float_parsing": "E004",
    "int_parsing": "E004",
    "bool_type": "E004",
    "literal_error": "E005",
    "yaml_syntax_error": "E006",
    "empty_file": "E007",
    "empty_input": "E007",
    "less_than_equal": "E003",
    "greater_than_equal": "E003",
}

# Human-readable descriptions for error codes
ERROR_DESCRIPTIONS: dict[str, str] = {
    "E001": "unknown field",
    "E002": "required field missing",
    "E003": "invalid value",
    "E004": "type mismatch",
    "E005": "invalid literal",
    "E006": "YAML syntax error",
    "E007": "empty input",
}


class ErrorFormatter:
    """Formats validation errors for human or CI consumption.

    In human mode, produces Rust/Elm-style annotated errors with
    line numbers, source snippets, and arrows pointing to problems.
    In CI mode, produces concise file:line:col -- message format.

    Args:
        ci_mode: If True, use CI-friendly concise output. If None,
            auto-detect from the CI environment variable.
    """

    def __init__(self, ci_mode: bool | None = None) -> None:
        if ci_mode is None:
            self.ci_mode = os.environ.get("CI", "").lower() in ("true", "1", "yes")
        else:
            self.ci_mode = ci_mode

    def _get_error_code(self, error_type: str) -> str:
        """Get the error code for a Pydantic error type."""
        # Check for exact match first
        if error_type in ERROR_CODES:
            return ERROR_CODES[error_type]
        # Check for partial matches (e.g. 'float_parsing' matches 'float')
        for key, code in ERROR_CODES.items():
            if key in error_type:
                return code
        return "E999"

    def _get_error_description(self, error_code: str) -> str:
        """Get the human-readable description for an error code."""
        return ERROR_DESCRIPTIONS.get(error_code, "validation error")

    def format_error(
        self,
        error: ValidationErrorDetail,
        source_lines: list[str],
        filename: str,
    ) -> str:
        """Format a single error for display.

        Args:
            error: The validation error detail.
            source_lines: Lines of the original YAML source.
            filename: Filename being validated.

        Returns:
            Formatted error string.
        """
        if self.ci_mode:
            return self._format_ci(error, filename)
        return self._format_rich(error, source_lines, filename)

    def _format_ci(self, error: ValidationErrorDetail, filename: str) -> str:
        """Format error in CI-friendly concise format.

        Format: filename:line:col -- field: message [suggestion]
        """
        line = error.line if error.line is not None else 0
        col = error.col if error.col is not None else 0
        suggestion_suffix = f" ({error.suggestion})" if error.suggestion else ""
        return f"{filename}:{line}:{col} -- {error.field}: {error.message}{suggestion_suffix}"

    def _format_rich(
        self,
        error: ValidationErrorDetail,
        source_lines: list[str],
        filename: str,
    ) -> str:
        """Format error in Rust/Elm-style rich format.

        Produces output like:
            error[E001]: unknown field
              --> test.yaml:1:1
               |
             1 | modle: gpt-4
               | ^^^^^ Extra inputs are not permitted
               |
               = help: Did you mean 'model'?
        """
        error_code = self._get_error_code(error.type)
        description = self._get_error_description(error_code)

        lines = []
        lines.append(f"error[{error_code}]: {description}")

        if error.line is not None:
            col = error.col if error.col is not None else 1
            lines.append(f"  --> {filename}:{error.line}:{col}")
            lines.append("   |")

            # Show the source line if available
            line_idx = error.line - 1  # 0-indexed
            if 0 <= line_idx < len(source_lines):
                src_line = source_lines[line_idx].rstrip()
                line_num_str = str(error.line)
                padding = " " * len(line_num_str)
                lines.append(f" {line_num_str} | {src_line}")

                # Add arrow/underline under the field name
                field_name = error.field.split(".")[-1]  # last segment
                # Find the field in the source line
                field_start = src_line.find(field_name)
                if field_start >= 0:
                    arrow_padding = " " * field_start
                    arrows = "^" * len(field_name)
                    lines.append(f" {padding} | {arrow_padding}{arrows} {error.message}")
                else:
                    lines.append(f" {padding} | {error.message}")
            else:
                lines.append(f"   | {error.message}")

            lines.append(f"   |")
        else:
            # No line number available
            lines.append(f"  --> {filename}")
            lines.append(f"   |")
            lines.append(f"   | {error.field}: {error.message}")
            lines.append(f"   |")

        if error.suggestion:
            lines.append(f"   = help: {error.suggestion}")

        return "\n".join(lines)

    def format_all(
        self,
        errors: list[ValidationErrorDetail],
        source: str,
        filename: str,
    ) -> str:
        """Format all errors for display.

        Args:
            errors: List of validation error details.
            source: Original YAML source string.
            filename: Filename being validated.

        Returns:
            All formatted errors joined with blank line separators.
        """
        source_lines = source.splitlines()
        formatted = []
        for error in errors:
            formatted.append(self.format_error(error, source_lines, filename))
        return "\n\n".join(formatted)

    def print_errors(
        self,
        errors: list[ValidationErrorDetail],
        source: str,
        filename: str,
    ) -> None:
        """Print formatted errors to stderr.

        Args:
            errors: List of validation error details.
            source: Original YAML source string.
            filename: Filename being validated.
        """
        output = self.format_all(errors, source, filename)
        print(output, file=sys.stderr)

    def print_success(self, filename: str) -> None:
        """Print a success message for a valid file.

        Args:
            filename: Filename that passed validation.
        """
        print(f"  {filename} ... valid")
