from __future__ import annotations

_ENGINES: dict = {}


def register(engine_cls):
    inst = engine_cls()
    if not inst.id:
        raise ValueError("engine must define an id")
    _ENGINES[inst.id] = inst
    return engine_cls


def get(engine_id: str):
    load_builtin()
    try:
        return _ENGINES[engine_id]
    except KeyError:
        raise KeyError(f"no engine registered as '{engine_id}'") from None


def available() -> list:
    load_builtin()
    return sorted(_ENGINES)


_loaded = False


def load_builtin():
    global _loaded
    if _loaded:
        return
    _loaded = True
    from .fluid import engine as _f  # noqa: F401
    from .heightfield import engine as _h  # noqa: F401
    from .spectral import engine as _s  # noqa: F401
    from .spectral import interaction as _i  # noqa: F401
