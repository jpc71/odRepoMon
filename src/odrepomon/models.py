from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class MirrorStats:
    copied: int = 0
    skipped: int = 0
    failed: int = 0
    deleted: int = 0


@dataclass(slots=True)
class CopyDecision:
    source: Path
    destination: Path
    action: str
