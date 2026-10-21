"""Guiding: low-res domain (or effector) drives a high-res region of interest. Feasibility: spike S3."""
from __future__ import annotations


def enable_guide(ds, source: str = "DOMAIN", parent=None, vel_factor: float = 2.0, alpha: float = 2.0,
                 beta: int = 5):
    if source not in ("DOMAIN", "EFFECTOR"):
        raise ValueError("guide source must be DOMAIN or EFFECTOR")
    if source == "DOMAIN" and parent is None:
        raise ValueError("a DOMAIN guide needs the parent (low-resolution) domain object")
    ds.use_guide = True
    ds.guide_source = source
    if parent is not None:
        ds.guide_parent = parent
    ds.guide_vel_factor = vel_factor
    ds.guide_alpha = alpha
    ds.guide_beta = beta
    return ds
