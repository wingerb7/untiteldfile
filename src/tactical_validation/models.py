from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ValidationOutcome(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass(frozen=True)
class ValidationResult:
    check: str
    subject_id: str
    outcome: ValidationOutcome
    detail: str
    evidence: dict[str, Any] = field(default_factory=dict)
