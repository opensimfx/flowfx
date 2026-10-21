from __future__ import annotations

import hashlib
import json
import re
import uuid


def new_uid() -> str:
    return uuid.uuid4().hex[:12]


def stable_hash(obj) -> str:
    """Order-independent short hash of JSON-serialisable data (stale cache detection)."""
    raw = json.dumps(obj, sort_keys=True, default=str).encode()
    return hashlib.sha1(raw).hexdigest()[:12]


def slug(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_").lower() or "body"
