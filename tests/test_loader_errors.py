"""Tests for the rich error formatter."""

from salvo.loader.errors import ErrorFormatter
from salvo.loader.validator import ValidationErrorDetail


class TestErrorFormatterRichMode:
    """Tests for human-readable rich error formatting."""

    def test_format_error_includes_line_and_snippet(self):
        """Rich format includes line number, source snippet, and arrow."""
        error = ValidationErrorDetail(
            field="modle",
            message="Extra inputs are not permitted",
            type="extra_forbidden",
            line=1,
            col=1,
            suggestion="Did you mean 'model'?",
        )
        source_lines = ["modle: gpt-4", "prompt: hello"]
        formatter = ErrorFormatter(ci_mode=False)
        result = formatter.format_error(error, source_lines, "test.yaml")
        assert "1" in result  # line number
        assert "modle" in result  # source snippet
        assert "test.yaml" in result  # filename

    def test_format_error_includes_error_code(self):
        """Rich format includes an error code identifier like error[E001]."""
        error = ValidationErrorDetail(
            field="modle",
            message="Extra inputs are not permitted",
            type="extra_forbidden",
            line=1,
            col=1,
        )
        source_lines = ["modle: gpt-4"]
        formatter = ErrorFormatter(ci_mode=False)
        result = formatter.format_error(error, source_lines, "test.yaml")
        assert "error[E" in result

    def test_format_error_shows_suggestion_in_rich_mode(self):
        """Rich format shows 'did you mean' suggestion when present."""
        error = ValidationErrorDetail(
            field="modle",
            message="Extra inputs are not permitted",
            type="extra_forbidden",
            line=1,
            col=1,
            suggestion="Did you mean 'model'?",
        )
        source_lines = ["modle: gpt-4"]
        formatter = ErrorFormatter(ci_mode=False)
        result = formatter.format_error(error, source_lines, "test.yaml")
        assert "model" in result.lower()

    def test_format_error_handles_none_line_number(self):
        """Formatter produces useful output when line number is None."""
        error = ValidationErrorDetail(
            field="model",
            message="Field required",
            type="missing",
            line=None,
            col=None,
        )
        source_lines = ["prompt: hello"]
        formatter = ErrorFormatter(ci_mode=False)
        result = formatter.format_error(error, source_lines, "test.yaml")
        assert "model" in result
        assert "required" in result.lower() or "missing" in result.lower()


class TestErrorFormatterCIMode:
    """Tests for CI-friendly concise error formatting."""

    def test_ci_format_is_concise(self):
        """CI format produces file:line:col -- message format."""
        error = ValidationErrorDetail(
            field="modle",
            message="Extra inputs are not permitted",
            type="extra_forbidden",
            line=1,
            col=1,
            suggestion="Did you mean 'model'?",
        )
        source_lines = ["modle: gpt-4"]
        formatter = ErrorFormatter(ci_mode=True)
        result = formatter.format_error(error, source_lines, "test.yaml")
        assert "test.yaml" in result
        assert "1" in result
        assert "--" in result

    def test_ci_format_includes_suggestion(self):
        """CI format includes suggestion when present."""
        error = ValidationErrorDetail(
            field="modle",
            message="Extra inputs are not permitted",
            type="extra_forbidden",
            line=1,
            col=1,
            suggestion="Did you mean 'model'?",
        )
        source_lines = ["modle: gpt-4"]
        formatter = ErrorFormatter(ci_mode=True)
        result = formatter.format_error(error, source_lines, "test.yaml")
        assert "model" in result.lower()


class TestErrorFormatterFormatAll:
    """Tests for formatting multiple errors."""

    def test_format_all_formats_all_errors(self):
        """format_all with multiple errors formats all of them."""
        errors = [
            ValidationErrorDetail(
                field="modle",
                message="Extra inputs are not permitted",
                type="extra_forbidden",
                line=1,
                col=1,
            ),
            ValidationErrorDetail(
                field="prompt",
                message="Field required",
                type="missing",
                line=None,
                col=None,
            ),
        ]
        source = "modle: gpt-4\n"
        formatter = ErrorFormatter(ci_mode=False)
        result = formatter.format_all(errors, source, "test.yaml")
        assert "modle" in result
        assert "prompt" in result
