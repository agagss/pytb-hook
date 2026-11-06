"""
Run a function on a module right after it is first imported, without importing
it now. Used at interpreter start-up so the hook does not pay for importing
traceback / threading in processes that never print a traceback.
"""
import sys

_PENDING: dict = {}     # module name -> callback(module)


class _PatchOnImport:
    """
    A sys.meta_path finder that finds nothing itself: for a watched module it
    asks the other finders for the spec, then wraps the loader's exec_module
    so the callback runs once the module has been executed.
    """

    def find_spec(self, name, path=None, target=None):
        """
        Inputs: name (str) - module being imported; path, target - as importlib passes them.
        Output: ModuleSpec|None - the real spec with a wrapped loader for a watched
        module; None (let the other finders handle it) for anything else.
        """
        if name not in _PENDING:
            return None
        for finder in sys.meta_path:
            if finder is self or not hasattr(finder, "find_spec"):
                continue
            spec = finder.find_spec(name, path, target)
            if spec is not None:
                break
        else:
            return None
        loader = spec.loader
        if loader is None or not hasattr(loader, "exec_module"):
            return spec
        original_exec = loader.exec_module

        def exec_module(module):
            """Inputs: module - the new module. Output: None. Executes it, then runs the callback."""
            original_exec(module)
            callback = _PENDING.pop(name, None)
            if callback is not None:
                try:
                    callback(module)
                except Exception:
                    pass
            if not _PENDING:
                _remove_finder()

        loader.exec_module = exec_module
        return spec


_FINDER = _PatchOnImport()


def _remove_finder() -> None:
    """Inputs: none. Output: None. Takes the finder off sys.meta_path."""
    try:
        sys.meta_path.remove(_FINDER)
    except ValueError:
        pass


def patch_on_import(name: str, callback) -> None:
    """
    Inputs: name (str) - top-level module name; callback (callable(module)).
    Output: None. Runs callback(module) right after `name` is first imported
    (immediately if it already is).
    """
    if name in sys.modules:
        callback(sys.modules[name])
        return
    _PENDING[name] = callback
    if _FINDER not in sys.meta_path:
        sys.meta_path.insert(0, _FINDER)


def cancel_all() -> None:
    """Inputs: none. Output: None. Drops every pending callback and the finder."""
    _PENDING.clear()
    _remove_finder()
