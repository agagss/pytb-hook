"""
TracebackFormatter: Python's default traceback text -> a short report with the
reason first:

    ValueError: bad value

    Traceback (most recent call last):
      File ".../main.py", line 9, in <module>
        run()
      File ".../main.py", line 5, in run
        raise ValueError("bad value")

It works on text (stderr of any process, a log file), not on exception
objects, so it can reformat the output of programs it does not run in.
"""
import re
from pathlib import Path


class TracebackFormatter:
    """
    Turns raw Python output into a trimmed traceback report.

    - Only the LAST traceback in the text is kept (earlier chained exceptions
      are dropped); source lines and ^^^^ markers stay with their frame.
    - The reason ("ValueError: ...") is moved above the frames.
    - Text already in this format is read too, so formatting twice is a no-op.
    - With stop_at_imported, the traceback is cut at the first frame outside
      project_root (or inside exclude_paths / site-packages / dist-packages).
    """

    HEADER = "Traceback (most recent call last):"
    FRAME_RE = re.compile(r'^\s*File "(.+?)", line (\d+)(?:, in (.+))?\s*$')
    EXTERNAL_DIRS = {"site-packages", "dist-packages"}
    UNKNOWN_REASON = "RuntimeError: unknown Python error"
    # "ValueError: x", "pkg.mod.TimeoutError", "KeyboardInterrupt" ...
    EXC_LINE_RE = re.compile(
        r"^[A-Za-z_][\w.]*(?:Error|Exception|Warning|Exit|Interrupt|Iteration|Group|Fault)"
        r"(?::\s.*|:)?$")
    # any dotted name, optionally followed by ": message" (custom exception names)
    NAME_LINE_RE = re.compile(r"^[A-Za-z_][\w.]*(?::\s.*|:)?$")

    def __init__(self, project_root=None, stop_at_imported=False, exclude_paths=None):
        """
        Inputs: project_root (str|Path|None) - frames under it are project
        frames (default: the current directory); stop_at_imported (bool) - cut
        the traceback at the first non-project frame; exclude_paths
        (list|None) - folders always treated as outside the project.
        Output: None.
        """
        self.project_root = Path(project_root or Path.cwd()).resolve()
        self.stop_at_imported = stop_at_imported
        self.exclude_paths = [Path(p).resolve() for p in (exclude_paths or [])]

    def format(self, output, stop_at_imported=None) -> str:
        """
        Inputs: output (str) - raw stdout/stderr text holding a traceback;
        stop_at_imported (bool|None) - overrides the instance setting.
        Output: str - "<reason>\\n\\nTraceback (most recent call last):\\n  <frames>",
        or the stripped input unchanged when no frame can be read from it.
        """
        stop = self.stop_at_imported if stop_at_imported is None else stop_at_imported

        lines = (output or "").splitlines()
        start = 0
        for i, line in enumerate(lines):
            if line.strip() == self.HEADER:
                start = i + 1          # keep only the last traceback

        frames, reason_lines = [], []
        for line in lines[start:]:
            m = self.FRAME_RE.match(line)
            if m and not reason_lines:
                frames.append({"text": line.strip(), "path": self._resolve_path(m.group(1))})
            elif not frames:
                continue                # noise before the first frame
            elif not reason_lines and (line.startswith((" ", "\t")) or not line.strip()):
                if line.strip():
                    frames[-1]["text"] += "\n" + line.rstrip()   # source line / ^^^^
            else:
                reason_lines.append(line.rstrip())

        if not frames:
            return (output or "").strip()

        if not reason_lines:
            reason_lines = self._reason_before_header(lines, start - 1)

        if stop:
            frames = self._filter_frames(frames)

        reason = "\n".join(reason_lines).strip() or self.UNKNOWN_REASON
        result = [reason, "", self.HEADER]
        result.extend(f"  {f['text']}" for f in frames)
        return "\n".join(result)

    @classmethod
    def _reason_before_header(cls, lines, header_index):
        """
        Inputs: lines (list[str]) - the text's lines; header_index (int) -
        index of the last traceback header line.
        Output: list[str] - for text already in this format ("<reason>", "",
        header, frames...), the reason: the non-blank lines just above the
        blank line before the header, starting at the first line that looks
        like an exception ("ValueError: ...", "pkg.MyError"), so program output
        printed right before it is left out. [] otherwise.
        """
        end = header_index - 1
        if end < 1 or lines[end].strip():
            return []
        begin = end
        while begin > 0 and lines[begin - 1].strip():
            begin -= 1
        block = [line.rstrip() for line in lines[begin:end]]
        for i, line in enumerate(block):           # first well-known exception name
            if cls.EXC_LINE_RE.match(line):
                return block[i:]
        for i in range(len(block) - 1, -1, -1):    # else the last name-like line
            if cls.NAME_LINE_RE.match(block[i]):
                return block[i:]
        return block

    @staticmethod
    def _resolve_path(location):
        """
        Inputs: location (str) - path text from a File "..." line.
        Output: Path|None - resolved path; None for "<string>", "<frozen ...>"
        or anything unresolvable.
        """
        if location.startswith("<"):
            return None
        try:
            return Path(location).resolve()
        except (OSError, ValueError):
            return None

    def _filter_frames(self, frames):
        """
        Inputs: frames (list[dict]) - parsed frames, outermost first.
        Output: list[dict] - frames up to (not including) the first excluded or
        non-project frame. Frames with no known path are kept.
        """
        filtered = []
        for frame in frames:
            path = frame["path"]
            if path is None:
                filtered.append(frame)
                continue
            if self._is_excluded(path) or not self._is_project_file(path):
                break
            filtered.append(frame)
        return filtered

    def _is_project_file(self, path):
        """
        Inputs: path (Path).
        Output: bool - True if under project_root and not inside site-packages /
        dist-packages (so a venv located in the project still counts as external).
        """
        if self.EXTERNAL_DIRS & set(path.parts):
            return False
        try:
            path.relative_to(self.project_root)
            return True
        except ValueError:
            return False

    def _is_excluded(self, path):
        """
        Inputs: path (Path).
        Output: bool - True if path is, or is inside, one of exclude_paths.
        """
        for excluded in self.exclude_paths:
            if path == excluded or excluded in path.parents:
                return True
        return False


def format_traceback(text, project_root=None, stop_at_imported=False, exclude_paths=None) -> str:
    """
    Inputs: text (str) - raw output holding a Python traceback; project_root,
    stop_at_imported, exclude_paths - as TracebackFormatter.
    Output: str - the formatted report (see TracebackFormatter.format).
    """
    return TracebackFormatter(project_root, stop_at_imported, exclude_paths).format(text)
