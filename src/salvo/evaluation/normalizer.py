"""Assertion normalizer -- converts shorthand forms to canonical.

Operator-key style: {path: "...", contains: "value"}
Canonical form: {type: "jmespath", expression: "...", operator: "contains", value: "value"}
"""

from __future__ import annotations

OPERATOR_KEYS = {"eq", "ne", "gt", "gte", "lt", "lte", "contains", "regex"}


def normalize_assertion(raw: dict) -> dict:
    """Convert an operator-key-style assertion to canonical form.

    If the dict already has a ``type`` key it is returned unchanged
    (already canonical).  Otherwise, exactly one operator key from
    OPERATOR_KEYS must be present; it is extracted and used to build a
    canonical jmespath assertion dict.

    Raises:
        ValueError: If multiple operator keys or no recognizable format.
    """
    if "type" in raw:
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
