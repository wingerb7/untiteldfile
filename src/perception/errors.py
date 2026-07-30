from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PerceptionError(ValueError):
    code: str
    detail: str
    stage: str = "perception"

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"
