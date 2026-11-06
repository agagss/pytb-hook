"""
Tests for the process-wide hook. Each case runs a fresh interpreter, so they
check what the installed .pth start-up hook really does (the package must be
installed in the interpreter running the tests: pip install -e . or pip install .).
"""
import os
import subprocess
import sys
import textwrap

import pytest

HEADER = "Traceback (most recent call last):"


def run(code: str, **env) -> subprocess.CompletedProcess:
    """
    Inputs: code (str) - Python source for a fresh interpreter; env - extra
    environment variables.
    Output: CompletedProcess - captured stdout/stderr (text).
    """
    full_env = {k: v for k, v in os.environ.items() if not k.startswith("PYTB_HOOK")}
    full_env.update(env)
    return subprocess.run([sys.executable, "-c", textwrap.dedent(code)],
                          capture_output=True, text=True, env=full_env, timeout=60)


def assert_reason_first(stderr: str, reason: str) -> None:
    """Inputs: stderr (str); reason (str) - expected first line. Output: None (asserts)."""
    assert reason in stderr, stderr
    assert stderr.index(reason) < stderr.index(HEADER), stderr


@pytest.fixture(autouse=True, scope="module")
def require_startup_hook():
    """Inputs: none. Output: None - skips the module when the .pth hook is not installed."""
    probe = run("import sys; print(sys.excepthook.__module__)")
    if probe.stdout.strip() != "pytb_hook.hook":
        pytest.skip("pytb_hook.pth is not active for this interpreter (pip install the package)")


def test_uncaught():
    """Inputs: none. Output: None - an uncaught exception prints reason first, exit code 1."""
    res = run("def f(): raise ValueError('bad value')\nf()")
    assert res.returncode == 1
    assert_reason_first(res.stderr, "ValueError: bad value")


def test_print_exc_and_format_exc():
    """Inputs: none. Output: None - traceback.print_exc / format_exc use the format."""
    res = run("""
        import sys, traceback
        try: 1/0
        except Exception:
            traceback.print_exc()
            sys.stdout.write(traceback.format_exc())
    """)
    assert_reason_first(res.stderr, "ZeroDivisionError")
    assert_reason_first(res.stdout, "ZeroDivisionError")


def test_logging_and_threads():
    """Inputs: none. Output: None - logger.exception and thread crashes use the format."""
    res = run("""
        import logging, threading
        try: {}['k']
        except Exception: logging.exception('oops')
        t = threading.Thread(target=lambda: [][1], name='worker'); t.start(); t.join()
    """)
    assert "Exception in thread worker:" in res.stderr
    assert_reason_first(res.stderr, "KeyError: 'k'")
    assert_reason_first(res.stderr.split("Exception in thread worker:")[1], "IndexError")


def test_lazy_startup():
    """Inputs: none. Output: None - start-up imports neither traceback nor the formatter."""
    res = run("import sys; print('traceback' in sys.modules, 'pytb_hook.formatter' in sys.modules)")
    assert res.stdout.split() == ["False", "False"]


def test_disabled_by_env():
    """Inputs: none. Output: None - PYTB_HOOK=0 keeps Python's default output."""
    res = run("1/0", PYTB_HOOK="0")
    assert res.stderr.lstrip().startswith(HEADER)


def test_stop_at_imported_env(tmp_path):
    """Inputs: tmp_path. Output: None - PYTB_HOOK_STOP_AT_IMPORTED cuts at library frames."""
    res = run("import json; json.loads('{')", PYTB_HOOK_STOP_AT_IMPORTED="1",
              PYTB_HOOK_PROJECT_ROOT=str(tmp_path))
    assert_reason_first(res.stderr, "json.decoder.JSONDecodeError")
    assert "json/decoder.py" not in res.stderr.replace("\\", "/")
