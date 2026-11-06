"""
pytb_hook - reason-first, trimmed Python tracebacks, for every Python process.

    pip install <path or git URL of pytb-hook>     # the hook is now on for that interpreter

Library use:

    from pytb_hook import TracebackFormatter, format_traceback, install, uninstall
    TracebackFormatter(project_root=".", stop_at_imported=True).format(stderr_text)

Names are loaded on first use, so `import pytb_hook` at start-up stays cheap.
"""
__version__ = "0.1.0"

_EXPORTS = {
    "TracebackFormatter": "formatter",
    "format_traceback": "formatter",
    "install": "hook",
    "uninstall": "hook",
    "configure": "hook",
    "is_active": "hook",
}

__all__ = list(_EXPORTS) + ["__version__"]


def __getattr__(name):
    """
    Inputs: name (str) - attribute looked up on the package.
    Output: the exported object, imported from its submodule on first use.
    Raises AttributeError for unknown names.
    """
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module 'pytb_hook' has no attribute {name!r}")
    import importlib
    value = getattr(importlib.import_module(f".{module}", __name__), name)
    globals()[name] = value
    return value


def __dir__():
    """Inputs: none. Output: list[str] - the exported names."""
    return sorted(__all__)
