from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class Corpus:
    messages: tuple[Any, ...]
    skipped: int = 0

@dataclass(frozen=True)
class Point:
    original_index: int
    second: float
    row: int
    is_system: bool = False

@dataclass(frozen=True)
class TimelineView:
    day: str
    start: float
    end: float
    count: int
    labels: tuple[str, ...]
    points: tuple[Point, ...]
    aggregated: bool
    # (minute of day, row, count) when density mode is active.
    density: tuple[tuple[int, int, int], ...] = ()
    row_kinds: tuple[bool, ...] = ()
