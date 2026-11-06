"""Tests for pytb_hook.formatter.TracebackFormatter (pure text in, text out)."""
from pathlib import Path

from pytb_hook import TracebackFormatter, format_traceback

RAW = '''some stdout
Traceback (most recent call last):
  File "/proj/main.py", line 9, in <module>
    run()
    ~~~^^
  File "/proj/main.py", line 5, in run
    raise ValueError("bad value")
ValueError: bad value
'''

EXPECTED = '''ValueError: bad value

Traceback (most recent call last):
  File "/proj/main.py", line 9, in <module>
    run()
    ~~~^^
  File "/proj/main.py", line 5, in run
    raise ValueError("bad value")'''


def test_reason_moves_first():
    """Inputs: none. Output: None - the reason is put above the frames, noise dropped."""
    assert format_traceback(RAW) == EXPECTED


def test_idempotent():
    """Inputs: none. Output: None - formatting an already formatted report changes nothing."""
    assert format_traceback(EXPECTED) == EXPECTED
    assert format_traceback("child said hi\n" + EXPECTED + "\n") == EXPECTED


def test_keeps_only_last_traceback():
    """Inputs: none. Output: None - in a chain only the final traceback is kept."""
    chained = (RAW + "\nDuring handling of the above exception, another exception occurred:\n\n"
               'Traceback (most recent call last):\n  File "/proj/main.py", line 12, in <module>\n'
               "    handle()\nKeyError: 'x'\n")
    out = format_traceback(chained)
    assert out.startswith("KeyError: 'x'")
    assert "ValueError" not in out and "line 12" in out


def test_no_traceback_is_returned_unchanged():
    """Inputs: none. Output: None - text without frames comes back stripped, not altered."""
    assert format_traceback("  just an error message\n") == "just an error message"
    assert format_traceback("") == ""


def test_missing_reason_falls_back():
    """Inputs: none. Output: None - truncated output gets the 'unknown' reason."""
    cut = 'Traceback (most recent call last):\n  File "/proj/a.py", line 1, in <module>\n    x()\n'
    assert format_traceback(cut).startswith(TracebackFormatter.UNKNOWN_REASON)


def test_stop_at_imported(tmp_path: Path):
    """Inputs: tmp_path (Path). Output: None - frames are cut at the first library frame."""
    project = tmp_path / "proj"
    lib = tmp_path / "venv" / "lib" / "site-packages" / "lib.py"
    raw = (f'Traceback (most recent call last):\n'
           f'  File "{project / "main.py"}", line 3, in <module>\n    lib.call()\n'
           f'  File "{lib}", line 10, in call\n    inner()\n'
           f'  File "{project / "cb.py"}", line 2, in inner\n    1/0\n'
           f'ZeroDivisionError: division by zero\n')
    full = TracebackFormatter(project).format(raw)
    cut = TracebackFormatter(project, stop_at_imported=True).format(raw)
    assert full.count('File "') == 3
    assert cut.count('File "') == 1 and "main.py" in cut
    assert cut.startswith("ZeroDivisionError")


def test_exclude_paths(tmp_path: Path):
    """Inputs: tmp_path (Path). Output: None - an excluded project folder ends the traceback."""
    vendored = tmp_path / "vendor"
    raw = (f'Traceback (most recent call last):\n'
           f'  File "{tmp_path / "main.py"}", line 1, in <module>\n    go()\n'
           f'  File "{vendored / "x.py"}", line 2, in go\n    boom()\n'
           f'RuntimeError: boom\n')
    out = TracebackFormatter(tmp_path, True, [vendored]).format(raw)
    assert out.count('File "') == 1


def test_custom_exception_name_after_stdout():
    """Inputs: none. Output: None - a custom exception name is found below program output."""
    text = EXPECTED.replace("ValueError: bad value", "Boom: it broke", 1)
    assert format_traceback("Result: 5\nall good\n" + text).startswith("Boom: it broke")
