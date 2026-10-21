"""Secondary (whitewater) particle configuration: spray, foam, bubbles."""
from __future__ import annotations

_FLAGS = ("use_spray_particles", "use_foam_particles", "use_bubble_particles")


def _set_flag(ds, name: str, desired: bool):
    """Set a boolean only when it differs.

    In Blender 5.2.2 these three RNA setters toggle the flag whatever value is assigned
    (docs/spikes.md S10), so assigning blindly can flip a flag the wrong way.
    """
    if getattr(ds, name) != desired:
        setattr(ds, name, desired)
    if getattr(ds, name) != desired:
        raise RuntimeError(f"could not set {name} to {desired}")


def configure_secondary(ds, spray: bool, foam: bool, bubbles: bool, **tuning):
    for name, value in zip(_FLAGS, (spray, foam, bubbles)):
        _set_flag(ds, name, bool(value))
    for key, value in tuning.items():
        if not key.startswith("sndparticle_"):
            raise KeyError(f"'{key}' is not a secondary particle property")
        setattr(ds, key, value)
    return ds
