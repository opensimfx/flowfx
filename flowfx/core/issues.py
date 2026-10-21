from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class Severity(IntEnum):
    INFO = 0
    WARNING = 1
    ERROR = 2


@dataclass
class Issue:
    severity: Severity
    code: str
    message: str
    target: str = ""
    fix_op: str = ""

    def __str__(self) -> str:
        return f"[{self.severity.name}] {self.code}: {self.message}"
