"""
pytb-hook command line (also: python -m pytb_hook).

    pytb-hook status                      is the hook installed / active for this interpreter?
    pytb-hook format [FILE]               reformat a traceback from FILE or stdin
        --stop-at-imported --project-root DIR --exclude DIR (repeatable)
    pytb-hook demo                        raise an error to show the format
"""
import argparse
import os
import sys
import sysconfig
from pathlib import Path


def _pth_locations() -> list:
    """
    Inputs: none.
    Output: list[Path] - pytb_hook.pth files found in this interpreter's
    site-packages folders (user site included).
    """
    import site
    folders = {sysconfig.get_paths()["purelib"], sysconfig.get_paths()["platlib"]}
    try:
        folders.update(site.getsitepackages())
    except AttributeError:
        pass
    if site.ENABLE_USER_SITE:
        folders.add(site.getusersitepackages())
    return sorted(p for p in (Path(f) / "pytb_hook.pth" for f in folders) if p.is_file())


def cmd_status(_opts) -> int:
    """Inputs: _opts (argparse.Namespace). Output: int - 0 if active at start-up, else 1."""
    from . import __version__
    from .hook import disabled_by_env, is_active, settings_from_env
    pth = _pth_locations()
    print(f"pytb-hook {__version__} on Python {sys.version.split()[0]} ({sys.executable})")
    print(f"  start-up file : {', '.join(map(str, pth)) or 'not found (hook is not auto-loaded)'}")
    print(f"  disabled by env (PYTB_HOOK=0): {disabled_by_env()}")
    print(f"  active in this process: {is_active()}")
    settings = settings_from_env()
    print(f"  stop_at_imported={settings['stop_at_imported']} "
          f"project_root={settings['project_root'] or '(cwd)'} "
          f"exclude={settings['exclude_paths'] or '[]'}")
    return 0 if is_active() else 1


def cmd_format(opts) -> int:
    """
    Inputs: opts (argparse.Namespace) - file, stop_at_imported, project_root, exclude.
    Output: int - 0. Prints the reformatted text.
    """
    from .formatter import TracebackFormatter
    text = Path(opts.file).read_text(encoding="utf-8", errors="replace") if opts.file \
        else sys.stdin.read()
    formatter = TracebackFormatter(opts.project_root, opts.stop_at_imported, opts.exclude)
    print(formatter.format(text))
    return 0


def cmd_demo(_opts) -> int:
    """Inputs: _opts (argparse.Namespace). Output: never returns normally (raises ValueError)."""
    def inner(value):
        """Inputs: value (int). Output: none - always raises ValueError."""
        raise ValueError(f"demo error for value={value}")
    inner(42)
    return 0


def main(argv=None) -> int:
    """
    Inputs: argv (list[str]|None) - arguments (default: sys.argv[1:]).
    Output: int - exit code of the chosen sub-command.
    """
    parser = argparse.ArgumentParser(prog="pytb-hook", description="Reason-first Python tracebacks.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="show whether the hook is installed and active")
    fmt = sub.add_parser("format", help="reformat a traceback read from FILE or stdin")
    fmt.add_argument("file", nargs="?")
    fmt.add_argument("--stop-at-imported", action="store_true",
                     help="cut at the first frame outside --project-root")
    fmt.add_argument("--project-root", default=os.getcwd())
    fmt.add_argument("--exclude", action="append", default=[],
                     help="folder never counted as project (repeatable)")
    sub.add_parser("demo", help="raise an error to show the format")

    opts = parser.parse_args(argv)
    return {"status": cmd_status, "format": cmd_format, "demo": cmd_demo}[opts.command](opts)


if __name__ == "__main__":
    sys.exit(main())
