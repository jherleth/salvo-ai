"""Assertion normalizer -- converts shorthand forms to canonical.

Operator-key style: {path: "...", contains: "value"}
Canonical form: {type: "jmespath", expression: "...", operator: "contains", value: "value"}

Sugar types (expanded to jmespath):
- tool_called: {type: "tool_called", tool: "name"} -> jmespath exists check
- output_contains: {type: "output_contains", value: "text"} -> jmespath contains check
"""

from __future__ import annotations

OPERATOR_KEYS = {"eq", "ne", "gt", "gte", "lt", "lte", "contains", "regex"}


def _expand_tool_called(raw: dict) -> dict:
    """Expand tool_called sugar to a jmespath exists assertion."""
    tool = raw["tool"]
    return {
        "type": "jmespath",
        "expression": f"tool_calls[?name=='{tool}'] | [0]",
        "operator": "exists",
        "value": None,
        "weight": raw.get("weight", 1.0),
        "required": raw.get("required", False),
    }


def _expand_output_contains(raw: dict) -> dict:
    """Expand output_contains sugar to a jmespath contains assertion."""
    return {
        "type": "jmespath",
        "expression": "response.content",
        "operator": "contains",
        "value": raw["value"],
        "weight": raw.get("weight", 1.0),
        "required": raw.get("required", False),
    }


_SUGAR_TYPES = {
    "tool_called": _expand_tool_called,
    "output_contains": _expand_output_contains,
}


def normalize_assertion(raw: dict) -> dict:
    """Convert shorthand or sugar-type assertions to canonical form.

    Sugar types (tool_called, output_contains) are expanded to jmespath
    assertions.  Operator-key-style dicts are converted to canonical
    jmespath form.  Already-canonical dicts are returned unchanged.

    Raises:
        ValueError: If multiple operator keys or no recognizable format.
    """
    if "type" in raw:
        expander = _SUGAR_TYPES.get(raw["type"])
        if expander is not None:
            return expander(raw)
        return raw

    found_ops = OPERATOR_KEYS & raw.keys()

    if len(found_ops) > 1:
        raise ValueError(
            f"Assertion has multiple operator keys: {sorted(found_ops)}. "
            "Use exactly one operator per assertion."
        )

    if len(found_ops) == 0:
        raise ValueError(
            f"Assertion has no 'type' and no operator key from "
            f"{sorted(OPERATOR_KEYS)}. Cannot determine assertion type."
        )

    operator = found_ops.pop()
    value = raw[operator]
    expression = raw.get("path", "response.content")
    weight = raw.get("weight", 1.0)
    required = raw.get("required", False)

    return {
        "type": "jmespath",
        "expression": expression,
        "operator": operator,
        "value": value,
        "weight": weight,
        "required": required,
    }


def normalize_assertions(raw_list: list[dict]) -> list[dict]:
    """Normalize a list of assertion dicts."""
    return [normalize_assertion(raw) for raw in raw_list]
