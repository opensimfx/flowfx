from __future__ import annotations

import hashlib
import json
import re
import uuid


_UID_RE = re.compile(r"[0-9a-f]{12}")


def new_uid() -> str:
    return uuid.uuid4().hex[:12]


def is_uid(value) -> bool:
    """True for a body ID in the format ``new_uid`` makes. A .blend is untrusted input: an ID read from it is only
    used in a cache path when it matches exactly (no "..", separators or absolute paths)."""
    return isinstance(value, str) and _UID_RE.fullmatch(value) is not None


def stable_hash(obj) -> str:
    """Order-independent short hash of JSON-serialisable data (stale cache detection)."""
    raw = json.dumps(obj, sort_keys=True, default=str).encode()
    return hashlib.sha1(raw).hexdigest()[:12]


def slug(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower() or "body"
