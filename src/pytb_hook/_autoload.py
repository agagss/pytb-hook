"""
Imported at every interpreter start-up by pytb_hook.pth (site-packages).
Installs the hook lazily; any failure is swallowed so a broken hook can never
stop Python from starting.
"""
try:
    from .hook import install as _install
    _install(lazy=True)
except Exception:  # pragma: no cover - never block interpreter start-up
    pass
