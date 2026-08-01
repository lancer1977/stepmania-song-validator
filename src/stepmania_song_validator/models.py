"""Shared data structures used across all check modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass
class Finding:
    """A single validation finding attached to a file or folder."""

    category: str  # "chart_integrity" | "duplicate" | "batocera_layout"
    severity: Severity
    code: str
    message: str
    path: Path

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "severity": self.severity.value,
            "code": self.code,
            "message": self.message,
            "path": str(self.path),
        }


@dataclass
class Report:
    """Aggregate result of a full library validation run."""

    library_path: Path
    findings: list[Finding] = field(default_factory=list)
    songs_scanned: int = 0
    charts_scanned: int = 0

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)

    @property
    def error_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == Severity.WARNING)

    @property
    def ok(self) -> bool:
        return self.error_count == 0

    def to_dict(self) -> dict:
        return {
            "library_path": str(self.library_path),
            "songs_scanned": self.songs_scanned,
            "charts_scanned": self.charts_scanned,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "ok": self.ok,
            "findings": [f.to_dict() for f in self.findings],
        }
