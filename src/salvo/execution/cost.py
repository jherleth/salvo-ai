"""Cost estimation from token usage and model pricing.

Provides a static pricing table for supported models and a function
to estimate the USD cost of a single adapter turn based on token counts.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPricing:
    """Pricing per million tokens for a single model."""

    input_per_million: float
    output_per_million: float


# Static pricing table for supported models.
# Prices are in USD per million tokens.
PRICING_TABLE: dict[str, ModelPricing] = {
    # OpenAI models
    "gpt-4o": ModelPricing(input_per_million=2.50, output_per_million=10.00),
    "gpt-4o-mini": ModelPricing(input_per_million=0.15, output_per_million=0.60),
    # Anthropic models
    "claude-sonnet-4-5": ModelPricing(input_per_million=3.00, output_per_million=15.00),
    "claude-haiku-4-5": ModelPricing(input_per_million=1.00, output_per_million=5.00),
}

# Aliases for dated model versions that share pricing with their base model.
MODEL_ALIASES: dict[str, str] = {
    "claude-sonnet-4-5-20250929": "claude-sonnet-4-5",
    "claude-haiku-4-5-20241022": "claude-haiku-4-5",
}


def estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float | None:
    """Estimate the USD cost of a single turn based on token usage.

    Looks up the model in the pricing table (resolving aliases first),
    then calculates: (input_tokens / 1M * input_price) + (output_tokens / 1M * output_price).

    Args:
        model: The model name (e.g., "gpt-4o", "claude-sonnet-4-5").
        input_tokens: Number of input/prompt tokens.
        output_tokens: Number of output/completion tokens.

    Returns:
        Estimated cost in USD rounded to 6 decimal places,
        or None if the model is not in the pricing table.
    """
    # Resolve aliases first
    resolved = MODEL_ALIASES.get(model, model)

    pricing = PRICING_TABLE.get(resolved)
    if pricing is None:
        return None

    cost = (
        (input_tokens / 1_000_000) * pricing.input_per_million
        + (output_tokens / 1_000_000) * pricing.output_per_million
    )

    return round(cost, 6)
