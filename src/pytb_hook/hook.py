"""
The process-wide hook: makes every traceback Python prints use TracebackFormatter.

Covered once installed:
  - uncaught exceptions          sys.excepthook
  - uncaught thread exceptions   threading.excepthook
  - the traceback module         print_exception / format_exception, and through
                                 them print_exc, format_exc, print_last, logging's
                                 exc_info / logger.exception, asyncio's handler

This module imports only sys and os at load time; traceback, threading and the
formatter are imported when they are first needed, so the start-up hook
(_autoload) stays cheap.

Settings (environment, read by settings_from_env()):
  PYTB_HOOK=0                     turn the hook off (also: off / false / no)
  PYTB_HOOK_STOP_AT_IMPORTED=1    cut tracebacks at the first non-project frame
  PYTB_HOOK_PROJECT_ROOT=<dir>    project root for that cut (default: cwd)
  PYTB_HOOK_EXCLUDE=<dir>:<dir>   folders never counted as project (os.pathsep-separated)
"""
import os
import sys

ENV_SWITCH = "PYTB_HOOK"
LEGACY_SWITCH = "PY_TRACEBACK_HELPER"
_OFF = ("0", "off", "false", "no")

_ORIGINAL: dict = {}        # "print_exception" / "format_exception" / "excepthook" /
                            # "thread_excepthook" -> what was there before
_STATE: dict = {"formatter": None, "settings": {}, "active": False}


# ---- settings ----------------------------------------------------------------

def disabled_by_env() -> bool:
    """Inputs: none. Output: bool - PYTB_HOOK (or legacy PY_TRACEBACK_HELPER) turns the hook off."""
    for name in (ENV_SWITCH, LEGACY_SWITCH):
        if os.environ.get(name, "").strip().lower() in _OFF:
            return True
    return False


def settings_from_env() -> dict:
    """
    Inputs: none.
    Output: dict - {"project_root", "stop_at_imported", "exclude_paths"} read
    from the PYTB_HOOK_* variables (None / False / [] when unset).
    """
    exclude = os.environ.get("PYTB_HOOK_EXCLUDE", "")
    return {
        "project_root": os.environ.get("PYTB_HOOK_PROJECT_ROOT") or None,
        "stop_at_imported": os.environ.get("PYTB_HOOK_STOP_AT_IMPORTED", "").strip().lower()
                            in ("1", "on", "true", "yes"),
        "exclude_paths": [p for p in exclude.split(os.pathsep) if p],
    }


def configure(project_root=None, stop_at_imported=False, exclude_paths=None) -> None:
    """
    Inputs: project_root (str|Path|None) - default: the current directory;
    stop_at_imported (bool); exclude_paths (list|None) - see TracebackFormatter.
    Output: None. Changes how the active hook formats; takes effect at the
    next traceback.
    """
    _STATE["settings"] = {"project_root": project_root, "stop_at_imported": stop_at_imported,
                          "exclude_paths": list(exclude_paths or [])}
    _STATE["formatter"] = None        # rebuilt on first use


def _formatter():
    """Inputs: none. Output: TracebackFormatter - built from the current settings on first use."""
    if _STATE["formatter"] is None:
        from .formatter import TracebackFormatter
        _STATE["formatter"] = TracebackFormatter(**_STATE["settings"])
    return _STATE["formatter"]


# ---- formatting --------------------------------------------------------------

def render(text: str) -> str:
    """
    Inputs: text (str) - a traceback in Python's default format.
    Output: str - the reformatted traceback ending in a newline; text unchanged
    when the hook is off, there is no traceback header (e.g. an exception that
    was never raised), or formatting fails - a broken formatter never hides
    an error.
    """
    if not _STATE["active"] or "Traceback (most recent call last):" not in text:
        return text
    try:
        return _formatter().format(text).rstrip("\n") + "\n"
    except Exception:
        return text


def format_exception(*args, **kwargs) -> list:
    """
    Inputs: same as traceback.format_exception (exc, /, value, tb, limit, chain, ...).
    Output: list[str] - the reformatted lines, each ending in a newline.
    """
    text = "".join(_ORIGINAL["format_exception"](*args, **kwargs))
    return render(text).splitlines(keepends=True)


def print_exception(*args, **kwargs) -> None:
    """
    Inputs: same as traceback.print_exception (exc, /, value, tb, limit, file,
    chain, ...); file by position (5th, as logging passes it) or by name.
    Output: None. Writes the reformatted traceback to file (default: the
    current sys.stderr, so redirected streams still get it); nothing when
    there is no stream (pythonw).
    """
    _ensure_traceback_patched()
    import io
    args = list(args)
    buffer = io.StringIO()
    if len(args) > 4:
        target, args[4] = args[4], buffer
    else:
        target, kwargs["file"] = kwargs.get("file"), buffer
    target = target or sys.stderr
    if target is None:
        return
    _ORIGINAL["print_exception"](*args, **kwargs)
    target.write(render(buffer.getvalue()))
    try:
        target.flush()
    except Exception:
        pass


def excepthook(exc_type, exc, tb) -> None:
    """Inputs: exc_type, exc, tb - an uncaught exception. Output: None (printed to sys.stderr)."""
    print_exception(exc_type, exc, tb)


def thread_excepthook(args) -> None:
    """
    Inputs: args (threading.ExceptHookArgs).
    Output: None. Silent for SystemExit, else "Exception in thread <name>:"
    and the reformatted traceback on sys.stderr, like the default hook.
    """
    if args.exc_type is SystemExit or sys.stderr is None:
        return
    import threading
    name = args.thread.name if args.thread is not None else threading.get_ident()
    sys.stderr.write(f"Exception in thread {name}:\n")
    print_exception(args.exc_type, args.exc_value, args.exc_traceback, file=sys.stderr)


# ---- patching ------------------------------------------------------------------

def patch_traceback_module(module) -> None:
    """
    Inputs: module - the traceback module.
    Output: None. Replaces its print_exception / format_exception (once; the
    originals are kept in _ORIGINAL).
    """
    if module.print_exception is print_exception:
        return
    _ORIGINAL.setdefault("print_exception", module.print_exception)
    _ORIGINAL.setdefault("format_exception", module.format_exception)
    module.print_exception = print_exception
    module.format_exception = format_exception


def patch_threading_module(module) -> None:
    """
    Inputs: module - the threading module.
    Output: None. Replaces threading.excepthook (once).
    """
    if module.excepthook is thread_excepthook:
        return
    _ORIGINAL.setdefault("thread_excepthook", module.excepthook)
    module.excepthook = thread_excepthook


def _ensure_traceback_patched() -> None:
    """Inputs: none. Output: None. Imports the traceback module and patches it if needed."""
    if "print_exception" not in _ORIGINAL:
        import traceback
        patch_traceback_module(traceback)


def install(project_root=None, stop_at_imported=None, exclude_paths=None, lazy=False) -> bool:
    """
    Inputs: project_root, stop_at_imported, exclude_paths - formatting settings;
    any left as None comes from the PYTB_HOOK_* environment variables;
    lazy (bool) - patch traceback / threading only when something imports
    them (used at interpreter start-up), instead of importing them now.
    Output: bool - True if the hook is active; False when PYTB_HOOK=0.
    Calling it again only updates the settings.
    """
    if disabled_by_env():
        return False
    env = settings_from_env()
    configure(
        project_root=project_root if project_root is not None else env["project_root"],
        stop_at_imported=stop_at_imported if stop_at_imported is not None
        else env["stop_at_imported"],
        exclude_paths=exclude_paths if exclude_paths is not None else env["exclude_paths"],
    )
    if not _STATE["active"]:
        _ORIGINAL.setdefault("excepthook", sys.excepthook)
        sys.excepthook = excepthook
        _STATE["active"] = True
    for name, patch in (("traceback", patch_traceback_module),
                        ("threading", patch_threading_module)):
        if name in sys.modules:
            patch(sys.modules[name])
        elif lazy:
            from ._lazy import patch_on_import
            patch_on_import(name, patch)
        else:
            patch(__import__(name))
    return True


def uninstall() -> None:
    """
    Inputs: none.
    Output: None. Restores Python's own functions and hooks in this process
    and cancels pending lazy patches.
    """
    lazy = sys.modules.get(__package__ + "._lazy")
    if lazy is not None:
        lazy.cancel_all()
    if "excepthook" in _ORIGINAL and sys.excepthook is excepthook:
        sys.excepthook = _ORIGINAL["excepthook"]
    tb = sys.modules.get("traceback")
    if tb is not None and "print_exception" in _ORIGINAL:
        tb.print_exception = _ORIGINAL["print_exception"]
        tb.format_exception = _ORIGINAL["format_exception"]
    th = sys.modules.get("threading")
    if th is not None and "thread_excepthook" in _ORIGINAL:
        th.excepthook = _ORIGINAL["thread_excepthook"]
    _ORIGINAL.clear()
    _STATE.update(formatter=None, active=False)


def is_active() -> bool:
    """Inputs: none. Output: bool - the hook is installed in this process."""
    return _STATE["active"]
