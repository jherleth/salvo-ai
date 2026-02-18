"""Per-assertion result formatting with severity ordering and score breakdowns.

Minimal on pass, detailed on fail, full detail on demand.
"""

from __future__ import annotations

from salvo.models.result import EvalResult


def _describe_assertion(result: EvalResult) -> str:
    """Produce a short description from the assertion type and details.

    Parses the details string to extract key information for display.
    """
    details = result.details
    atype = result.assertion_type

    if atype == "jmespath":
        # details format: path='...' operator=... expected=... actual=...
        parts = {}
        for segment in details.split(" "):
            if "=" in segment:
                key, _, val = segment.partition("=")
                parts[key] = val
        path = parts.get("path", "?").strip("'\"")
        operator = parts.get("operator", "?")
        expected = parts.get("expected", "?").strip("'\"")
        return f"{path} {operator} {expected}"

    if atype == "tool_sequence":
        # details usually contains mode and sequence info
        return f"tool_sequence: {details}"

    if atype == "cost_limit":
        # details format: Cost $X.XXXX vs limit $X.XXXX
        return f"cost_limit: {details}"

    if atype == "latency_limit":
        # details format: Latency X.XXXs vs limit X.XXXs
        return f"latency_limit: {details}"

    return f"{atype}: {details}"


def format_eval_results(
    eval_results: list[EvalResult],
    score: float,
    threshold: float,
    passed: bool,
    hard_fail: bool,
    verbose: bool = False,
) -> str:
    """Format evaluation results for CLI output.

    On pass (not verbose): single score line.
    On pass (verbose): score line + all assertions + breakdown.
    On fail: score line + severity-ordered assertions + breakdown.

    Args:
        eval_results: Individual assertion evaluation results.
        score: Computed weighted score (0.0 to 1.0).
        threshold: Pass/fail threshold.
        passed: Whether the overall evaluation passed.
        hard_fail: Whether a required assertion failed.
        verbose: Show full detail even on pass.

    Returns:
        Multi-line formatted string (plain text, no Rich markup).
    """
    lines: list[str] = []

    # Score header line
    if passed:
        lines.append(f"Score: {score:.2f} (>= {threshold:.2f})  PASS")
    elif hard_fail:
        lines.append(f"Score: {score:.2f}  HARD FAIL (required assertion failed)")
    else:
        lines.append(f"Score: {score:.2f} (< {threshold:.2f})  FAILED")

    # Determine if we show detail
    show_detail = not passed or verbose

    if not show_detail or not eval_results:
        return "\n".join(lines)

    lines.append("")

    # Sort by severity: hard failures first, then soft failures, then passes
    hard_failures = [r for r in eval_results if r.required and not r.passed]
    soft_failures = [r for r in eval_results if not r.required and not r.passed]
    passes = [r for r in eval_results if r.passed]

    sorted_results = hard_failures + soft_failures + passes

    # Per-assertion details
    for result in sorted_results:
        desc = _describe_assertion(result)
        if result.required and not result.passed:
            lines.append(f"  HARD FAIL  [required] {desc}")
            # Show expected/actual from details
            _append_details(lines, result)
        elif not result.passed:
            lines.append(f"  FAILED     {desc}")
            _append_details(lines, result)
        else:
            lines.append(f"  PASS       {desc}")

    # Score breakdown (always shown on fail, shown on verbose pass)
    lines.append("")
    lines.append("  Score breakdown:")
    for result in sorted_results:
        desc = _describe_assertion(result)
        product = result.score * result.weight
        req_tag = "  [REQUIRED]" if result.required else ""
        lines.append(
            f"    {desc}    {result.score:.1f} * {result.weight:.1f} = {product:.2f}{req_tag}"
        )

    total_weight = sum(r.weight for r in eval_results)
    weighted_sum = sum(r.score * r.weight for r in eval_results)
    lines.append("    " + "\u2500" * 30)
    lines.append(
        f"    Total: {weighted_sum:.2f} / {total_weight:.2f} = {score:.2f}"
    )

    return "\n".join(lines)


def _append_details(lines: list[str], result: EvalResult) -> None:
    """Append expected/actual detail lines for a failed assertion."""
    details = result.details
    if not details:
        return

    # For jmespath, parse expected/actual
    if result.assertion_type == "jmespath":
        parts = {}
        # Parse key=value pairs from details string
        import shlex
        try:
            tokens = shlex.split(details)
        except ValueError:
            tokens = details.split()
        for token in tokens:
            if "=" in token:
                key, _, val = token.partition("=")
                parts[key] = val
        if "expected" in parts:
            lines.append(f"             Expected: {parts['expected']}")
        if "actual" in parts:
            lines.append(f"             Actual: {parts['actual']}")
        if "path" in parts:
            lines.append(f"             Path: {parts['path']}")
    else:
        # For other types, just show the details string
        lines.append(f"             {details}")
