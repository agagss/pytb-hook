# pytb-hook

Reason-first, trimmed Python tracebacks for **every** Python process of an
interpreter. Install it and every traceback looks like this:

```
ValueError: bad value

Traceback (most recent call last):
  File "/proj/main.py", line 9, in <module>
    run()
  File "/proj/main.py", line 5, in run
    raise ValueError("bad value")
```

- The reason comes first, then the frames.
- Only the **last** traceback of a chain is kept.
- Optionally the traceback is **cut at the first non-project frame**.
- Output that is already in this format is read too, so reformatting a
  child process's output twice is a no-op.

## Install

```bash
pip install /path/to/pytb-hook                   # or: pip install git+https://github.com/<you>/pytb-hook
pip install -e /path/to/pytb-hook                # editable, while you work on it
```

Run that with every interpreter or venv you want covered (`path/to/venv/bin/python -m pip install ...`).
A wheel puts `pytb_hook.pth` in site-packages. Python runs it at start-up, so the
hook is on in every script, REPL, test run and tool started with that interpreter.
`pip uninstall pytb-hook` removes it again.

Start-up stays cheap: only `sys`/`os` are touched. `traceback` and `threading` are
patched when something imports them, and the formatter loads on the first traceback.

## What it covers

| Source | How |
|---|---|
| uncaught exceptions | `sys.excepthook` |
| uncaught exceptions in threads | `threading.excepthook` |
| `traceback.print_exc / format_exc / print_exception / format_exception / print_last` | patched `traceback` module |
| `logging` (`exc_info=True`, `logger.exception`), asyncio's error handler | through the `traceback` module |

## Settings (environment)

| Variable | Effect |
|---|---|
| `PYTB_HOOK=0` | off for that process (`off`/`false`/`no` work too) |
| `PYTB_HOOK_STOP_AT_IMPORTED=1` | cut at the first frame outside the project root |
| `PYTB_HOOK_PROJECT_ROOT=<dir>` | project root for the cut (default: current directory) |
| `PYTB_HOOK_EXCLUDE=<dir>:<dir>` | folders never counted as project (`;` on Windows) |

site-packages / dist-packages always count as outside the project.

## Library use

```python
from pytb_hook import TracebackFormatter, format_traceback, install, uninstall, configure

TracebackFormatter(project_root=".", stop_at_imported=True).format(stderr_text)
configure(project_root="/my/project", stop_at_imported=True)   # change the live hook
uninstall()                                                    # this process only
```

## Command line

```bash
pytb-hook status                          # is the .pth there, is the hook active?
pytb-hook format crash.log                # reformat a saved traceback (or pipe via stdin)
pytb-hook format --stop-at-imported --project-root . < err.txt
pytb-hook demo                            # raise an error to see the format
```

## Develop

```bash
pip install -e ".[test]"
pytest
```
