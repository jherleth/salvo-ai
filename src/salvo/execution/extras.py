"""Extras validation with security guardrails.

Validates the extras dict passed to adapter configs, blocking
secret-like keys and enforcing size limits to prevent accidental
credential leakage and oversized payloads.
"""

from __future__ import annotations

import json

# Keys that are blocked from extras to prevent accidental credential leakage.
# Matching is case-insensitive.
BLOCKED_KEYS: frozenset[str] = frozenset({
    "api_key",
    "api_secret",
    "secret",
    "token",
    "password",
    "authorization",
    "secret_key",
    "access_token",
    "refresh_token",
})

# Maximum number of keys allowed in extras.
MAX_EXTRAS_KEYS: int = 10

# Maximum serialized size of extras in bytes.
MAX_EXTRAS_SIZE: int = 4096


def validate_extras(extras: dict) -> dict:
    """Validate an extras dict for security and size constraints.

    Checks:
    1. No keys match the blocked keys list (case-insensitive).
    2. Number of keys does not exceed MAX_EXTRAS_KEYS.
    3. JSON-serialized size does not exceed MAX_EXTRAS_SIZE bytes.

    Args:
        extras: The extras dict to validate.

    Returns:
        The validated extras dict (unchanged if valid).

    Raises:
        ValueError: If any validation check fails, with a descriptive message.
    """
    # Check for blocked keys (case-insensitive)
    for key in extras:
        if key.lower() in BLOCKED_KEYS:
            raise ValueError(
                f"Extras key '{key}' is blocked because it looks like a secret or credential. "
                f"Secrets should be configured via environment variables, not passed in extras."
            )

    # Check key count
    if len(extras) > MAX_EXTRAS_KEYS:
        raise ValueError(
            f"Extras has {len(extras)} keys, exceeding the limit of {MAX_EXTRAS_KEYS}. "
            f"Consider reducing the number of extra parameters."
        )

    # Check serialized size
    serialized = json.dumps(extras)
    size = len(serialized.encode("utf-8"))
    if size > MAX_EXTRAS_SIZE:
        raise ValueError(
            f"Extras serialized size is {size} bytes, exceeding the limit of {MAX_EXTRAS_SIZE} bytes. "
            f"Consider reducing the size of extra parameter values."
        )

    return extras
