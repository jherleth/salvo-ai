"""Adapter registry for resolving adapter names to classes.

Supports both builtin adapter names (e.g., "openai", "anthropic")
and custom dotted-path imports (e.g., "my.module.MyAdapter").
"""

from __future__ import annotations

import importlib

from salvo.adapters.base import BaseAdapter

# Mapping of builtin adapter short names to their fully-qualified class paths.
# These adapters are lazily imported -- the provider SDK must be installed.
BUILTIN_ADAPTERS: dict[str, str] = {
    "openai": "salvo.adapters.openai_adapter.OpenAIAdapter",
    "anthropic": "salvo.adapters.anthropic_adapter.AnthropicAdapter",
}

# Maps builtin names to their pip install extras for helpful error messages.
_INSTALL_HINTS: dict[str, str] = {
    "openai": "pip install salvo-ai[openai]",
    "anthropic": "pip install salvo-ai[anthropic]",
}


def get_adapter(name: str) -> BaseAdapter:
    """Resolve an adapter by name or dotted path and return an instance.

    For builtin names ("openai", "anthropic"), resolves to the registered
    fully-qualified class path and lazily imports it.

    For dotted paths ("my.module.MyAdapter"), imports the module and
    retrieves the class directly.

    Args:
        name: A builtin adapter name or a fully-qualified dotted path
              to an adapter class.

    Returns:
        An instance of the resolved adapter class.

    Raises:
        ValueError: If the name is not a builtin and has no dots (unknown).
        ImportError: If the module cannot be imported (e.g., missing SDK).
        TypeError: If the resolved class is not a subclass of BaseAdapter.
    """
    # Resolve builtin name to dotted path
    if name in BUILTIN_ADAPTERS:
        dotted_path = BUILTIN_ADAPTERS[name]
    elif "." in name:
        dotted_path = name
    else:
        available = ", ".join(sorted(BUILTIN_ADAPTERS.keys()))
        raise ValueError(
            f"Unknown adapter '{name}'. "
            f"Available builtin adapters: {available}. "
            f"For custom adapters, provide the full dotted path "
            f"(e.g., 'my.module.MyAdapter')."
        )

    # Split dotted path into module path and class name
    module_path, _, class_name = dotted_path.rpartition(".")
    if not module_path or not class_name:
        raise ValueError(
            f"Invalid adapter path '{dotted_path}'. "
            f"Expected format: 'module.path.ClassName'."
        )

    # Import the module
    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        # Provide helpful install hint for builtin adapters
        if name in _INSTALL_HINTS:
            raise ImportError(
                f"Adapter '{name}' requires the {name} package. "
                f"Install it: {_INSTALL_HINTS[name]}"
            ) from exc
        raise

    # Get the class from the module
    try:
        cls = getattr(module, class_name)
    except AttributeError:
        raise ImportError(
            f"Module '{module_path}' has no attribute '{class_name}'."
        ) from None

    # Validate it's a BaseAdapter subclass
    if not isinstance(cls, type) or not issubclass(cls, BaseAdapter):
        raise TypeError(
            f"'{dotted_path}' is not a subclass of BaseAdapter. "
            f"Custom adapters must inherit from salvo.adapters.base.BaseAdapter."
        )

    return cls()
