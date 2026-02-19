"""Judge prompt template builder from criteria.

Builds system prompts, user prompts, tool definitions, and
provider-specific tool_choice directives for judge evaluation.
"""

from __future__ import annotations


JUDGE_SYSTEM_TEMPLATE = """You are an expert evaluator assessing the quality of an AI agent's response.

Evaluate the agent's response against each of the following criteria independently. Score each criterion on a 0.0 to 1.0 scale using these anchors:

- **0.0**: Completely fails to meet the criterion
- **0.25**: Mostly fails, with only minor elements present
- **0.5**: Partially meets the criterion
- **0.75**: Mostly meets the criterion with minor gaps
- **1.0**: Fully meets the criterion

**Criteria to evaluate:**

{criteria_block}

**Instructions:**
- Evaluate each criterion independently -- do not let one criterion's score influence another.
- Provide specific reasoning for each score referencing the agent's actual output.
- Use the score_criteria tool to submit your evaluation."""


JUDGE_USER_TEMPLATE = """Please evaluate the following agent interaction against the criteria defined in your instructions.

{context_block}

Use the score_criteria tool to submit your per-criterion scores and reasoning."""


def build_criteria_block(criteria: list[dict]) -> str:
    """Format criteria list into a readable block for the system prompt.

    Args:
        criteria: List of criterion dicts with name, description, weight.

    Returns:
        Formatted string with one criterion per line.
    """
    lines = []
    for c in criteria:
        lines.append(f"- **{c['name']}** (weight: {c['weight']}): {c['description']}")
    return "\n".join(lines)


def build_judge_prompt(criteria: list[dict]) -> str:
    """Build the complete judge system prompt from criteria.

    Args:
        criteria: List of criterion dicts with name, description, weight.

    Returns:
        Fully rendered system prompt string.
    """
    criteria_block = build_criteria_block(criteria)
    return JUDGE_SYSTEM_TEMPLATE.format(criteria_block=criteria_block)


def build_scoring_tool(criteria: list[dict]) -> dict:
    """Build the tool definition dict for structured score extraction.

    Creates a tool named 'score_criteria' with per-criterion nested
    objects containing score (number) and reasoning (string).

    Args:
        criteria: List of criterion dicts with name, description, weight.

    Returns:
        Tool definition dict compatible with BaseAdapter.send_turn() tools param.
    """
    properties = {}
    required = []

    for c in criteria:
        name = c["name"]
        required.append(name)
        properties[name] = {
            "type": "object",
            "description": f"Evaluation for '{name}': {c['description']}",
            "properties": {
                "score": {
                    "type": "number",
                    "description": f"Score for {name} on 0.0-1.0 scale",
                },
                "reasoning": {
                    "type": "string",
                    "description": f"Reasoning for the {name} score",
                },
            },
            "required": ["score", "reasoning"],
        }

    return {
        "name": "score_criteria",
        "description": "Submit per-criterion evaluation scores and reasoning.",
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }


def format_tool_choice(provider_name: str, tool_name: str) -> dict:
    """Return provider-specific tool_choice dict.

    Args:
        provider_name: Provider identifier (e.g., "openai", "anthropic").
        tool_name: Name of the tool to force.

    Returns:
        Dict with tool_choice key, or empty dict for unknown providers.
    """
    lower = provider_name.lower()

    if "openai" in lower:
        return {
            "tool_choice": {
                "type": "function",
                "function": {"name": tool_name},
            }
        }

    if "anthropic" in lower:
        return {
            "tool_choice": {"type": "tool", "name": tool_name}
        }

    return {}
